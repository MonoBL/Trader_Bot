import json
import os
import time

class TradeTracker:
    def __init__(self, filename="positions.json"):
        self.filename = filename
        self.positions =self._load_positions()
    
    def _load_positions(self):
        if not os.path.exists(self.filename):
            if not os.path.exists(self.filename):
                return{}
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return{}
            
    def save_positions(self):
        with open(self.filename, 'w') as f:
            json.dump(self.positions, f, indent=4)

    def add_position(self, token_address, symbol, entry_price, amount_tokens):
        self.positions[token_address]={
            "symbol": symbol,
            "entry_price": float(entry_price),
            "amount_tokens": int(amount_tokens), #in lamports
            "timestamp": time.time(),
            "status":"OPEN"
        }
        self.save_positions()
        print(f"📝 Position added: {symbol}")

    def remove_position(self, token_address):
        if token_address in self.positions:
            del self.positions[token_address]
            self.save_positions()
            print(f"🗑️ Position removed: {token_address}")

    def get_open_positions(self):
        return self.positions