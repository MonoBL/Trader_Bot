import aiohttp
import json
import time

class DataEngine:
    def __init__(self):
        self.dex_api = "https://api.dexscreener.com/latest/dex/tokens/"
        self.rugcheck_api = "https://api.rugcheck.xyz/v1/tokens/"
        self.jupiter_quote_api = "https://quote-api.jup.ag/v6/quote"
        self.jupiter_swap_api = "https://quote-api.jup.ag/v6/swap"

    async def get_token_data(self, token_address):
        #Will get prces adn liquidity from DexScreener
        async with aiohttp.ClientSession() as session:
            async with session.get(self.dex_api + token_address) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('pairs'):
                        pair= data['pairs'][0]
                        #calculate age or pass 0 but normaly DEXS give a pairCreatedAt
                        create_at= pair.get('pairCreatedAt', time.time()*1000)
                        age_hours= (time.time()*1000 - create_at)/ (1000*3600)
                        return{
                            #Identy
                            "name": pair['baseToken']['name'],
                            "symbol": pair['baseToken']['symbol'],
                            "pairAddress": pair['pairAddress'],

                            #Market Stats
                            "price": pair['priceUsd'],
                            "liquidity": pair['liquidity']['usd'],
                            "volume_24h": pair['volume']['h24'],
                            "fdv": pair.get('fdv', 0),
                            "market_cap": pair.get('marketCap', 0),

                            #Activity
                            "age_hours": round(age_hours, 1),
                            "buy_tx_count": pair['txns']['h24']['buys'],
                            "sell_tx_count": pair['txns']['h24']['buys'],

                            #price changes
                            "price_change_1h": pair['priceChange']['h1'],
                            "price_change_24h": pair['priceChange']['h24'],

                            #Holders
                            "top_10_percentage": 0 
                            #Dex doesnt always give holders %
                            #Asuume 0 or get info from Solscan
                        }
        return None
    
    async def check_safety(self, token_address):
        #Check the token on RugCheck
        async with aiohttp.ClientSession() as session:
            async  with session.get(f"{self.rugcheck_api}{token_address}/report") as response:
                if response.status == 200:
                    data = await response.json()
                    score = data.get('score', 0)

                    #Simple logic if risks is find
                    risks = [risk['name'] for risk in data.get('risks', [])]
                    return{"score": score, "risks": risks}
        return {"score": "Unknown", "risks":[]}
    
    async def get_swap_transaction(self, user_pubkey, input_mint, output_mint, amount_lamports):
        #Get Jupiter Transaction
        #1 Get Quote
        params ={
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount_lamports,
            "slippageBps": 100 #1% slipage
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self.jupiter_quote_api, params=params) as response:
                quote_data = await response.json()


            # 2 Get Swap Tx
            payload = {
                "quoteResponse": quote_data,
                "userPublicKey": user_pubkey,
                "wrapAndUnwrapSol": True
            }    
            async with session.post(self.jupiter_swap_api, json=payload) as response:
                swap_data = await response.json()
                return swap_data.get('swapTransaction')