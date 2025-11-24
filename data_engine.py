import aiohttp
import json
import time
import socket


class DataEngine:
    def __init__(self):
        self.dex_api = "https://api.dexscreener.com/latest/dex/tokens/"
        self.rugcheck_api = "https://api.rugcheck.xyz/v1/tokens/"
        self.jupiter_quote_api = "https://public.jupiterapi.com/quote"
        self.jupiter_swap_api = "https://public.jupiterapi.com/swap"

    async def get_token_data(self, token_address):
        #Will get prces adn liquidity from DexScreener
        conn=aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                url =self.dex_api + token_address
                print(f"🔍 Fetching: {url}") # DEBUG PRINT

                async with session.get(url) as response:
                    # 1. Check HTTP Status
                    if response.status != 200:
                        print(f"❌ DexScreener HTTP Error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    # 2. Check if Pairs exist
                    if not data.get('pairs'):
                        print(f"❌ DexScreener returned JSON, but 'pairs' list is empty.")
                        # Sometimes DexScreener returns null for new pairs, wait 1s and retry?
                        return None

                    # DexScreener returns multiple pairs. We want the biggest Solana one.
                    pairs = data['pairs']
                    pair = None
                    
                    # Find the first pair that is on Solana
                    for p in pairs:
                        if p.get('chainId') == 'solana':
                            pair = p
                            break
                    
                    if not pair:
                        print("❌ Token found, but no Solana pair detected.")
                        return None
                    created_at = pair.get('pairCreatedAt', time.time() * 1000)
                    current_time = time.time() * 1000
                    age_hours = (current_time - created_at) / (1000 * 3600)

                    price_change = pair.get('priceChange', {})
                    txns = pair.get('txns', {}).get('h24', {})
                    volume = pair.get('volume', {})
                    liquidity = pair.get('liquidity', {})
                    return{
                                #Identy
                                "name": pair['baseToken'].get('name', 'Unknown'),
                                "symbol": pair['baseToken'].get('symbol', 'Unknown'),
                                "pairAddress": pair.get('pairAddress', token_address),
                                "address": pair['baseToken']['address'], 
                                
                                # Market Stats
                                "price": float(pair.get('priceUsd', 0)),
                                "liquidity": float(liquidity.get('usd', 0)),
                                "volume_24h": float(volume.get('h24', 0)),
                                "fdv": float(pair.get('fdv', 0)),
                                "market_cap": float(pair.get('marketCap', 0)),
                                
                                # Momentum / Activity
                                "age_hours": round(age_hours, 1),
                                "buy_tx_count": int(txns.get('buys', 0)),
                                "sell_tx_count": int(txns.get('sells', 0)),
                                
                                # Price Changes (Safe Access)
                                "price_change_1h": float(price_change.get('h1', 0)),
                                "price_change_24h": float(price_change.get('h24', 0)),
                                
                                "top_10_percentage": 0
                                #Dex doesnt always give holders %
                                #Asuume 0 or get info from Solscan
                            }
        except Exception as e:
            print(f"❌ Network/Code Error in get_token_data: {e}")
            return None

    
    async def check_safety(self, token_address):
        conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        """Checks if the token is a honeypot via RugCheck"""
        async with aiohttp.ClientSession(connector=conn) as session:
            try:
                async with session.get(f"{self.rugcheck_api}{token_address}/report") as response:
                    if response.status == 200:
                        data = await response.json()
                        score = data.get('score', 0)
                        risks = [risk['name'] for risk in data.get('risks', [])]
                        return {"score": score, "risks": risks}
            except Exception as e:
                print(f"⚠️ RugCheck Error: {e}")
        
        # Default if API fails
        return {"score": "Unknown", "risks": []}
    
    async def get_swap_transaction(self, user_pubkey, input_mint, output_mint, amount_lamports):
        """Gets a serialized transaction from Jupiter to sign"""
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": 100 # 1% slippage
        }

        conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            try:
                async with session.get(self.jupiter_quote_api, params=params) as response:
                    if response.status != 200:
                        print(f"Jupiter Quote Error: {await response.text()}")
                        return None
                    quote_data = await response.json()
                    
                payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": user_pubkey,
                    "wrapAndUnwrapSol": True
                }
                async with session.post(self.jupiter_swap_api, json=payload) as response:
                    if response.status != 200:
                        return None
                    swap_data = await response.json()
                    return swap_data.get('swapTransaction')
            except Exception as e:
                print(f"⚠️ Jupiter Error: {e}")
                return None