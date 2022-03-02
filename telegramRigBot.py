from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import subprocess
import platform


with open("/home/user/python/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())


def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    txt = 'Useless bot'

    update.message.reply_text(txt)
    update.message.reply_text(update.effective_chat.id)

def help(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        """Sends explanation on how to use the bot Rig Nacho."""
        txt = '/getIp - devuelve el ip del host'
        txt += chr(10)
        txt += '/start - cómo funciona'
        txt += chr(10)
        txt += '/reboot - resetea el rig'
        txt += chr(10)
        txt += '/minerRestart - resetea el minero'
        txt += chr(10)
        txt += '/minerStop - para el minero'
        txt += chr(10)
        txt += '/minerStart - arrancha el minero'
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=txt)

def get_ip(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        ip = requests.get('https://api.ipify.org').content.decode('utf8')
        context.bot.send_message(chat_id=data["chatId"], text=ip)


def reboot(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'sudo reboot'
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text='Rebooting...')
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        update.message.reply_text('Tomatela gato.')

def miner_restart(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'miner restart'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def miner_stop(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'miner stop'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def miner_start(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'miner start'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')


def send_message():
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatId"], "text": "Bot " + platform.node() + " has just Started"}
    requests.get(url, params=params)

def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(data["botToken"])

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("getIp", get_ip))
    dispatcher.add_handler(CommandHandler("reboot", reboot))
    dispatcher.add_handler(CommandHandler("minerRestart", miner_restart))
    dispatcher.add_handler(CommandHandler("minerStop", miner_stop))
    dispatcher.add_handler(CommandHandler("minerStart", miner_start))

    # Start the Bot
    updater.start_polling()

    send_message()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()