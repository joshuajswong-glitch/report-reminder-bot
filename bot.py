import os
import json
import logging
import asyncio
from datetime import datetime
import pytz
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, ChatMemberHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8791093740:AAEXo7_ofaGkyjygOr43fNbk5Jay57oALiE"
DATA_FILE = "groups.json"
TIMEZONE = "Australia/Perth"

REMINDER_MESSAGE = """📋 *Class Report Reminder*

Hi team! 👋 Just a reminder to submit your class report for today's session.

Please make sure your leave has filled in the report after class.

_If you have already submitted, please ignore this message_ ✅"""

def load_groups():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_groups(groups):
    with open(DATA_FILE, "w") as f:
        json.dump(groups, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm the Report Reminder Bot!\n\n"
        "To activate reminders for this group, send:\n"
        "/setup MWF — for Mon/Wed/Fri classes\n"
        "/setup TTS — for Tue/Thu/Sat classes\n\n"
        "I'll send a reminder at 9pm on every class day!",
    )

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not context.args:
        await update.message.reply_text(
            "Please specify: /setup MWF or /setup TTS"
        )
        return

    schedule = context.args[0].upper()
    if schedule not in ["MWF", "TTS"]:
        await update.message.reply_text("Invalid. Use /setup MWF or /setup TTS")
        return

    groups = load_groups()
    groups[str(chat.id)] = {
        "title": chat.title,
        "schedule": schedule
    }
    save_groups(groups)

    days = "Monday, Wednesday & Friday" if schedule == "MWF" else "Tuesday, Thursday & Saturday"
    await update.message.reply_text(
        f"✅ Setup complete!\n\n"
        f"This group will receive reminders every {days} at 9:00 PM.\n\n"
        f"To change, run /setup again."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    groups = load_groups()
    group_data = groups.get(str(chat.id))
    if group_data:
        schedule = group_data["schedule"]
        days = "Monday, Wednesday & Friday" if schedule == "MWF" else "Tuesday, Thursday & Saturday"
        await update.message.reply_text(
            f"✅ This group is active\n"
            f"Schedule: {days}\n"
            f"Reminder time: 9:00 PM"
        )
    else:
        await update.message.reply_text(
            "❌ Not set up yet.\n"
            "Send /setup MWF or /setup TTS to activate."
        )

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    groups = load_groups()
    if str(chat.id) in groups:
        del groups[str(chat.id)]
        save_groups(groups)
        await update.message.reply_text("✅ Reminders removed for this group.")
    else:
        await update.message.reply_text("This group was not set up.")

async def on_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member:
        new_status = update.my_chat_member.new_chat_member.status
        chat = update.my_chat_member.chat
        if new_status in ["member", "administrator"]:
            try:
                await context.bot.send_message(
                    chat.id,
                    "👋 Hi! I'm the Report Reminder Bot!\n\n"
                    "To activate reminders, send:\n"
                    "/setup MWF — Mon/Wed/Fri\n"
                    "/setup TTS — Tue/Thu/Sat\n\n"
                    "I'll remind your group at 9pm on class days!"
                )
            except Exception as e:
                logger.error(f"Could not send welcome message: {e}")

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    day = now.weekday()

    is_mwf = day in [0, 2, 4]
    is_tts = day in [1, 3, 5]

    if not is_mwf and not is_tts:
        return

    groups = load_groups()
    for chat_id, data in groups.items():
        schedule = data.get("schedule", "MWF")
        if schedule == "MWF" and not is_mwf:
            continue
        if schedule == "TTS" and not is_tts:
            continue
        try:
            await context.bot.send_message(
                int(chat_id),
                REMINDER_MESSAGE,
                parse_mode="Markdown"
            )
            logger.info(f"Sent to {data.get('title', chat_id)}")
        except Exception as e:
            logger.error(f"Failed {chat_id}: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setup", setup))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(ChatMemberHandler(on_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

    tz = pytz.timezone(TIMEZONE)
    application.job_queue.run_daily(
        send_reminders,
        time=datetime.now(tz).replace(hour=21, minute=0, second=0).timetz()
    )

    logger.info("Bot is running!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
