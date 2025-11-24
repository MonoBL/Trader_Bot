import aiohttp
import time
import socket

class DataEngine:
    def __init__(self):
        self.dex_api = "https://api.dexscreener.com/latest/dex/tokens/"
        self.rugcheck_api = "https://api.rugcheck.xyz/v1/tokens/"
        self.jupiter_quote_api = "https://public.jupiterapi.com/quote"
        self.jupiter_swap_api = "https://public.jupiterapi.com/swap"

    async def get_token_data(self, token_address):
        """Fetches data and SUMS liquidity across all pairs"""
        conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                url = self.dex_api + token_address
                
                async with session.get(url) as response:
                    if response.status != 200: return None
                    data = await response.json()
                    
                    if not data.get('pairs'): return None

                    pairs = data['pairs']
                    
                    # --- NEW LOGIC: Calculate Totals ---
                    total_liquidity = 0
                    total_volume = 0
                    main_pair = None
                    
                    for p in pairs:
                        # Only count Solana pairs
                        if p.get('chainId') == 'solana':
                            # Set the first valid pair as the "Main" one for price/info
                            if main_pair is None:
                                main_pair = p
                            
                            # Add to totals
                            total_liquidity += float(p.get('liquidity', {}).get('usd', 0))
                            total_volume += float(p.get('volume', {}).get('h24', 0))
                    
                    if not main_pair: return None

                    # --- Process Main Pair Data ---
                    created_at = main_pair.get('pairCreatedAt', time.time() * 1000)
                    current_time = time.time() * 1000
                    age_hours = (current_time - created_at) / (1000 * 3600)

                    price_change = main_pair.get('priceChange', {})
                    txns = main_pair.get('txns', {}).get('h24', {})

                    return {
                        "name": main_pair['baseToken'].get('name', 'Unknown'),
                        "symbol": main_pair['baseToken'].get('symbol', 'Unknown'),
                        "address": main_pair['baseToken']['address'], # Token Mint
                        "pairAddress": main_pair.get('pairAddress', token_address),
                        
                        "price": float(main_pair.get('priceUsd', 0)),
                        
                        # USE THE TOTALS HERE
                        "liquidity": total_liquidity, 
                        "volume_24h": total_volume,
                        
                        "fdv": float(main_pair.get('fdv', 0)),
                        "market_cap": float(main_pair.get('marketCap', 0)),
                        "age_hours": round(age_hours, 1),
                        
                        # Transaction counts (We stick to main pair for this as summing is tricky)
                        "buy_tx_count": int(txns.get('buys', 0)),
                        "sell_tx_count": int(txns.get('sells', 0)),
                        
                        "price_change_1h": float(price_change.get('h1', 0)),
                        "price_change_24h": float(price_change.get('h24', 0)),
                        "top_10_percentage": 0 
                    }
                    
        except Exception as e:
            print(f"❌ Error in get_token_data: {e}")
            return None

    # ... (Keep check_safety and get_swap_transaction exactly the same) ...
    async def check_safety(self, token_address):
        conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(f"{self.rugcheck_api}{token_address}/report") as response:
                    if response.status == 200:
                        data = await response.json()
                        score = data.get('score', 0)
                        risks = [risk['name'] for risk in data.get('risks', [])]
                        return {"score": score, "risks": risks}
        except Exception as e:
            print(f"⚠️ RugCheck Error: {e}")
        return {"score": "Unknown", "risks": []}

    async def get_swap_transaction(self, user_pubkey, input_mint, output_mint, amount_lamports):
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": 100
        }
        conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            try:
                async with session.get(self.jupiter_quote_api, params=params) as response:
                    if response.status != 200: return None
                    quote_data = await response.json()
                    
                payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": user_pubkey,
                    "wrapAndUnwrapSol": True
                }
                async with session.post(self.jupiter_swap_api, json=payload) as response:
                    if response.status != 200: return None
                    swap_data = await response.json()
                    return swap_data.get('swapTransaction')
            except Exception as e:
                print(f"⚠️ Jupiter Connection Error: {e}")
                return None