from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import subprocess

with open("/home/ubuntu/projects/pybot/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    txt = 'Useless bot'

    await update.message.reply_text(txt)

async def statusP(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp status'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result.stderr.decode('utf-8'))
    else:
        await update.message.reply_text('Tomatela gato.')

async def startP(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp start'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result.stderr.decode('utf-8'))
    else:
        await update.message.reply_text('Tomatela gato.')

async def stopP(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp stop'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result.stderr.decode('utf-8'))
    else:
        await update.message.reply_text('Tomatela gato.')

def send_message():
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": "Bot has just Started"}
    requests.get(url, params=params)

def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    application = ApplicationBuilder().token(data["botToken"]).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("statusP", statusP))
    application.add_handler(CommandHandler("startP", startP))
    application.add_handler(CommandHandler("stopP", stopP))

    send_message()

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
