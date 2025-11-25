import asyncio
import logging
from solana.rpc.async_api import AsyncClient
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned
import base64

#Settings
BUY_AMOUNT_SOL = 0.02 
TAKE_PROFIT_PCT= 30 #+30%
STOP_LOSS_PCT = 15 #-15%
SOL_MINT= "So11111111111111111111111111111111111111112"

class AutoTrader:
    def __init__(self, wallet, data_engine, hunter, tracker, bot_app):
        self.wallet= wallet
        self.data= data_engine
        self.hunter= hunter
        self.tracker= tracker
        self.bot = bot_app #Telegram app to send alerts
        self.is_running= False
        self.chat_id= None # we need to know where to send alerts

    async def start(self, chat_id):
        self.is_running = True
        self.chat_id= chat_id
        #start both loops
        asyncio.create_task(self.hunting_loop())
        asyncio.create_task(self.management_loop())
        return "✅ **Auto-Trading Started!**\nI will scan for gems and manage positions."

    async def stop(self):
        self.is_running= False
        return  "🛑 **Auto-Trading Stopped.**"

    async def execute_swap(self, input_mint, output_mint, amount, is_buy=True):
        #helper to execute a trade
        try:
            #Get Transaction
            swap_tx= await self.data.get_swap_transaction(
                self.wallet.get_public_key(),
                input_mint,
                output_mint,
                int(amount)
            )
            if not swap_tx: 
                return None
            
            #sign and send
            rpc_client= AsyncClient("https://api.mainnet-beta.solana.com")
            tx_bytes= base64.b64decode(swap_tx)
            tx = VersionedTransaction.from_bytes(tx_bytes)

            keypair= self.wallet.get_keypair()
            message = to_bytes_versioned(tx.message)
            signature= keypair.sign_message(message)
            signed_tx= VersionedTransaction.populate(tx.message, [signature])

            result= await rpc_client.send_transaction(signed_tx)
            await rpc_client.close()
            return str(result.value)
        except Exception as e:
            logging.error(f"Swap Error: {e}")
            return None