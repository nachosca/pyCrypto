from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
import subprocess
import json
import platform
import statistics

runCheck = True

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
        txt += '/minerStart - arranca el minero'
        txt += chr(10)
        txt += '/rigStats - stats del minero'
        txt += chr(10)
        txt += '/startCheckRig - comienza a checkear el minero'
        txt += chr(10)
        txt += '/stopCheckRig - para de checkear el minero'
        txt += chr(10)
        txt += '/selfUpdate - bot self update'
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
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text='Restarting miner...')
    else:
        update.message.reply_text('Tomatela gato.')


def miner_stop(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'miner stop'
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text='Stopping miner...')
    else:
        update.message.reply_text('Tomatela gato.')


def miner_start(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'miner start'
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        context.bot.send_message(chat_id=context._chat_id_and_data[0], text='Starting miner...')
    else:
        update.message.reply_text('Tomatela gato.')


def start_check_rig(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        global runCheck
        runCheck = True
        context.job_queue.run_repeating(check_bot, interval=300.0, first=0.0)
        context.bot.send_message(chat_id=data["chatId"],
                                 text='Runfutures: ' + str(runCheck) + ' comenzó ejecución de check rig')


def stop_check_rig(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        global runCheck
        runCheck = False
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatId"],
                                 text='Runfutures: ' + str(runCheck) + ' se paró la ejecución de check rig')


def get_rig_stats(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        try:
            dict_result = get_miner_stats()
            context.bot.send_message(chat_id=data["chatId"],
                                     text=json.dumps(dict_result, sort_keys=True, indent=4).replace('\n', chr(10)))
        except:
            context.bot.send_message(chat_id=data["chatId"], text=txt_problem())


def self_update(update: Update, context: CallbackContext):
    if update.effective_chat.id in [int(data["chatId"])]:
        cmd = 'curl -o /home/user/python/bot.py https://raw.githubusercontent.com/nachosca/pyCrypto/main/telegramRigBot.py'
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd = 'curl -o /etc/systemd/system/bot.service https://raw.githubusercontent.com/nachosca/pyCrypto/main/bot.service'
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd = 'sudo systemctl daemon-reload'
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd = 'systemctl restart bot.service'
        context.bot.send_message(chat_id=data["chatId"], text="update OK")
        subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def check_bot(context: CallbackContext):
    if runCheck == 1:
        try:
            dict_result = get_miner_stats()

            harmonic_mean = statistics.harmonic_mean(map(float, dict_result['hs']))
            dict_result['Media'] = harmonic_mean

            for i in dict_result['hs']:
                if (harmonic_mean / i - 1) > float(0.05):
                    context.bot.send_message(chat_id=data["chatId"], text=json.dumps(dict_result, sort_keys=True, indent=4).replace('\n', chr(10)))
                    context.bot.send_message(chat_id=data["chatId"], text=txt_problem())
                    break
        except:
            context.bot.send_message(chat_id=data["chatId"], text=txt_problem())


def txt_problem():
    txt = 'Rig con problemas. Ejecutar:'
    txt += chr(10)
    txt += '/reboot - resetea el rig'
    txt += chr(10)
    txt += '/minerRestart - resetea el minero'
    txt += chr(10)
    return txt

def get_miner_stats():
    hive_log_file = open("/var/log/hive-agent.log", "r")
    hive_log = hive_log_file.readlines()
    hive_log_file.close()

    log_text = ""
    for i in reversed(hive_log):
        if "method" in i:
            log_text = i[i.find("{")::]
            break
        else:
            continue

    dict_log = json.loads(log_text)["params"]["miner_stats"]
    print(dict_log)

    whiteList = ['hs', 'temp']
    dict_result = dict((k, v) for k, v in dict_log.items() if k in whiteList)
    dict_result['hs'] = [0 if x is None else round(x / 1000 / 1000, 2) for x in dict_result['hs']]

    return dict_result


def send_message():
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    txt = "Bot " + platform.node() + " has just Started"
    txt += chr(10)
    txt += "Ejecutar /startCheckRig para que comience a checkear el rig."
    params = {"chat_id": data["chatId"], "text": txt}
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
    dispatcher.add_handler(CommandHandler("rigStats", get_rig_stats))
    dispatcher.add_handler(CommandHandler("startCheckRig", start_check_rig))
    dispatcher.add_handler(CommandHandler("stopCheckRig", stop_check_rig))
    dispatcher.add_handler(CommandHandler("selfUpdate", self_update))

    # Start the Bot
    updater.start_polling()

    send_message()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
