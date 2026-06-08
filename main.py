import logging
import aiohttp
import asyncio
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# =================== CHANNEL VERIFICATION SETUP ===================
# To find your channel ID:
# 1. If channel has a username (e.g., @mychannel), use: "@mychannel"
# 2. If channel is private, forward a message from it to @JsonDumpBot
#    or use the bot command /channelid in your channel
#    The ID will look like: -1001234567890 (always starts with -100)
# 3. Your channel join link: https://t.me/+1NRRqUd1replNTM1
# ==================================================================

# Owner ID
OWNER_ID = 8441236350

# Database initialization
def init_database():
    """Initialize SQLite database for storing search history and premium system"""
    conn = sqlite3.connect('phone_lookup_history.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone_number TEXT,
            name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_premium (
            user_id INTEGER PRIMARY KEY,
            daily_searches INTEGER DEFAULT 0,
            credits INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            last_reset DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS protected_numbers (
            phone_number TEXT PRIMARY KEY,
            protected_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_database(user_id, phone_number, name):
    """Save search to database"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO search_history (user_id, phone_number, name) VALUES (?, ?, ?)',
                      (user_id, phone_number, name))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def get_search_history(user_id, limit=5):
    """Get recent searches for a user"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT phone_number, name, timestamp FROM search_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
                      (user_id, limit))
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

# =================== PREMIUM SYSTEM FUNCTIONS ===================

def init_user_premium(user_id):
    """Initialize user in premium system"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO user_premium (user_id, referral_code) VALUES (?, ?)',
                      (user_id, f"REF_{user_id}"))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def get_daily_searches(user_id):
    """Get daily searches count for user"""
    try:
        init_user_premium(user_id)
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT daily_searches, last_reset FROM user_premium WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            daily_searches, last_reset = result
            # Reset daily searches at midnight
            last_reset_date = datetime.fromisoformat(last_reset).date()
            today = datetime.now().date()
            
            if last_reset_date != today:
                reset_daily_searches(user_id)
                return 0
            return daily_searches
        return 0
    except Exception as e:
        logger.error(f"Database error: {e}")
        return 0

def reset_daily_searches(user_id):
    """Reset daily searches at midnight"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE user_premium SET daily_searches = 0, last_reset = ? WHERE user_id = ?',
                      (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def increment_daily_searches(user_id):
    """Increment daily searches count"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE user_premium SET daily_searches = daily_searches + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def get_credits(user_id):
    """Get user credits"""
    try:
        init_user_premium(user_id)
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT credits FROM user_premium WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Database error: {e}")
        return 0

def add_credits(user_id, amount):
    """Add credits to user"""
    try:
        init_user_premium(user_id)
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE user_premium SET credits = credits + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def use_credit(user_id):
    """Use one credit"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE user_premium SET credits = credits - 1 WHERE user_id = ? AND credits > 0', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

def get_referral_code(user_id):
    """Get user's referral code"""
    try:
        init_user_premium(user_id)
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT referral_code FROM user_premium WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else f"REF_{user_id}"
    except Exception as e:
        logger.error(f"Database error: {e}")
        return f"REF_{user_id}"

def is_number_protected(phone_number):
    """Check if a number is protected"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM protected_numbers WHERE phone_number = ?', (phone_number,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

def protect_number(phone_number):
    """Add a number to protected list"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO protected_numbers (phone_number) VALUES (?)', (phone_number,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

def unprotect_number(phone_number):
    """Remove a number from protected list"""
    try:
        conn = sqlite3.connect('phone_lookup_history.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM protected_numbers WHERE phone_number = ?', (phone_number,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

# Replace with your actual Telegram Bot Token from @BotFather
BOT_TOKEN = "8749470838:AAH4po84TjIc8-D776KRpq1H_mEabt_QnCs"
API_URL = "http://devilsofheaven-tgnum.vercel.app/api/number?number={}&key=onlyformadara"

# Channel join verification settings
REQUIRED_CHANNEL = "-1003439670516"  # Replace with actual channel ID or use @channel_username
CHANNEL_JOIN_LINK = "https://t.me/+1NRRqUd1replNTM1"

async def is_member_of_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int, channel_id: str) -> bool:
    """Check if user is a member of the required channel"""
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        # Check if user is member, administrator, or creator
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

async def verify_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verify user is a member of required channel, send prompt if not"""
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    is_member = await is_member_of_channel(context, user_id, REQUIRED_CHANNEL)
    
    if not is_member:
        keyboard = [
            [InlineKeyboardButton("✅ Join Channel", url=CHANNEL_JOIN_LINK)],
            [InlineKeyboardButton("✔️ I've Joined, Verify Me", callback_data="verify_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "<blockquote><b>⛔ CHANNEL VERIFICATION REQUIRED</b>\n\n"
            "You must join our channel first to use this bot!\n\n"
            "<b>📢 Join Channel:</b>\n"
            f"<a href='{CHANNEL_JOIN_LINK}'>Click here to join</a>\n\n"
            "After joining, click the button below to verify your membership.\n\n"
            "<i>⏱️ This is a quick verification process</i></blockquote>"
        )
        
        if update.message:
            await update.message.reply_text(message_text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(message_text, parse_mode="HTML", reply_markup=reply_markup)
        
        return False
    
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    # Verify channel membership first
    if not await verify_channel_membership(update, context):
        return
    
    user_id = update.message.from_user.id
    init_user_premium(user_id)
    
    # --- START ANIMATION ---
    loading_1 = await update.message.reply_text("<b>⏳</b>", parse_mode="HTML")
    
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ʜʟᴏ ʙᴀʙʏ.❤️‍🔥</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ʜʟᴏ ʙᴀʙʏ..❤️‍🔥</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ʜʟᴏ ʙᴀʙʏ...❤️‍🔥</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ᴏsɪɴᴛ</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ᴏsɪɴᴛ ꭙ</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>ᴏsɪɴᴛ ꭙ ϻᴀᴅᴀʀᴀ ♪</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.edit_text("<b>sᴛᴧʀᴛed!🥀</b>", parse_mode="HTML")
    await asyncio.sleep(0.1)
    await loading_1.delete()
    # --- ANIMATION END ---
    
    # Get user stats
    daily_searches = get_daily_searches(user_id)
    credits = get_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🕵️‍♂️ 𝔑𝔲𝔪𝔟𝔢𝔯 𝔖𝔢𝔞𝔯𝔠𝔥 🔍", callback_data="start_search", style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton("👨‍💻 𝔇𝔢𝔳𝔢𝔩𝔬𝔭𝔢𝔯", url="tg://user?id=8441236350", style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("✨ 𝔐𝔶 ℌ𝔬𝔪𝔢", url="https://t.me/+1NRRqUd1replNTM1", style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("🛡️ 𝔓𝔯𝔬𝔱𝔢𝔠𝔱 𝔜𝔬𝔲𝔯 𝔑𝔲𝔪𝔟𝔢𝔯 🔒", callback_data="protect_number_btn", style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton("💳 𝔊𝔢𝔱 ℭ𝔯𝔢𝔡𝔦𝔱𝔰", callback_data="get_credits_paid", style=enums.ButtonStyle.PRIMARY)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Single message with image and caption with 3-part blockquote
    caption = (
        "<blockquote><b>🌟 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴍᴀᴅᴀʀᴀ x ᴏsɪɴᴛ ᴘʜᴏɴᴇ ʟᴏᴏᴋᴜᴘ ʙᴏᴛ 🌟</b>\n\n"
        "<b>📱 ᴀʙᴏᴜᴛ ᴛʜɪꜱ ʙᴏᴛ:</b>\n"
        "📞 ɢᴇᴛ ᴅᴇᴛᴀɪʟᴇᴅ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ ᴀʙᴏᴜᴛ ᴀɴʏ ɪɴᴅɪᴀɴ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ɪɴ ꜱᴇᴄᴏɴᴅꜱ!\n\n"
        "<b>💡 ʜᴏᴡ ᴛᴏ ᴜꜱᴇ::</b>\n"
        "ᴊᴜꜱᴛ ꜱᴇɴᴅ ᴍᴇ ᴀ <b>10-ᴅɪɢɪᴛ ɪɴᴅɪᴀɴ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ</b>\n"
        "📱 ᴇxᴀᴍᴘʟᴇ: 9876543210</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>⚠️ ɪᴍᴘᴏʀᴛᴀɴᴛ ɴᴏᴛɪᴄᴇ:</b>\n\n"
        "• <i> ᴡᴇ ᴅᴏ ɴᴏᴛ ꜱᴜᴘᴘᴏʀᴛ ᴏʀ ᴘʀᴏᴍᴏᴛᴇ ᴀɴʏ ɪʟʟᴇɢᴀʟ ᴀᴄᴛɪᴠɪᴛɪᴇꜱ.</i>\n"
        "• ᴀʟʟ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ ɪꜱ ʙᴀꜱᴇᴅ ᴏɴ ᴘᴜʙʟɪᴄʟʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴅᴀᴛᴀ.\n"
        "• <i>ʏᴏᴜ ᴀʀᴇ ꜱᴏʟᴇʟʏ ʀᴇꜱᴘᴏɴꜱɪʙʟᴇ ꜰᴏʀ ʜᴏᴡ ʏᴏᴜ ᴜꜱᴇ ᴀɴʏ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ.</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>📊 Your Stats:</b>\n"
        f"Daily Searches: {daily_searches}/2\n"
        f"Credits: {credits}\n\n"
        f"<b>⚡ ᴅᴇᴠᴇʟᴏᴘᴇᴅ & ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴍᴀᴅᴀʀᴀ</b>\n\n"
        "<i>Ready to lookup any phone number?</i></blockquote>"
    )
    
    await update.message.reply_photo(
        photo="https://i.ibb.co/rG4TWrGg/image.jpg",
        caption=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
        has_spoiler=True
    )

async def fetch_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches details from the API based on user input."""
    user_query = update.message.text.strip()
    user_id = update.message.from_user.id
    
    # =================== HANDLE PROTECT NUMBER REQUEST ===================
    if context.user_data.get('waiting_for_protect'):
        context.user_data['waiting_for_protect'] = False
        
        # Validate input is a 10-digit number
        if not user_query.isdigit() or len(user_query) != 10:
            await update.message.reply_text(
                "❌ <b>Invalid Input</b>\n\n"
                "Please enter a valid <b>10-digit Indian phone number</b>\n"
                "You entered: <code>{}</code> ({} digits)".format(user_query, len(user_query)),
                parse_mode="HTML"
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("🛡️ 𝔓𝔯𝔬𝔱𝔢𝔠𝔱 𝔜𝔬𝔲𝔯 𝔑𝔲𝔪𝔟𝔢𝔯 🔒", callback_data="protect_number_btn")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"<blockquote><b>🔒 PROTECT NUMBER REQUEST</b>\n\n"
            f"Phone: <code>{user_query}</code>\n\n"
            f"This will protect your number's details from being visible to bot users.\n\n"
            f"To complete this request, contact:\n"
            f"@MADARA_X_HELPER_bot\n\n"
            f"Click the button to confirm:</blockquote>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return
    
    # =======================================================================
    
    # Verify channel membership first
    if not await verify_channel_membership(update, context):
        return
    
    # Check if we're waiting for a number from the button click
    if context.user_data.get('waiting_for_number'):
        context.user_data['waiting_for_number'] = False
        
        # Validate input is a 10-digit number
        if not user_query.isdigit() or len(user_query) != 10:
            await update.message.reply_text(
                "❌ <b>Invalid Input</b>\n\n"
                "Please enter a valid <b>10-digit Indian phone number</b>\n"
                "You entered: <code>{}</code> ({} digits)\n\n"
                "Try again: 9876543210".format(user_query, len(user_query)),
                parse_mode="HTML"
            )
            return
    
    # =================== PREMIUM SYSTEM CHECK ===================
    # Owner has unlimited searches
    if user_id != OWNER_ID:
        daily_searches = get_daily_searches(user_id)
        credits = get_credits(user_id)
        
        # Check if user has exhausted free searches and has no credits
        if daily_searches >= 2 and credits <= 0:
            referral_code = get_referral_code(user_id)
            keyboard = [
                [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")],
                [InlineKeyboardButton("💳 Get Paid Credits", callback_data="get_credits_paid")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "<blockquote><b>⛔ SEARCH LIMIT REACHED</b>\n\n"
                f"You have used your <b>2 free searches today</b>.\n\n"
                "<b>📊 Your Stats:</b>\n"
                f"Daily Searches: {daily_searches}/2\n"
                f"Credits Available: {credits}\n\n"
                "<b>🔗 Get More Searches:</b>\n"
                "1️⃣ Refer friends using your referral link\n"
                "2️⃣ Each successful refer = 1 search\n"
                "3️⃣ Or buy paid credits\n\n"
                f"<b>Your Referral Code:</b> <code>{referral_code}</code>\n\n"
                "<i>Contact for paid credits →</i> @MADARA_X_HELPER_bot</blockquote>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return
        
        # Check if using free search or credit
        if daily_searches < 2:
            increment_daily_searches(user_id)
        elif credits > 0:
            use_credit(user_id)
    
    # =======================================================
    
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
                            # =================== CHECK IF NUMBER IS PROTECTED ===================
                            result_data = db2_data['data']['results'][0]
                            mobile = result_data.get('mobile', 'N/A')
                            
                            if is_number_protected(mobile):
                                keyboard = [
                                    [InlineKeyboardButton("🔒 Protect Your Number", callback_data="protect_number_btn")],
                                    [InlineKeyboardButton("🔄 New Search", callback_data="new_search")]
                                ]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                
                                await update.message.reply_text(
                                    "<blockquote><b>🔒 PREMIUM PROTECTED NUMBER</b>\n\n"
                                    "This number is protected by the owner.\n"
                                    "No details available.\n\n"
                                    "If you want to also protect your number:\n"
                                    "Contact: @MADARA_X_HELPER_bot</blockquote>",
                                    parse_mode="HTML",
                                    reply_markup=reply_markup
                                )
                                return
                            
                            # ================================================================
                            
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
                            
                            # Save to database
                            save_to_database(user_id, mobile, name)
                            
                            # Safety Redaction: Ensure Aadhaar digits are never exposed by the bot
                            aadhaar_display = "[Aadhaar Redacted for Privacy]" if aadhaar != "N/A" else "N/A"
                            
                            # Format the response message with blockquote styling
                            response_text = (
                                f"<blockquote><b>✨ PHONE LOOKUP RESULT ✨</b>\n\n"
                                f"📞 <b>Mobile Number:</b>\n<code>{mobile}</code>\n\n"
                                f"👤 <b>Name:</b>\n<i>{name}</i>\n\n"
                                f"👨‍👦 <b>Father's Name:</b>\n<i>{father_name}</i>\n\n"
                                f"🏘️ <b>Address:</b>\n<i>{address}</i>\n\n"
                                f"📍 <b>Circle:</b>\n<code>{circle}</code>\n\n"
                                f"✉️ <b>Email:</b>\n<code>{email}</code>\n\n"
                                f"📱 <b>Alternative Mobile:</b>\n<code>{alt_mobile}</code>\n\n"
                                f"🔐 <b>Aadhaar ID:</b>\n<i>{aadhaar_display}</i>\n\n"
                                f"<b>⚡ POWERED BY MADARA</b></blockquote>"
                            )
                            
                            keyboard = [
                                [InlineKeyboardButton("👨‍💻 𝔇𝔢𝔳𝔢𝔩𝔬𝔭𝔢𝔯", url="tg://user?id=8441236350", style=enums.ButtonStyle.PRIMARY),
                                 InlineKeyboardButton("📖 History", callback_data="view_history")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            message = await update.message.reply_text(response_text, parse_mode="HTML", reply_markup=reply_markup)
                            
                            # Delete message after 45 seconds
                            try:
                                await asyncio.sleep(45)
                                await message.delete()
                            except Exception as e:
                                logger.error(f"Error deleting message: {e}")
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Handle verification button separately (before membership check)
    if query.data == "verify_membership":
        is_member = await is_member_of_channel(context, user_id, REQUIRED_CHANNEL)
        
        if is_member:
            await query.edit_message_text(
                "<blockquote><b>✅ Verification Successful!</b>\n\n"
                "You are now verified as a channel member.\n"
                "You can now use all bot features.\n\n"
                "Send /start to continue.</blockquote>",
                parse_mode="HTML"
            )
        else:
            await query.answer("❌ You are not yet a member of the channel. Please join first!", show_alert=True)
        return
    
    # For all other buttons, verify membership first
    if not await verify_channel_membership(update, context):
        return
    
    if query.data == "start_search":
        context.user_data['waiting_for_number'] = True
        try:
            # Try to edit caption if it's a photo, otherwise edit text
            await query.edit_message_caption(
                caption="📱 <b>Enter Phone Number</b>\n\n"
                "Please send me a <b>10-digit Indian phone number</b>\n\n"
                "<i>Example: 9876543210</i>",
                parse_mode="HTML"
            )
        except:
            await query.edit_message_text(
                "📱 <b>Enter Phone Number</b>\n\n"
                "Please send me a <b>10-digit Indian phone number</b>\n\n"
                "<i>Example: 9876543210</i>",
                parse_mode="HTML"
            )
    
    elif query.data == "view_history":
        history = get_search_history(user_id, limit=10)
        if history:
            history_text = "<b>📖 Your Search History:</b>\n\n"
            for phone, name, timestamp in history:
                history_text += f"📞 <code>{phone}</code> - <i>{name}</i>\n"
            try:
                await query.edit_message_caption(caption=history_text, parse_mode="HTML")
            except:
                await query.edit_message_text(history_text, parse_mode="HTML")
        else:
            try:
                await query.edit_message_caption(caption="📭 No search history yet", parse_mode="HTML")
            except:
                await query.edit_message_text("📭 No search history yet")
    
    elif query.data == "clear_history":
        try:
            conn = sqlite3.connect('phone_lookup_history.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM search_history WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            try:
                await query.edit_message_caption(caption="✅ Search history cleared!", parse_mode="HTML")
            except:
                await query.edit_message_text("✅ Search history cleared!")
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
            try:
                await query.edit_message_caption(caption="❌ Error clearing history", parse_mode="HTML")
            except:
                await query.edit_message_text("❌ Error clearing history")
    
    elif query.data == "new_search":
        context.user_data['waiting_for_number'] = True
        try:
            await query.edit_message_caption(
                caption="📱 <b>Enter Phone Number</b>\n\n"
                "Please send me a <b>10-digit Indian phone number</b>\n\n"
                "<i>Example: 9876543210</i>",
                parse_mode="HTML"
            )
        except:
            await query.edit_message_text(
                "📱 <b>Enter Phone Number</b>\n\n"
                "Please send me a <b>10-digit Indian phone number</b>\n\n"
                "<i>Example: 9876543210</i>",
                parse_mode="HTML"
            )
    
    elif query.data == "protect_number_btn":
        context.user_data['waiting_for_protect'] = True
        try:
            # Try to edit caption if it's a photo message
            await query.edit_message_caption(
                caption="🔒 <b>Protect Your Number</b>\n\n"
                "Please send your <b>10-digit phone number</b> to protect it.\n"
                "Once protected, your details won't be visible to bot users.\n\n"
                "<i>To protect your number contact:</i> @MADARA_X_HELPER_bot",
                parse_mode="HTML"
            )
        except:
            # Fall back to editing text if it's a text message
            await query.edit_message_text(
                "🔒 <b>Protect Your Number</b>\n\n"
                "Please send your <b>10-digit phone number</b> to protect it.\n"
                "Once protected, your details won't be visible to bot users.\n\n"
                "<i>To protect your number contact:</i> @MADARA_X_HELPER_bot",
                parse_mode="HTML"
            )
    
    elif query.data == "get_referral":
        referral_code = get_referral_code(user_id)
        await query.answer(
            f"Your Referral Code: {referral_code}\n\n"
            "Share this with your friends to get 1 search per referral!",
            show_alert=True
        )
    
    elif query.data == "get_credits_paid":
        keyboard = [
            [InlineKeyboardButton("📤 Get Referral Link", callback_data="get_referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Try to edit caption if it's a photo message
            await query.edit_message_caption(
                caption="<blockquote><b>💳 GET MORE CREDITS</b>\n\n"
                "<b>Option 1: Free (Referral)</b>\n"
                "Share your referral code with friends.\n"
                "Each referral = 1 search credit\n\n"
                "<b>Option 2: Paid Credits</b>\n"
                "Get unlimited searches with paid credits.\n\n"
                "<b>Contact for paid credits:</b>\n"
                "@MADARA_X_HELPER_bot\n\n"
                "<i>They will add credits to your account.</i></blockquote>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except:
            # Fall back to editing text if it's a text message
            await query.edit_message_text(
                "<blockquote><b>💳 GET MORE CREDITS</b>\n\n"
                "<b>Option 1: Free (Referral)</b>\n"
                "Share your referral code with friends.\n"
                "Each referral = 1 search credit\n\n"
                "<b>Option 2: Paid Credits</b>\n"
                "Get unlimited searches with paid credits.\n\n"
                "<b>Contact for paid credits:</b>\n"
                "@MADARA_X_HELPER_bot\n\n"
                "<i>They will add credits to your account.</i></blockquote>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    
    # Handle protect confirmation
    elif query.data.startswith("confirm_protect_"):
        phone_number = query.data.replace("confirm_protect_", "")
        protect_number(phone_number)
        try:
            await query.edit_message_caption(
                caption=f"<blockquote><b>✅ PROTECTION REQUEST SENT</b>\n\n"
                f"Phone: <code>{phone_number}</code>\n\n"
                f"Your number protection request has been sent to the admin.\n"
                f"Once approved, this number's details will be protected.\n\n"
                f"You will receive a notification once it's done.\n\n"
                f"Admin Contact: @MADARA_X_HELPER_bot</blockquote>",
                parse_mode="HTML"
            )
        except:
            await query.edit_message_text(
                f"<blockquote><b>✅ PROTECTION REQUEST SENT</b>\n\n"
                f"Phone: <code>{phone_number}</code>\n\n"
                f"Your number protection request has been sent to the admin.\n"
                f"Once approved, this number's details will be protected.\n\n"
                f"You will receive a notification once it's done.\n\n"
                f"Admin Contact: @MADARA_X_HELPER_bot</blockquote>",
                parse_mode="HTML"
            )

async def owner_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle owner commands"""
    user_id = update.message.from_user.id
    
    # Check if user is owner
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use owner commands.")
        return
    
    command = update.message.text.split(None, 1)
    
    if not command:
        return
    
    # /protect <phone_number> - Protect a number
    if command[0] == "/protect":
        if len(command) < 2:
            await update.message.reply_text("Usage: /protect <phone_number>")
            return
        
        phone_number = command[1].strip()
        
        if not phone_number.isdigit() or len(phone_number) != 10:
            await update.message.reply_text("❌ Invalid phone number. Please provide a 10-digit number.")
            return
        
        if protect_number(phone_number):
            await update.message.reply_text(
                f"✅ <b>Number Protected Successfully</b>\n\n"
                f"Phone: <code>{phone_number}</code>\n\n"
                f"This number's details will no longer be visible to users.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ Error protecting number. Please try again.")
    
    # /unprotect <phone_number> - Unprotect a number
    elif command[0] == "/unprotect":
        if len(command) < 2:
            await update.message.reply_text("Usage: /unprotect <phone_number>")
            return
        
        phone_number = command[1].strip()
        
        if not phone_number.isdigit() or len(phone_number) != 10:
            await update.message.reply_text("❌ Invalid phone number. Please provide a 10-digit number.")
            return
        
        if unprotect_number(phone_number):
            await update.message.reply_text(
                f"✅ <b>Protection Removed</b>\n\n"
                f"Phone: <code>{phone_number}</code>\n\n"
                f"This number's details will now be visible to users.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ Error removing protection. Please try again.")
    
    # /addcredit <credits> <user_id> - Add credits to user
    elif command[0] == "/addcredit":
        if len(command) < 2:
            await update.message.reply_text("Usage: /addcredit <credits> <user_id>")
            return
        
        args = command[1].strip().split()
        
        if len(args) < 2:
            await update.message.reply_text("Usage: /addcredit <credits> <user_id>")
            return
        
        try:
            credits = int(args[0])
            target_user_id = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ Please provide valid numbers for credits and user ID.")
            return
        
        if credits <= 0:
            await update.message.reply_text("❌ Credits must be greater than 0.")
            return
        
        add_credits(target_user_id, credits)
        
        await update.message.reply_text(
            f"✅ <b>Credits Added</b>\n\n"
            f"User ID: <code>{target_user_id}</code>\n"
            f"Credits Added: <b>{credits}</b>\n\n"
            f"Total credits have been updated in the system.",
            parse_mode="HTML"
        )

def main() -> None:
    """Start the bot."""
    # Initialize database
    init_database()
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["protect", "unprotect", "addcredit"], owner_commands))
    application.add_handler(CallbackQueryHandler(button_handler))
    # Responds to any text message that isn't a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fetch_details))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
