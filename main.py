import logging
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio
import re

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your bot token
TOKEN = 'YOUR_BOT_TOKEN'

# List of authorized user IDs
AUTH_LIST = [1045700254, 1189238402, 7169228651]  # Replace with actual authorized user IDs

# Default deletion time (in seconds)
DEFAULT_DELETE_TIME = 3600  # 1 hour

# File to store group settings
SETTINGS_FILE = 'group_settings.json'

# Load group settings
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save group settings
def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

# Global variable to store settings
group_settings = load_settings()

async def start(update: Update, context):
    start_message = (
        "Hello there! I am the Deletion Bot.\n\n"
        "I automatically delete messages in group chats after a set time.\n"
        "Authorized users and group owners can change the deletion time using the /set_delete command.\n"
        "Use /ping to check if I'm responsive.\n\n"
        "Use /admin_exclude to toggle admin message exclusion.\n\n"
        "If you're facing any difficulties, please contact @@iacbotsupport for support."
    )
    await update.message.reply_text(start_message)

async def delete_message(context, chat_id, message_id):
    await asyncio.sleep(group_settings[str(chat_id)]['delete_time'])
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

async def handle_message(update: Update, context):
    message = update.message
    if message.chat.type != 'private':
        chat_id = str(message.chat_id)
        if chat_id in group_settings:
            if group_settings[chat_id]['admin_exclude']:
                user = await context.bot.get_chat_member(message.chat_id, message.from_user.id)
                if user.status in ['administrator', 'creator']:
                    return
            context.application.create_task(delete_message(context, message.chat_id, message.message_id))

async def is_user_authorized(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if user_id in AUTH_LIST:
        return True
    
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    return chat_member.status == 'creator'

async def set_delete(update: Update, context):
    if not await is_user_authorized(update, context):
        await update.message.reply_text("You are not authorized to use this command. Only group owners and authorized users can set the deletion time.")
        return

    if not context.args:
        await update.message.reply_text("Please provide a time for message deletion.")
        return

    time_str = context.args[0]
    seconds = parse_time(time_str)

    if seconds is None:
        await update.message.reply_text("Invalid time format. Use combinations of d, h, m, s (e.g., 1h30m).")
        return

    chat_id = str(update.effective_chat.id)
    if chat_id not in group_settings:
        group_settings[chat_id] = {'delete_time': seconds, 'admin_exclude': False}
    else:
        group_settings[chat_id]['delete_time'] = seconds
    save_settings(group_settings)
    await update.message.reply_text(f"Message deletion time set to {time_str}.")

async def admin_exclude(update: Update, context):
    if not await is_user_authorized(update, context):
        await update.message.reply_text("You are not authorized to use this command. Only group owners and authorized users can toggle admin exclusion.")
        return

    if not context.args or context.args[0] not in ['enable', 'disable']:
        await update.message.reply_text("Please specify 'enable' or 'disable' for admin exclusion.")
        return

    chat_id = str(update.effective_chat.id)
    if chat_id not in group_settings:
        group_settings[chat_id] = {'delete_time': DEFAULT_DELETE_TIME, 'admin_exclude': False}

    group_settings[chat_id]['admin_exclude'] = (context.args[0] == 'enable')
    save_settings(group_settings)
    status = "enabled" if group_settings[chat_id]['admin_exclude'] else "disabled"
    await update.message.reply_text(f"Admin message exclusion has been {status}.")

def parse_time(time_str):
    pattern = re.compile(r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?')
    match = pattern.match(time_str)
    
    if not match:
        return None

    days, hours, minutes, seconds = match.groups()
    total_seconds = 0
    
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)

    return total_seconds if total_seconds > 0 else None

async def send_restart_notifications(application):
    for chat_id, settings in group_settings.items():
        try:
            delete_time = settings['delete_time']
            time_str = f"{delete_time // 3600}h {(delete_time % 3600) // 60}m {delete_time % 60}s"
            message = f"I'm back! I will start deleting messages from this point onward. Current deletion time: {time_str}"
            await application.bot.send_message(chat_id=int(chat_id), text=message)
        except Exception as e:
            logger.error(f"Error sending restart notification to chat {chat_id}: {e}")

#Ping! 
async def ping(update: Update, context):
    await update.message.reply_text("Pong! I'm here and responsive cutie.")

def main():
    application = Application.builder().token(TOKEN).build()

    # Adding handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_delete", set_delete))
    application.add_handler(CommandHandler("admin_exclude", admin_exclude))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("ping", ping))

    # Send restart notifications
    application.create_task(send_restart_notifications(application))

    application.run_polling()

if __name__ == '__main__':
    main()
