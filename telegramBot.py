from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import json

with open("secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

runFutures = 0


def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    txt = 'Las alertas del bot se envían a t.me/CryptoPiolaAlerts'

    update.message.reply_text(txt)

    txt = 'Cómo funciona esto?'
    txt += chr(10)
    txt += 'Operando con spot/futuros se puede obtener un buen rendimiento en USDT en plazos menores a 3 meses.'
    txt += chr(10)
    txt += 'Ese rendimiento va variando constantemente. Si lo enganchás en un buen momento, puede rendir arriba del 4%'

    update.message.reply_text(txt)

    txt = 'Cómo operar?'
    txt += chr(10)
    txt += 'Comprás en spot con USDT la crypto que más rinda. Ej: BTC'
    txt += chr(10)
    txt += 'Movés esos BTC a la wallet de futuros'
    txt += chr(10)
    txt += 'Buscás el contrato que te devuelvo en COIN-M ej BTCUSD0325'
    txt += chr(10)
    txt += 'Shorteas el contrato en 1x'

    update.message.reply_text(txt)

    txt = 'Esperás al vencimiento del contrato'
    txt += chr(10)
    txt += 'En este caso sería el 25/02 - Siempre es a las 8am UTC'
    txt += chr(10)
    txt += 'En ese momento te van a transferir la crypto a tu billetera de futuros.'
    txt += chr(10)
    txt += 'Pasas la crypto a billtera de spot.'
    txt += chr(10)
    txt += 'Vendés los BTC por USDT.'
    txt += chr(10)
    txt += 'Y listo, ganancia asegurada.'

    update.message.reply_text(txt)

    txt = 'Si hacemos un 4% cada 3 meses -> a fin de año es un 17% aprox de ganancia asegurada.'
    update.message.reply_text(txt)

def stop_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runFutures
        runFutures = 0
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runFutures) + ' se paró la ejecución de futuros')

def start_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runFutures
        runFutures = 1
        context.job_queue.run_repeating(futures_auto, interval=1800.0, first=0.0)
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runFutures) + ' comenzó ejecución de futuros')

def check_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runFutures))

def futures_auto(context: CallbackContext):
    if runFutures == 1:
        result = check_futures()
        resultText = ""

        for i in result:
            resultText += json.dumps(i)
            resultText += chr(10)

        if result[0].get('percentage') > 3.5:
            context.bot.send_message(chat_id=data["chatChannel"],
                                     text="Encontré buen rendimiento de futuros en Binance!")
            context.bot.send_message(chat_id=data["chatChannel"], text=resultText)


def futures(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:

        result = check_futures()

        resultText = ""

        for i in result:
            resultText += json.dumps(i)
            resultText += chr(10)

        context.bot.send_message(chat_id=context._chat_id_and_data[0], text=resultText)
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
    dispatcher.add_handler(CommandHandler("futures", futures))
    dispatcher.add_handler(CommandHandler("startFuturesAuto", start_futures_auto))
    dispatcher.add_handler(CommandHandler("stopFuturesAuto", stop_futures_auto))
    dispatcher.add_handler(CommandHandler("checkFuturesAuto", check_futures_auto))

    # Start the Bot
    updater.start_polling()

    send_message()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


def check_futures():
    name = '220325'
    lst = json.loads(requests.get('https://dapi.binance.com/dapi/v1/premiumIndex').content)
    lst = [d for d in lst if name in d['symbol']]

    result = []
    for i in lst:
        d = {'name': i['symbol'],
             'percentage': round((float(i['markPrice']) * 100 / float(i['indexPrice'])) - 100, 3)}
        result.append(d)

    return sorted(result, key=lambda d: d['percentage'], reverse=True)


if __name__ == '__main__':
    main()
