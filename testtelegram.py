from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import json


def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    update.message.reply_text('Qué onda, este es el bot más piola.')


def futures(update: Update, context: CallbackContext):
    if update.effective_chat.id in ['YOUR_CHAT_IDS']:
        chatId = context._chat_id_and_data[0]
        name = '220325'
        lst = json.loads(requests.get('https://dapi.binance.com/dapi/v1/premiumIndex').content)
        lst = [d for d in lst if name in d['symbol']]

        result = []
        for i in lst:
            d = {'name': i['symbol'],
                 'percentage': round((float(i['markPrice']) * 100 / float(i['indexPrice'])) - 100, 3)}
            result.append(d)

        result = sorted(result, key=lambda d: d['percentage'], reverse=True)

        resultText = ""

        for i in result:
            resultText += json.dumps(i)
            resultText += chr(10)

        context.bot.send_message(chat_id=chatId, text=resultText)
    else:
        update.message.reply_text('Tomatela gato.')


def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("YOUR_BOT_TOKEN")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("futures", futures))

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
