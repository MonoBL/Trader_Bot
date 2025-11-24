import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIGURATION ----------------
MODEL_NAME = "models/gemini-2.5-flash"
# -----------------------------------------------

class AIAnalyst:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in .env file!")
        
        genai.configure(api_key=api_key)
        print(f"🧠 AI Analyst initialized using model: {MODEL_NAME}")
        
        self.model = genai.GenerativeModel(
            MODEL_NAME,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.1 
            }
        )

    async def analyze_token(self, token_data, safety_data):
        prompt = f"""
        Act as a professional crypto trading algorithm.
        
        --- INPUT DATA ---
        Token: {token_data.get('symbol')}
        Price: ${token_data.get('price')}
        Mcap: ${token_data.get('market_cap')}
        Liq: ${token_data.get('liquidity')}
        
        Momentum (1h): {token_data.get('price_change_1h')}%
        Momentum (24h): {token_data.get('price_change_24h')}%
        
        Volume: ${token_data.get('volume_24h')}
        Buys: {token_data.get('buy_tx_count')}
        Sells: {token_data.get('sell_tx_count')}
        
        RugCheck Score: {safety_data.get('score')}

        --- STRATEGY RULES ---
        1. FAIL if RugCheck > 55.
        2. FAIL if Liquidity < $3,000.
        3. FAIL if Volume < $10,000.
        4. FAIL if Sells are > 3x Buys.
        
        --- ENTRY LOGIC (Choose A or B) ---
        
        Scenario A: "The Dip Buy"
        - IF 1h Change is NEGATIVE (Pullback) AND 24h Change is POSITIVE (Uptrend).
        - VERDICT: BUY.
        
        Scenario B: "The Momentum Buy"
        - IF 1h Change is POSITIVE (0% to 15%) AND Volume is High.
        - VERDICT: BUY (Riding the trend).
        
        Scenario C: "The FOMO Trap"
        - IF 1h Change is > 30% (Pumped too hard).
        - VERDICT: AVOID (Wait for cooldown).

        Output JSON ONLY:
        {{
            "verdict": "BUY" or "AVOID",
            "confidence": 0-100,
            "risk_level": "LOW", "MEDIUM", or "HIGH",
            "reasoning": "Concise reason."
        }}
        """

        try:
            response = await self.model.generate_content_async(prompt)
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ AI Error ({MODEL_NAME}): {e}")
            return {"verdict": "ERROR", "confidence": 0, "reasoning": "AI Unreachable"}