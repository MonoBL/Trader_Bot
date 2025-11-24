import aiohttp
import asyncio
from data_engine import DataEngine

class Hunter:
    def __init__(self, ai_analyst):
        self.coingecko_api = "https://api.coingecko.com/api/v3/search/trending"
        # Search specifically for "pump" to find Pump.fun tokens
        self.pump_search_api = "https://api.dexscreener.com/latest/dex/search?q=pump" 
        self.dex_search_api = "https://api.dexscreener.com/latest/dex/search?q=solana"
        self.data_engine = DataEngine()
        self.ai = ai_analyst

    async def get_trending_coingecko(self):
        """Plan A: Check Global Trending list"""
        print("🕵️ Checking CoinGecko Trending...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.coingecko_api) as response:
                    if response.status != 200: return []
                    data = await response.json()
            
            candidates = []
            for coin in data.get('coins', []):
                item = coin['item']
                slug = item.get('slug', '').lower()
                if 'solana' in slug or 'sol' in slug:
                    candidates.append({"address": None, "symbol": item['symbol'], "source": "CoinGecko"})
            return candidates
        except Exception:
            return []

    async def get_pump_fun_targets(self):
        """Plan C: Scan specifically for Pump.fun tokens"""
        print("💊 Scanning Pump.fun ecosystem...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.pump_search_api) as response:
                    if response.status != 200: return []
                    data = await response.json()
            
            candidates = []
            pairs = data.get('pairs', [])
            
            # Sort by Volume to find the ones moving NOW
            pairs.sort(key=lambda x: x.get('volume', {}).get('h24', 0), reverse=True)

            for pair in pairs:
                if pair.get('chainId') == 'solana':
                    # Pump.fun criteria:
                    # Lower Liquidity is okay ($1k+) because they are new
                    # High Volume is a MUST ($10k+)
                    liq = pair.get('liquidity', {}).get('usd', 0)
                    vol = pair.get('volume', {}).get('h24', 0)
                    
                    if liq > 1000 and vol > 10000:
                        candidates.append({
                            "address": pair['baseToken']['address'], 
                            "source": "Pump.fun 💊"
                        })
                        
                if len(candidates) >= 5: break 
            return candidates
        except Exception as e:
            print(f"Pump Scan Error: {e}")
            return []

    async def get_trending_dexscreener(self):
        """Plan B: General Solana High Volume"""
        print("🌊 Checking Solana High Volume...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.dex_search_api) as response:
                    if response.status != 200: return []
                    data = await response.json()
            
            candidates = []
            pairs = data.get('pairs', [])
            pairs.sort(key=lambda x: x.get('volume', {}).get('h24', 0), reverse=True)

            for pair in pairs:
                if pair.get('chainId') == 'solana':
                    liq = pair.get('liquidity', {}).get('usd', 0)
                    vol = pair.get('volume', {}).get('h24', 0)
                    
                    # Standard criteria
                    if liq > 10000 and vol > 50000:
                        if pair['baseToken']['symbol'] != 'SOL':
                            candidates.append({
                                "address": pair['baseToken']['address'], 
                                "source": "DexScreener 🌊"
                            })
                            
                if len(candidates) >= 5: break
            return candidates
        except Exception:
            return []

    async def hunt(self):
        """The Main Function"""
        
        # 1. Gather candidates from all sources
        cg_candidates = await self.get_trending_coingecko() # Usually empty for SOL
        pump_candidates = await self.get_pump_fun_targets() # The Degen plays
        dex_candidates = await self.get_trending_dexscreener() # The Safe plays
        
        # Combine them (Prioritize Pump > Dex > CG)
        all_candidates = pump_candidates + dex_candidates
        
        # Remove duplicates based on address
        unique_candidates = []
        seen_addresses = set()
        for item in all_candidates:
            if item['address'] not in seen_addresses:
                unique_candidates.append(item)
                seen_addresses.add(item['address'])

        if not unique_candidates:
            return "❌ **Market is frozen.** No coins found matching criteria."

        # 2. Analyze
        print(f"🔎 Analyzing {len(unique_candidates)} potential gems...")
        valid_coins = []
        
        for item in unique_candidates[:5]: # Limit to 5
            address = item['address']
            
            # Get Data
            token_data = await self.data_engine.get_token_data(address)
            if not token_data: continue
            
            # Check Safety
            safety_data = await self.data_engine.check_safety(address)
            
            # Filter: 
            # If it's Pump.fun, we allow riskier scores (up to 60)
            # If it's Standard, we want safer scores (< 50)
            max_risk = 60 if "Pump" in item['source'] else 50
            
            if safety_data['score'] < max_risk:
                valid_coins.append({
                    "data": token_data, 
                    "safety": safety_data,
                    "source": item['source']
                })

        if not valid_coins:
            return "⚠️ Found coins, but they were all flagged as **Too Dangerous**."

        # 3. Generate Report
        report = "🕵️ **Daily Gem Report**\n\n"
        
        for coin in valid_coins:
            analysis = await self.ai.analyze_token(coin['data'], coin['safety'])
            verdict = "🟢" if analysis['verdict'] == "BUY" else "🔴"
            
            report += (
                f"🪙 **{coin['data']['name']}**\n"
                f"🏷️ Source: {coin['source']}\n"
                f"💰 Price: ${coin['data']['price']} | Vol: ${coin['data']['volume_24h']:,.0f}\n"
                f"🛡️ Risk: {coin['safety']['score']}/100\n"
                f"{verdict} AI: {analysis['reasoning']}\n"
                f"`{coin['data']['address']}`\n\n" 
            )
            
        return report