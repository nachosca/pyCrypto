from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import json

with open("/home/pi/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

runFutures = 0
runInFutures = 0
futuresDate = '240628'
futuresCheckData = [] # LINKUSD_240628,XRPUSD_240628
futuresCheckUp = 4.0
futuresCheckDown = 0.0
futuresGeneralCheckDown = -5.0


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


def help(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        """Sends explanation on how to use the bot."""
        txt = '/getIp - devuelve el ip del host'
        txt += chr(10)
        txt += '/start - cómo funciona'
        txt += chr(10)
        txt += '/futures - cuánto están rindiendo'
        txt += chr(10)
        txt += '/startFuturesAuto - empieza el robot del rendimiento'
        txt += chr(10)
        txt += '/stopFuturesAuto - para el robot del rendimiento'
        txt += chr(10)
        txt += '/checkData - checkea el estado del robot del rendimiento'
        txt += chr(10)
        txt += '/updateFuturesDate - updatea la fecha de futuros EJ: 240628'
        txt += chr(10)
        txt += '/updateFuturesCheckData - updatea los futuros a checkear EJ: LINKUSD_240628,XRPUSD_240628'
        txt += chr(10)
        txt += '/updateFuturesCheckUp - updatea el % de los futuros a checkear en alza'
        txt += chr(10)
        txt += '/updateFuturesCheckDown - updatea el % de los futuros a checkear en baja'
        txt += chr(10)
        txt += '/updateFuturesGeneralCheckDown - updatea el % de los futuros generales a checkear en baja'
        txt += chr(10)
        txt += '/startInFuturesAuto - empieza el robot del rendimiento'
        txt += chr(10)
        txt += '/stopInFuturesAuto - para el robot del rendimiento'
        context.bot.send_message(chat_id=data["chatNacho"], text=txt)


def stop_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runFutures
        runFutures = 0
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runFutures) + ' se paró la ejecución de futuros')

def stop_in_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runInFutures
        runInFutures = 0
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='RunInfutures: ' + str(runFutures) + ' se paró la ejecución de in futuros')


def start_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runFutures
        runFutures = 1
        context.job_queue.run_repeating(futures_auto, interval=86400.0, first=1.0)
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runFutures) + ' comenzó ejecución de futuros')

def start_in_futures_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runInFutures
        runInFutures = 1
        context.job_queue.run_repeating(in_futures_auto, interval=60.0, first=1.0)
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='RunInfutures: ' + str(runInFutures) + ' comenzó ejecución de in futuros')


def check_data(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        context.bot.send_message(chat_id=data["chatNacho"], text='RunFutures: ' + str(runFutures))
        context.bot.send_message(chat_id=data["chatNacho"], text='RunInFutures: ' + str(runInFutures))
        context.bot.send_message(chat_id=data["chatNacho"], text='futuresDate: ' + str(futuresDate))
        context.bot.send_message(chat_id=data["chatNacho"], text='futuresCheckData: ' + str(futuresCheckData))
        context.bot.send_message(chat_id=data["chatNacho"], text='futuresCheckUp: ' + str(futuresCheckUp))
        context.bot.send_message(chat_id=data["chatNacho"], text='futuresCheckDown: ' + str(futuresCheckDown))
        context.bot.send_message(chat_id=data["chatNacho"], text='futuresGeneralCheckDown: ' + str(futuresGeneralCheckDown))


def get_ip(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        ip = requests.get('https://api.ipify.org').content.decode('utf8')
        context.bot.send_message(chat_id=data["chatNacho"], text=ip)


def futures_auto(context: CallbackContext):
    if runFutures == 1:
        result = check_futures()
        resultText = ""

        result = [d for d in result if futuresDate in d['name']]

        for i in result:
            resultText += json.dumps(i)
            resultText += chr(10)

        if result[0].get('percentage') > futuresCheckUp:
            context.bot.send_message(chat_id=data["chatChannel"],
                                     text="Encontré buen rendimiento de futuros en Binance!")
            context.bot.send_message(chat_id=data["chatChannel"], text=resultText)

def in_futures_auto(context: CallbackContext):
    if runInFutures == 1:
        result = check_futures()
        for symbol in futuresCheckData:
            result_in = [d for d in result if symbol in d['name']]
            result_text = ""

            for i in result_in:
                result_text += json.dumps(i)
                result_text += chr(10)

            if result_in[0].get('percentage') < futuresCheckDown:
                context.bot.send_message(chat_id=data["chatNacho"],
                                         text="Seguí el precio. ojota")
                context.bot.send_message(chat_id=data["chatNacho"], text=result_text)

        result_text = ""

        for i in result:
            result_text += json.dumps(i)
            result_text += chr(10)

        if result[-1].get('percentage') < futuresGeneralCheckDown:
            context.bot.send_message(chat_id=data["chatNacho"],
                                     text="Seguí el precio. ojota")
            context.bot.send_message(chat_id=data["chatNacho"], text=result_text)



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


def send_message(message):
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}
    requests.get(url, params=params)


def update_futures_date(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global futuresDate
            futuresDate = str(context.args[0])
            context.bot.send_message(chat_id=data["chatNacho"], text="Fecha actualizada a: " + str(futuresDate))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")


def update_futures_check_up(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global futuresCheckUp
            futuresCheckUp = float(context.args[0])
            context.bot.send_message(chat_id=data["chatNacho"], text="Futures Check Up: " + str(futuresCheckUp))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")


def update_futures_check_down(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global futuresCheckDown
            futuresCheckDown = float(context.args[0])
            context.bot.send_message(chat_id=data["chatNacho"], text="Futures Check Down: " + str(futuresCheckDown))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")

def update_futures_general_check_down(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global futuresGeneralCheckDown
            futuresGeneralCheckDown = float(context.args[0])
            context.bot.send_message(chat_id=data["chatNacho"], text="Futures Check Down: " + str(futuresGeneralCheckDown))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")


def update_futures_check_data(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global futuresCheckData
            futuresCheckData = context.args[0].split(',')
            context.bot.send_message(chat_id=data["chatNacho"], text="futuresCheckData parametros actualizados a: " + str(futuresCheckData))
        except:
            futuresCheckData = []
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")



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
    dispatcher.add_handler(CommandHandler("checkData", check_data))
    dispatcher.add_handler(CommandHandler("getIp", get_ip))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("updateFuturesDate", update_futures_date))
    dispatcher.add_handler(CommandHandler("updateFuturesCheckData", update_futures_check_data))
    dispatcher.add_handler(CommandHandler("updateFuturesCheckUp", update_futures_check_up))
    dispatcher.add_handler(CommandHandler("updateFuturesCheckDown", update_futures_check_down))
    dispatcher.add_handler(CommandHandler("updateFuturesGeneralCheckDown", update_futures_general_check_down))
    dispatcher.add_handler(CommandHandler("startInFuturesAuto", start_in_futures_auto))
    dispatcher.add_handler(CommandHandler("stopInFuturesAuto", stop_in_futures_auto))

    # Start the Bot
    updater.start_polling()

    send_message("Bot has just Started")

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


def check_futures(symbol=None):
    url = 'https://dapi.binance.com/dapi/v1/premiumIndex'
    # If symbol is provided, add it as a query parameter
    if symbol:
        url += f'?symbol={symbol}'

    lst = json.loads(requests.get(url).content)
    lst = [d for d in lst if 'PERP' not in d['symbol']]

    result = []
    for i in lst:
        d = {'name': i['symbol'],
             'percentage': round((float(i['markPrice']) * 100 / float(i['indexPrice'])) - 100, 3)}
        result.append(d)

    return sorted(result, key=lambda d: d['percentage'], reverse=True)


if __name__ == '__main__':
    main()
