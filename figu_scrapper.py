from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

with open("/home/pi/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

runScrapper = 0


def help(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        """Sends explanation on how to use the bot."""
        txt = '/getIp - devuelve el ip del host'
        txt += chr(10)
        txt += '/startScrapper - empieza el scrapper de figus'
        txt += chr(10)
        txt += '/stopScrapper - para el scrapper de figus'


        context.bot.send_message(chat_id=data["chatNacho"], text=txt)


def stop_scrapper_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runScrapper
        runScrapper = 0
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runScrapper) + ' se paró la ejecución de futuros')



def start_scrapper_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runScrapper
        runScrapper = 1
        context.job_queue.run_repeating(scrapper_auto, interval=90.0, first=0.0)
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='Runfutures: ' + str(runScrapper) + ' comenzó ejecución de scrapper')


def get_ip(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        ip = requests.get('https://api.ipify.org').content.decode('utf8')
        context.bot.send_message(chat_id=data["chatNacho"], text=ip)



def scrapper_auto(context: CallbackContext):
    if runScrapper == 1:
        try:
            options = Options()
            options.BinaryLocation = "/usr/bin/chromium-browser"
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument("--window-size=1920x1080")
            options.add_argument("start-maximized")
            options.add_argument("enable-automation")
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-browser-side-navigation")
            options.add_argument("--disable-gpu")
            driver_path = "/usr/lib/chromium-browser/chromedriver"
            #driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            driver = webdriver.Chrome(service=Service(driver_path), options=options)
            driver.implicitly_wait(20)
            driver.get("https://www.zonakids.com/productos/pack-promo-1-album-tapa-dura-100-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
            page = driver.page_source
            soup = BeautifulSoup(''.join(page), 'html.parser').body
            txt = str(soup.find_all("input", {"class": "btn btn-primary full-width js-prod-submit-form js-addtocart nostock m-bottom-half"})[0])
            txt2 = str(soup.find_all("div", {"class": "js-addtocart js-addtocart-placeholder btn btn-primary full-width btn-transition m-bottom-half disabled"})[0])

            dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            if "Sin stock" in txt and "display: none" in txt2:
                print('No hay stock ' + dt)
            else:
                context.bot.send_message(chat_id=data["chatNacho"],
                                         text="Hay Stock de album!! https://www.zonakids.com/productos/pack-promo-1-album-tapa-dura-100-sobres-de-figuritas-fifa-world-cup-qatar-2022/")

        except Exception as e:
            context.bot.send_message(chat_id=data["chatNacho"],
                                         text="Por las dudas checkea!! https://www.zonakids.com/productos/pack-promo-1-album-tapa-dura-100-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
            print("error trayendo datos. " + dt)
            print(e)

        try:
          driver.get("https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
          page = driver.page_source
          soup = BeautifulSoup(''.join(page), 'html.parser').body
          txt = str(soup.find_all("input", {"class": "btn btn-primary full-width js-prod-submit-form js-addtocart nostock m-bottom-half"})[0])
          txt2 = str(soup.find_all("div", {"class": "js-addtocart js-addtocart-placeholder btn btn-primary full-width btn-transition m-bottom-half disabled"})[0])

          if "Sin stock" in txt and "display: none" in txt2:
              print('No hay stock ' + dt)
          else:
              context.bot.send_message(chat_id=data["chatNacho"],
                                       text="Hay Stock de figus!! https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022/")
        except Exception as e:
            context.bot.send_message(chat_id=data["chatNacho"],
                                         text="Por las dudas checkea!! https://www.zonakids.com/productos/pack-x-25-sobres-de-figuritas-fifa-world-cup-qatar-2022//")
            print("error trayendo datos. " + dt)
            print(e)


def send_message(message):
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}
    requests.get(url, params=params)



def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(data["botToken"])

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("getIp", get_ip))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("startScrapper", start_scrapper_auto))
    dispatcher.add_handler(CommandHandler("stopScrapper", start_scrapper_auto))

    # Start the Bot
    updater.start_polling()

    send_message("Fugu Scrapper Bot has just Started")

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()



if __name__ == '__main__':
    main()
