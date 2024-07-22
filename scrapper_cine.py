from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

with open("/home/pi/secrets.txt", encoding="UTF-8") as filedata:
    data = eval(filedata.read())

runScrapper = 0
movie = "deadpool"
cinema = "18"


def help(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        """Sends explanation on how to use the bot."""
        txt = '/getIp - devuelve el ip del host'
        txt += chr(10)
        txt += '/startScrapper - empieza el scrapper de cine'
        txt += chr(10)
        txt += '/stopScrapper - para el scrapper de cine'
        txt += chr(10)
        txt += '/updateMovie - actualiza la peli a buscar'
        txt += chr(10)
        txt += '/updateCinema - actualiza el cine a buscar'


        context.bot.send_message(chat_id=data["chatNacho"], text=txt)


def stop_scrapper_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runScrapper
        runScrapper = 0
        context.job_queue.stop()
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='RunScrapper: ' + str(runScrapper) + ' se paró la ejecución de scrapper')



def start_scrapper_auto(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runScrapper
        runScrapper = 1
        context.job_queue.run_repeating(scrapper_auto, interval=60.0, first=0.0)
        context.bot.send_message(chat_id=data["chatNacho"],
                                 text='RunScrapper: ' + str(runScrapper) + ' comenzó ejecución de scrapper')

def update_movie(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global movie
            movie = str(context.args[0]).lower()
            context.bot.send_message(chat_id=data["chatNacho"], text="movie actualizada a: " + str(movie))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")

def update_cinema(update: Update, context: CallbackContext):
    if update.effective_chat.id in [data["chatNacho"]]:
        try:
            global cinema
            cinema = str(context.args[0]).lower()
            context.bot.send_message(chat_id=data["chatNacho"], text="cinema actualizada a: " + str(cinema))
        except:
            context.bot.send_message(chat_id=data["chatNacho"], text="Error en parámetro.")


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
            driver.get("https://entradas.todoshowcase.com/showcase/boleteria.aspx")
            dropdown = Select(driver.find_element(By.ID, 'ctl00_Contenido_lstCinemaFull'))
            dropdown.select_by_value(cinema)

            element_present = EC.presence_of_element_located((By.ID, 'ctl00_Contenido_lstMovies'))
            WebDriverWait(driver, 20).until(element_present)

            # Locate the dropdown element
            dropdown = driver.find_element(By.ID, 'ctl00_Contenido_lstMovies')

            # Get all the options in the dropdown
            options = dropdown.find_elements(By.TAG_NAME, 'option')

            movie_found = False
            movie_title = ''
            for option in options:
                if movie.lower() in option.text.lower():
                    movie_found = True
                    movie_title = option.text
                    break

            if movie_found:
                print(f"{movie_title} is on the list.")
                result = f"Hay entradas para {movie_title} https://entradas.todoshowcase.com/showcase/boleteria.aspx"
                context.bot.send_message(chat_id=data["chatPibes"], text=result)

            # Close the WebDriver
            driver.quit()


        except Exception as e:
            print("error trayendo datos.")
            print(e)



def send_message(message):
    url = f"https://api.telegram.org/bot{data['botToken2']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}
    requests.get(url, params=params)



def main():
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(data["botToken2"])

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("getIp", get_ip))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("startScrapper", start_scrapper_auto))
    dispatcher.add_handler(CommandHandler("stopScrapper", stop_scrapper_auto))
    dispatcher.add_handler(CommandHandler("updateMovie", update_movie))
    dispatcher.add_handler(CommandHandler("updateCinema", update_cinema))

    # Start the Bot
    updater.start_polling()

    send_message("Movie Scrapper Bot has just Started")

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()



if __name__ == '__main__':
    main()
