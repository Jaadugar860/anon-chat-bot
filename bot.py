import asyncio
import logging
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# === CONFIG ===
BOT_TOKEN = '7501586254:AAHsi8NOH8w6-KcUxuBawlQOIEwy7p8euHg'
GROUP_USERNAME = 'randomtalksbuddy'  # without @

# === DATABASE SETUP ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        language TEXT DEFAULT 'en'
    )
""")
conn.commit()

# === BOT DATA ===
waiting_users = []
active_chats = {}
reconnect_requests = {}

# === LOGGER ===
logging.basicConfig(level=logging.INFO)

# === UTILITIES ===
TRANSLATIONS = {
    'en': {
        'join_required': "🚫 You must join the group @{group} to use this bot.",
        'already_in_chat': "👀 You're already in a chat. Type /next to switch.",
        'searching': "⏳ Searching for a partner...",
        'partner_found': "🎉 Partner found! Start chatting.",
        'still_searching': "⌛ Still searching... Try again later.",
        'not_in_chat': "❗ You're not in a chat. Type /start to find a partner.",
        'chat_ended': "✅ You’ve left the chat. Use /start to find a new one.",
        'reconnect_prompt': "🔁 Reconnected! Say hi again.",
        'reported': "🚫 Your partner has reported you. The chat has ended.",
        'report_success': "✅ User reported and chat ended.",
        'no_reconnect': "❗ No reconnect request found.",
        'waiting_reconnect': "⏳ Waiting for your partner to also send /reconnect...",
# === /HELP COMMAND ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to Anonymous Chat Bot!*\n\n"
        "💡 *Commands:*\n"
        "🔹 /start – Find a partner\n"
        "🔹 /next – Skip to a new partner\n"
        "🔹 /stop – Leave the current chat\n"
        "🔹 /report – Report abusive partner\n"
        "🔹 /reconnect – Reconnect if both users agree\n"
        "🔹 /help – Show this message\n\n"
        "⚠️ *Note:* Only group members can use this bot."
    )
    await update.message.reply_markdown_v2(msg)

        'select_lang': "🌐 Select your language:",
    },
    'hi': {
        'join_required': "🚫 इस बॉट का उपयोग करने के लिए आपको @{group} समूह में शामिल होना होगा।",
        'already_in_chat': "👀 आप पहले से ही चैट में हैं। /next टाइप करें।",
        'searching': "⏳ साथी की तलाश हो रही है...",
        'partner_found': "🎉 साथी मिल गया! चैट शुरू करें।",
        'still_searching': "⌛ अभी भी तलाश में... बाद में प्रयास करें।",
        'not_in_chat': "❗ आप किसी चैट में नहीं हैं। /start टाइप करें।",
        'chat_ended': "✅ आपने चैट छोड़ दी है। /start टाइप करके नया साथी पाएं।",
        'reconnect_prompt': "🔁 फिर से जुड़ गए! दोबारा बात शुरू करें।",
        'reported': "🚫 आपके साथी ने आपको रिपोर्ट किया है। चैट समाप्त हुई।",
        'report_success': "✅ उपयोगकर्ता की रिपोर्ट की गई और चैट समाप्त हुई।",
        'no_reconnect': "❗ कोई पुन: कनेक्शन अनुरोध नहीं मिला।",
        'waiting_reconnect': "⏳ आपके साथी से /reconnect का इंतजार किया जा रहा है...",
        'help': (
            "👋 *अनोनिमस चैट बॉट में आपका स्वागत है!*\n\n"
            "💡 कमांड्स:\n"
            "🔹 /start – साथी खोजें\n"
            "🔹 /next – नया साथी\n"
            "🔹 /stop – चैट छोड़ें\n"
            "🔹 /report – दुर्व्यवहार की रिपोर्ट करें\n"
            "🔹 /reconnect – पुनः कनेक्ट करें\n"
            "🔹 /help – सहायता संदेश\n"
            "🔹 /language – भाषा बदलें"
        ),
        'select_lang': "🌐 अपनी भाषा चुनें:",
    }
}

def get_user_language(user_id):
    cursor.execute("SELECT language FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 'en'

def set_user_language(user_id, lang):
    cursor.execute("INSERT OR REPLACE INTO users (id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()

async def is_user_in_group(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    t = TRANSLATIONS[lang]

    in_group = await is_user_in_group(user_id, context)
    if not in_group:
        await update.message.reply_text(t['join_required'].format(group=GROUP_USERNAME))
        return

    if user_id in active_chats:
        await update.message.reply_text(t['already_in_chat'])
        return

    if user_id not in waiting_users:
        waiting_users.append(user_id)
        await update.message.reply_text(t['searching'])

        for _ in range(15):
            if user_id in active_chats:
                return
            await asyncio.sleep(2)

        if user_id in waiting_users:
            await update.message.reply_text(t['still_searching'])
            waiting_users.remove(user_id)
    else:
        await update.message.reply_text(t['searching'])

    if len(waiting_users) >= 2:
        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)
        active_chats[user1] = user2
        active_chats[user2] = user1
        await context.bot.send_message(user1, t['partner_found'])
        await context.bot.send_message(user2, t['partner_found'])

# === MESSAGE HANDLER ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user.id
    lang = get_user_language(sender)
    t = TRANSLATIONS[lang]

    if sender not in active_chats:
        await update.message.reply_text(t['not_in_chat'])
        return

    receiver = active_chats[sender]
    msg = update.message
    try:
        if msg.text:
            await context.bot.send_message(receiver, msg.text)
        elif msg.sticker:
            await context.bot.send_sticker(receiver, msg.sticker.file_id)
        elif msg.photo:
            await context.bot.send_photo(receiver, msg.photo[-1].file_id, caption=msg.caption or "")
        elif msg.video:
            await context.bot.send_video(receiver, msg.video.file_id, caption=msg.caption or "")
        elif msg.voice:
            await context.bot.send_voice(receiver, msg.voice.file_id)
        elif msg.document:
            await context.bot.send_document(receiver, msg.document.file_id, caption=msg.caption or "")
    except:
        await update.message.reply_text("⚠️ Message sending failed.")

# === COMMANDS ===
async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    lang = get_user_language(user)
    t = TRANSLATIONS[lang]

    if user in active_chats:
        partner = active_chats.pop(user)
        active_chats.pop(partner, None)
        await context.bot.send_message(partner, t['chat_ended'])
        reconnect_requests[partner] = user

    if user in waiting_users:
        waiting_users.remove(user)

    await update.message.reply_text(t['chat_ended'])

async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_chat(update, context)
    await start(update, context)

async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter = update.effective_user.id
    lang = get_user_language(reporter)
    t = TRANSLATIONS[lang]

    if reporter in active_chats:
        reported = active_chats.pop(reporter)
        active_chats.pop(reported, None)
        await context.bot.send_message(reported, t['reported'])
        await update.message.reply_text(t['report_success'])

async def reconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    lang = get_user_language(user)
    t = TRANSLATIONS[lang]

    if user in reconnect_requests:
        partner = reconnect_requests[user]
        if reconnect_requests.get(partner) == user:
            active_chats[user] = partner
            active_chats[partner] = user
            reconnect_requests.pop(user)
            reconnect_requests.pop(partner, None)
            await context.bot.send_message(user, t['reconnect_prompt'])
            await context.bot.send_message(partner, t['reconnect_prompt'])
        else:
            await update.message.reply_text(t['waiting_reconnect'])
    else:
        await update.message.reply_text(t['no_reconnect'])

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(update.effective_user.id)
    t = TRANSLATIONS[lang]
    await update.message.reply_markdown(t['help'])

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇮🇳 हिंदी", callback_data='lang_hi')],
    ]
    await update.message.reply_text(
        TRANSLATIONS['en']['select_lang'],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_lang_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.split('_')[-1]
    set_user_language(user_id, lang_code)
    await query.answer("Language updated!")
    await help_command(update, context)

# === MAIN ===
if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler("next", next_chat))
    app.add_handler(CommandHandler("report", report_user))
    app.add_handler(CommandHandler("reconnect", reconnect))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", change_language))
    app.add_handler(CallbackQueryHandler(handle_lang_selection))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("🤖 Bot is running...")
    app.run_polling()
