import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

#Improt Modules
from wallet import WalletManager
from data_engine import DataEngine
from ai_analyst import AIAnalyst

#Setup And Configs
load_dotenv()

#Configure Logging, check errors on terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

#start our classes
wallet= WalletManager()
data_engine= DataEngine()
ai_brain= AIAnalyst()

#Constants
SOL_MINT = "So11111111111111111111111111111111111111112"
DEXSCREENER_BASE_URL = "https://dexscreener.com/solana/"

#get solana balance on the wallet
async def get_solana_balance(address_str):
    #Connect to the rpc and check the  balance 
    try:
        #connect to the rpc
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            #conver string addres to pubkey
            pubkey= Pubkey.from_string(address_str)
            #fetch balance (return on lamports)
            response= await client.get_balance(pubkey)
            # 1 SOL = 1,000,000,000 Lamports
            balance_sol = response.value/ 1_000_000_000
            return balance_sol
    except Exception as e:
        logging.error(f"Error fetching balance: {e}")
        return 0.0


#telegram command handlers
async def start(update:Update, context: ContextTypes.DEFAULT_TYPE):
    #Welcome message when user /start
    pubkey = wallet.get_public_key()
    balance = 0 #Will add a get_balance later on wallet.py
    await update.message.reply_text(
        f"🤖 **AI Sniper Bot Online**\n\n"
        f"💳 **Wallet:** `{pubkey}`\n"
        f"⚠️ **Balance:** Check Solscan (Send SOL here to trade)\n\n"
        f"🚀 **How to use:**\n"
        f"Just paste a Token Address (CA) to scan and trade.",
        parse_mode=ParseMode.MARKDOWN
    )

async def analyze_token_logic(chat_id, token_address, context, message_id_to_edit=None):
    """
    Core logic to fetch data -> analyze -> show results.
    Used by both new messages and the 'Refresh' button.
    """
    if message_id_to_edit:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id_to_edit,
            text=f"🔄 Refreshing data for {token_address}..."
        )
    else:
        msg= await context.bot.send_message(chat_id=chat_id, text=f"🔍 Scanning {token_address}...")
        message_id_to_edit = msg.message_id

    #fetch data (DexScreener)
    token_data= await data_engine.get_token_data(token_address)
    if not token_data:
        await context.bot.id_message_text(
            chat_id=chat_id,
            message_id=message_id_to_edit,
            text="❌ **Error:** Token not found on DexScreener."
        )
        return
    
    #Check Safety
    safety_data = await data_engine.check_safety(token_address)

    #Analysis (gemini) update status user
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id_to_edit,
        text=f"🧠 AI is analyzing {token_data['symbol']}..."
    )

    ai_result= await ai_brain.analyze_token(token_data, safety_data)

    #Format Output msg, Determine emojis based on data

    verdict_emoji= "🟢" if ai_result['verdict'] == "BUY" else "🔴"
    risk_emoji = "🛡️" if ai_result.get('risk_level') == "LOW" else "⚠️"

    #format numbers for readability
    mcap_formatted = f"${token_data['market_cap']:,.0f}"
    liq_formatted= f"${token_data['liquidity']:,.0f}"

    message_text = (
        f"🪙 **{token_data['name']} ({token_data['symbol']})**\n"
        f"`{token_address}`\n\n"

        f"📊 **Market Data**\n"
        f"• Price: ${token_data['price']}\n"
        f"• Mcap: {mcap_formatted} | Liq: {liq_formatted}\n"
        f"• Age: {token_data['age_hours']}h\n"
        f"• 1h Change: {token_data['price_change_1h']}%\n\n"

        f" {verdict_emoji} **Ai Verdict: {ai_result['verdict']}**({ai_result['confidence']}%)\n"
        f"{risk_emoji} **Risk Level:** {ai_result.get('risk_level', 'UNKNOWN')}\n"
        f"📝 **Reason:** {ai_result['reasoning']}\n"
    )

    #Create Buttons 
    #embed the token address in the callback data so the button knows what to buy
    keyboard = [
        [
            InlineKeyboardButton("Buy 0,1 SOL", callback_data=f"buy_0.1_{token_address}"),
            InlineKeyboardButton("Buy 0.5 SOL", callback_data=f"buy_0.5_{token_address}"),
            InlineKeyboardButton("Buy 1.0 SOL", callback_data=f"buy_1.0_{token_address}"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_0_{token_address}"),
            InlineKeyboardButton("📈 Chart", url=f"{DEXSCREENER_BASE_URL}{token_data['pairAddress']}")
        ]
    ]
    reply_markup= InlineKeyboardMarkup(keyboard)

    #Send/edit Final Msg
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id_to_edit,
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detects when user pastes a CA"""
    # Check if message has text (it might be a photo or sticker)
    if not update.message or not update.message.text:
        print("⚠️ Received a message without text.")
        return

    text = update.message.text.strip()
    chat_id = update.message.chat_id
    
    # --- DEBUG PRINTS (This will show in your terminal) ---
    print(f"📩 Received Message: '{text}'")
    print(f"📏 Length: {len(text)}")
    # -----------------------------------------------------

    # Simple filter: Solana addresses are usually 32-44 chars long
    if 30 < len(text) < 50 and " " not in text:
        print("✅ Valid Address format detected! Starting analysis...")
        await analyze_token_logic(chat_id, text, context)
    else:
        print("❌ Message ignored: Too short, too long, or contains spaces.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #Handles button clicks
    query = update.callback_query
    await query.answer() # Acknowledge click to stop loading animation

    data= query.data

    #wallet refresh
    if data == "check_wallet":
        user_address = wallet.get_public_key()
        balance = await get_solana_balance(user_address)

        text = (
            f"💳 **Your Wallet**\n"
            f"`{user_address}`\n\n"
            f"💰 **SOL Balance:** {balance:.4f} SOL\n"
            f"🔗 [View Holdings on Solscan](https://solscan.io/account/{user_address}#portfolio)"
        )

        #keep the refresh button there
        keyboard= [[InlineKeyboardButton("🔄 Refresh Balance", callback_data="check_wallet")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text, 
            parse_mode=ParseMode.MARKDOWN, 
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        return



    action, value, token_address = data.split('_')

    if action == "refresh":
        await analyze_token_logic(query.message.chat_id, token_address, context, message_id_to_edit=query.message.message_id)

    elif action == "buy":
        amount_sol= float(value)
        await query.message.reply_text(f"⏳ **Initiating Trade:** {amount_sol} SOL -> {token_address}...")

        try:
            #Convert Sol do Lamports
            lamports= int(amount_sol *1_000_000_000)

            #get Tx from jupidet
            swap_tx_base64= await data_engine.get_swap_transaction(
                wallet.get_public_key(),
                SOL_MINT, 
                token_address, 
                lamports
            )
            
            if not swap_tx_base64:
                await query.message.reply_text("❌ **Error:** Failed to get quote from Jupiter. Slippage might be too low.")
                return
            
            #Sign and send 
            #Improt here fo keep clean 
            from solana.rpc.async_api import AsyncClient
            from solders.transaction import VersionedTransaction
            from solders.message import to_bytes_versioned
            import base64

            #use public RPC 
            rpc_client = AsyncClient("https://api.mainnet-beta.solana.com")

            #desserializar convert 
            tx_bytes= base64.b64decode(swap_tx_base64)
            tx= VersionedTransaction.from_bytes(tx_bytes)

            #sign
            keypair= wallet.get_keypair()
            message= to_bytes_versioned(tx.message)
            signature= keypair.sign_message(message)
            signet_tx = VersionedTransaction.populate(tx.message, [signature])

            #send
            result = await rpc_client.send_transaction(signet_tx)
            await rpc_client.close()

            tx_sig= str(result.value)

            #Success Message
            await query.message.reply_text(
                f"✅ **Trade Sent!**\n"
                f"🔗 [View on Solscan](https://solscan.io/tx/{tx_sig})",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"Trade failed: {e}")
            await query.message.reply_text(f"❌ **Trade Failed:** {str(e)}")

async def wallet_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #Show wallet details and balance
    user_address = wallet.get_public_key()

    msg = await update.message.reply_text("🏦 Fetching wallet data...")

    #get real balance
    balance = await get_solana_balance(user_address)

    #format msg
    text=(
        f"💳 **Your Wallet**\n"
        f"`{user_address}`\n\n"
        f"💰 **SOL Balance:** {balance:.4f} SOL\n"
        f"💵 **USD Value:** ${balance * 245:.2f} (Approx)\n\n" # You can fetch real SOL price later if you want
        f"🔗 [View Holdings on Solscan](https://solscan.io/account/{user_address}#portfolio)"
    )

    #add button to refresh 
    keyboard= [[InlineKeyboardButton("🔄 Refresh Balance", callback_data="check_wallet")]]  
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=msg.message_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

#main entry point
if __name__ == '__main__':
    #check for token
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_TOKEN not found in .env")
        exit(1)
    
    #Build app
    app = ApplicationBuilder().token(token).build()

    #add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet_info))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


        