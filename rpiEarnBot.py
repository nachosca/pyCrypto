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

def statusP2P(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo docker ps'
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stdout.decode('utf-8'))
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')


def startP2P(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo docker rm -f peer2profit'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
        cmd = 'sudo docker run -d --restart always -e P2P_EMAIL=EMAIL --name peer2profit peer2profit/peer2profit_linux:latest'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')


def startHoney(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo docker run -it --rm  --restart always --platform linux/amd64 --name honey honeygain/honeygain -tou-accept -email MAIL -pass PASS -device rpi'
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

def stopP2P(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo docker stop peer2profit'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def stopHoney(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo docker stop honey'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')

def restart(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        cmd = 'sudo shutdown -r now'
        result = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=result.stderr.decode('utf-8'))
    else:
        update.message.reply_text('Tomatela gato.')


def get_ip(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        ip = requests.get('https://api.ipify.org').content.decode('utf8')
        context.bot.send_message(chat_id=data["chatNacho"], text=ip)

def help(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        """Sends explanation on how to use the bot."""
        txt = '/getIp - devuelve el ip del host'
        txt += chr(10)
        txt += '/start - cómo funciona'
        txt += chr(10)
        txt += '/statusP - está levantado earnapp?'
        txt += chr(10)
        txt += '/startP - levanta earnapp'
        txt += chr(10)
        txt += '/stopP - para earnapp'
        txt += chr(10)
        txt += '/statusP2P - está levantado peer2profit?'
        txt += chr(10)
        txt += '/startP2P - levanta peer2profit'
        txt += chr(10)
        txt += '/stopP2P - para peer2profit'
        txt += chr(10)
        txt += '/startHoney - levanta honeyGain'
        txt += chr(10)
        txt += '/stopHoney - para honeyGain'
        txt += chr(10)
        txt += '/restart - restartea rpi'
        context.bot.send_message(chat_id=data["chatNacho"], text=txt)

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
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("statusP", statusP))
    dispatcher.add_handler(CommandHandler("startP", startP))
    dispatcher.add_handler(CommandHandler("stopP", stopP))
    dispatcher.add_handler(CommandHandler("startP2P", startP2P))
    dispatcher.add_handler(CommandHandler("stopP2P", stopP2P))
    dispatcher.add_handler(CommandHandler("statusP2P", statusP2P))
    dispatcher.add_handler(CommandHandler("startHoney", startHoney))
    dispatcher.add_handler(CommandHandler("stopHoney", stopHoney))
    dispatcher.add_handler(CommandHandler("getIp", get_ip))

    dispatcher.add_handler(CommandHandler("restart", restart))

    # Start the Bot
    updater.start_polling()

    send_message()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
