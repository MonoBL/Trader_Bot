import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "models/gemini-2.5-flash"

class AIAnalyst:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌Error Gemini API Key not foundd in the env")

        genai.configure(api_key=api_key)
        print(f"🧠 AI Analyst initialized using model: {MODEL_NAME.removeprefix("models/")}")

        self.model = genai.GenerativeModel(
            MODEL_NAME,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.1 #lower less creative more logical
            }
        )

    async def analyze_token(self, token_data, safety_data):
        prompt= f"""
        Act as a conservative, algorithmic crypto risk analyst. 
        Your job is to filter out scams and identify high-probability entries.

       --- INPUT DATA ---
        Token: {token_data.get('symbol')}
        Age: {token_data.get('age_hours')} hours
        
        Price: ${token_data.get('price')}
        Market Cap: ${token_data.get('market_cap')}
        Liquidity: ${token_data.get('liquidity')}
        FDV: ${token_data.get('fdv')}
        
        Momentum (1h): {token_data.get('price_change_1h')}%
        Momentum (24h): {token_data.get('price_change_24h')}%
        
        Activity (24h):
        - Volume: ${token_data.get('volume_24h')}
        - Buys: {token_data.get('buy_tx_count')}
        - Sells: {token_data.get('sell_tx_count')}

        --- RISK REPORT ---
        RugCheck Score: {safety_data.get('score')} (0=safe, 100=danger)
        Risks: {', '.join(safety_data.get('risks', []))}

        
        --- STRATEGY RULES (STRICT) ---
        Output "AVOID" if ANY of these are true:
        1. RugCheck Score > 40.
        2. Liquidity is less than $3,000.
        3. Market Cap is > 20x Liquidity (Fake valuation / Thin liquidity).
        4. Volume (24h) is < 10% of Market Cap (Dead coin).
        5. Price Change (1h) is > 200% (Chasing a pump / High risk of pullback).
        6. Sells are 2x higher than Buys (Heavy dumping).


        --- ENTRY LOGIC (If no Strategy Fails) ---
        If it passes the filters above, check for "BUY" signal:
        - Ideal Entry: Price Change (1h) is slightly negative (pullback) while (24h) is positive (uptrend).
        - Volume Check: High volume relative to Liquidity is good.
        
        Analyze for a "BUY" verdict based on:
        1. Momentum: Are Buys > Sells?
        2. Liquidity Ratio: Is Liquidity at least 10% of FDV? (Healthy backing).
        3. Age Context: 
        - If Age < 24h: Require higher volume and strict safety.
        - If Age > 24h: Look for price stability and consistent volume.

        --- OUTPUT FORMAT ---
        Return ONLY this JSON object:
        {{
            "verdict": "BUY" or "AVOID",
            "confidence": 0-100,
            "risk_level": "LOW", "MEDIUM", or "HIGH",
            "reasoning": "One concise sentence explaining the decision."
        }}
        """

        try:
            response= await self.model.generate_content_async(prompt)
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ AI Error ({MODEL_NAME}): {e} ")
            return {"verdict": "ERROR", "confidence": 0, "reasoning": "AI Unreachable"}