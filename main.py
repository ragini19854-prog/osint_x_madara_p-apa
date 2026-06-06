import logging
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your actual Telegram Bot Token from @BotFather
BOT_TOKEN = "8749470838:AAH4po84TjIc8-D776KRpq1H_mEabt_QnCs"
API_URL = "https://devilsofheaven-tgnum.vercel.app//api/tg-phone?key=onlyformadara&query="

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Welcome! Send me any number/query, and I will fetch the indian number details for you!"
    )

async def fetch_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches details from the API based on user input."""
    user_query = update.message.text.strip()
    
    # Send a typing placeholder so the user knows the bot is working
    await update.message.reply_chat_action(action="typing")
    
    full_url = f"{API_URL}{user_query}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract fields with fallback defaults if keys are missing
                    mobile = data.get("mobile", "N/A")
                    name = data.get("name", "N/A")
                    father_name = data.get("father_name", "N/A")
                    address = data.get("address", "N/A")
                    alt_mobile = data.get("alt_mobile", "N/A")
                    circle = data.get("circle", "N/A")
                    email = data.get("email", "N/A")
                    
                    # Safety Redaction: Ensure Aadhaar digits are never exposed by the bot
                    aadhaar_display = "[Aadhaar Redacted for Privacy]"
                    
                    # Format the response message exactly as requested
                    response_text = (
                        f"📞 Mobile No     : {mobile}\n"
                        f"👨 Name          : {name}\n"
                        f"👴 Father Name   : {father_name}\n"
                        f"🏠 Address       : {address}\n"
                        f"🖄 Aadhaar ID    : {aadhaar_display}\n"
                        f"📱 Alt Mobile    : {alt_mobile}\n"
                        f"📍 Circle        : {circle}\n"
                        f"📧 Email         : {email}"
                    )
                    
                    await update.message.reply_text(response_text)
                else:
                    await update.message.reply_text("❌ Error: Unable to fetch details from the API.")
                    
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        await update.message.reply_text("⚠️ An error occurred while processing your request.")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    # Responds to any text message that isn't a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fetch_details))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
