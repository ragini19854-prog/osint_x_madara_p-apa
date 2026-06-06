import logging
import aiohttp
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your actual Telegram Bot Token from @BotFather
BOT_TOKEN = "8749470838:AAH4po84TjIc8-D776KRpq1H_mEabt_QnCs"
API_URL = "http://devilsofheaven-tgnum.vercel.app/api/number?number={}&key=onlyformadara"

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
    
    full_url = API_URL.format(user_query)
    logger.info(f"Fetching from URL: {full_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                logger.info(f"Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"API Response: {data}")
                    
                    # Navigate to the actual results from db2
                    try:
                        db2_data = data.get('result', {}).get('db2', {})
                        
                        if db2_data.get('success') and db2_data.get('data', {}).get('results'):
                            result_data = db2_data['data']['results'][0]
                            
                            # Extract fields with correct names
                            mobile = result_data.get('mobile', 'N/A')
                            name = result_data.get('name', 'N/A')
                            father_name = result_data.get('fname', 'N/A')
                            address = result_data.get('address', 'N/A')
                            alt_mobile = result_data.get('alt') or 'N/A'
                            circle = result_data.get('circle', 'N/A')
                            email = result_data.get('email') or 'N/A'
                            aadhaar = result_data.get('id', 'N/A')
                            
                            # Safety Redaction: Ensure Aadhaar digits are never exposed by the bot
                            aadhaar_display = "[Aadhaar Redacted for Privacy]" if aadhaar != "N/A" else "N/A"
                            
                            # Format the response message
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
                            await update.message.reply_text("❌ No data found for this number")
                    except (KeyError, IndexError) as e:
                        logger.error(f"Error parsing response: {e}")
                        await update.message.reply_text("❌ Error parsing API response")
                else:
                    error_text = await response.text()
                    logger.error(f"API Error {response.status}: {error_text}")
                    await update.message.reply_text(f"❌ Error: API returned status {response.status}")
                    
    except asyncio.TimeoutError:
        logger.error("API request timed out")
        await update.message.reply_text("⏱️ Request timed out. Please try again.")
    except Exception as e:
        logger.error(f"Error fetching data: {e}", exc_info=True)
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
