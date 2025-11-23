#Wallet manager, will create and manage wallet
import os
from dotenv import load_dotenv
from solders.keypair import Keypair as SolanaKeypair
import base58

load_dotenv()

class WalletManager:
    def __init__(self):
        self.keypair = self._load_or_create_wallet()
    
    def _load_or_create_wallet(self):
        #try to load from .env
        pk_str = os.getenv("PRIVATE_KEY_BASE58")

        if pk_str:
            try:
                #load existing wallet
                loaded_keypair = SolanaKeypair.from_base58_string(pk_str)
                print(f"✅ Wallet loaded: {loaded_keypair.pubkey()}")
                return loaded_keypair
            except Exception as e:
                print(f"❌ Error loading key: {e}")

        # IF no key existing create a wallet
        print("⚠️ No wallet found in .env. Generating a new one")

        new_keypair = SolanaKeypair()

        secret_string= base58.b58encode(bytes(new_keypair)).decode('utf-8')

        print(f"\n!!! SAVE THIS TO YOUR .env FILE !!!")
        print(f"PRIVATE_KEY_BASE58= {secret_string}")
        print(f"Public Key (Send SOL here): {new_keypair.pubkey()}\n")

        return new_keypair
    
    def get_public_key(self):
        return str(self.keypair.pubkey())
    
    def get_keypair(self):
        return self.keypair