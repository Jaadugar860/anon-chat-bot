import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import logging

# === CONFIG ===
BOT_TOKEN = '7501586254:AAHsi8NOH8w6-KcUxuBawlQOIEwy7p8euHg'
GROUP_USERNAME = 'randomtalksbuddy'  # without @
TEST_MODE = True  # 👈 Set to True for solo testing

# === BOT DATA ===
waiting_users = []
active_chats = {}
reconnect_requests = {}

# === LOGGER ===
logging.basicConfig(level=logging.INFO)

# === CHECK GROUP MEMBERSHIP ===
async def is_user_in_group(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"Group check error: {e}")
        return False

# === /START COMMAND ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    in_group = await is_user_in_group(user_id, context)
    if not in_group:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Join Group", url=f"https://t.me/{GROUP_USERNAME}")]
        ])
        await update.message.reply_text(
            "🚫 You must join the group "
            f"@{GROUP_USERNAME} to use this bot.\n\n"
            "⬇️ Click below to join and then press /start again.",
            reply_markup=keyboard
        )
        return

    if user_id in active_chats:
        await update.message.reply_text("👀 You're already in a chat. Type /next to switch.")
        return

    if user_id in waiting_users:
        await update.message.reply_text("⏳ Still searching for a partner...")
        return

    # Add to waiting list
    waiting_users.append(user_id)
    await update.message.reply_text("🔍 Looking for a partner...")

    for _ in range(15):
        if len(waiting_users) >= 2:
            if user_id not in waiting_users:
                return  # already matched
            user1 = waiting_users.pop(0)
            user2 = waiting_users.pop(0)

            active_chats[user1] = user2
            active_chats[user2] = user1

            await context.bot.send_message(user1, "🎉 Partner found! Start chatting.")
            await context.bot.send_message(user2, "🎉 Partner found! Start chatting.")
            return

        await asyncio.sleep(2)

    # Test mode: match user with self
    if TEST_MODE and len(waiting_users) == 1 and user_id in waiting_users:
        waiting_users.remove(user_id)
        active_chats[user_id] = user_id
        await context.bot.send_message(user_id, "🤖 Test mode: You're chatting with yourself.")
        return

    if user_id in waiting_users:
        waiting_users.remove(user_id)
        await update.message.reply_text("⌛ Still searching for a partner... Try again later.")

# === /NEXT, /STOP, /REPORT, /RECONNECT, /HELP ===
# (These handlers stay the same as in the previous version, just reusing them)

# === /NEXT COMMAND ===
async def next_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    if user in active_chats:
        partner = active_chats.pop(user)
        if partner != user:
            active_chats.pop(partner, None)
            await context.bot.send_message(partner, "🚪 Your partner has left the chat.\n\n💬 Type /reconnect to try reconnecting.")
            reconnect_requests[partner] = user
    await start(update, context)

# === /STOP COMMAND ===
async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    if user in active_chats:
        partner = active_chats.pop(user)
        if partner != user:
            active_chats.pop(partner, None)
            await context.bot.send_message(partner, "🚫 Your partner has ended the chat.")
            reconnect_requests[partner] = user
    elif user in waiting_users:
        waiting_users.remove(user)
    await update.message.reply_text("✅ You’ve left the chat. Use /start to find a new one.")

# === /REPORT COMMAND ===
async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter = update.effective_user.id
    if reporter in active_chats:
        reported = active_chats.pop(reporter)
        if reported != reporter:
            active_chats.pop(reported, None)
            await context.bot.send_message(reported, "🚫 Your partner has reported you. The chat has ended.")
            print(f"User {reporter} reported {reported}")
        await update.message.reply_text("✅ User reported and chat ended.")
    else:
        await update.message.reply_text("⚠️ You're not in a chat to report anyone.")

# === /RECONNECT COMMAND ===
async def reconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    if user in reconnect_requests:
        partner = reconnect_requests[user]
        if reconnect_requests.get(partner) == user:
            active_chats[user] = partner
            active_chats[partner] = user
            reconnect_requests.pop(user)
            reconnect_requests.pop(partner, None)
            await context.bot.send_message(user, "🔁 Reconnected! Say hi again.")
            await context.bot.send_message(partner, "🔁 Reconnected! Say hi again.")
        else:
            await update.message.reply_text("⏳ Waiting for your partner to also send /reconnect...")
    else:
        await update.message.reply_text("❗ No reconnect request found.")

# === /HELP COMMAND ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to Anonymous Chat Bot!*\n\n"
        "💡 Commands:\n"
        "🔹 /start – Find a partner\n"
        "🔹 /next – Skip to a new partner\n"
        "🔹 /stop – Leave the current chat\n"
        "🔹 /report – Report abusive partner\n"
        "🔹 /reconnect – Reconnect if both users agree\n"
        "🔹 /help – Show this message\n\n"
        "⚠️ Only group members can use this bot."
    )
    await update.message.reply_markdown(msg)

# === TYPING INDICATOR ===
async def send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user.id
    if sender in active_chats:
        receiver = active_chats[sender]
        if receiver != sender:
            try:
                await context.bot.send_chat_action(receiver, ChatAction.TYPING)
            except:
                pass

# === MESSAGE HANDLING ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user.id
    if sender not in active_chats:
        await update.message.reply_text("❗ You're not in a chat. Type /start to find a partner.")
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
        await update.message.reply_text("⚠️ Failed to send message. Partner may have left.")

# === MAIN ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("next", next_chat))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler("report", report_user))
    app.add_handler(CommandHandler("reconnect", reconnect))
    app.add_handler(CommandHandler("help", help_command))

    # Typing
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_typing), group=0)

    # Message forwarding
    app.add_handler(MessageHandler(filters.ALL, handle_message), group=1)

import asyncio

async def main():
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Webhook deleted. Bot is running...")
    await app.run_polling()

asyncio.run(main())

