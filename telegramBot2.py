from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import subprocess

with open("/home/ubuntu/projects/pybot/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())


def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    txt = 'Useless bot'

    update.message.reply_text(txt)

def statusP(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp status'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def startP(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp start'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def stopP(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'earnapp stop'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def send_message():
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": "Bot has just Started"}
    requests.get(url, params=params)

def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(data["botToken"])

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("statusP", statusP))
    dispatcher.add_handler(CommandHandler("startP", startP))
    dispatcher.add_handler(CommandHandler("stopP", stopP))

    # Start the Bot
    updater.start_polling()

    send_message()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
