import ast
import logging
import os
from pathlib import Path

import requests
from requests import RequestException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from webdriver_manager.chrome import ChromeDriverManager

LOGGER = logging.getLogger(__name__)
SECRETS_ENV_VAR = "SCRAPPER_SECRETS_FILE"
DEFAULT_SECRETS_PATHS = (
    Path(__file__).with_name("secrets.txt"),
    Path("/home/pi/secrets.txt"),
)
DEFAULT_CHROME_BINARY_PATHS = (
    Path("/usr/bin/chromium-browser"),
    Path("/usr/bin/chromium"),
    Path("/snap/bin/chromium"),
    Path("/usr/bin/google-chrome"),
)
DEFAULT_CHROMEDRIVER_PATHS = (
    Path("/usr/lib/chromium-browser/chromedriver"),
    Path("/usr/bin/chromedriver"),
)
TARGET_URL = "https://entradas.todoshowcase.com/showcase/boleteria.aspx"
SCRAPPER_JOB_NAME = "scrapper_auto"
REQUEST_TIMEOUT = 15


def load_config() -> dict:
    candidate_paths = []
    configured_path = os.getenv(SECRETS_ENV_VAR)
    if configured_path:
        candidate_paths.append(Path(configured_path).expanduser())
    candidate_paths.extend(DEFAULT_SECRETS_PATHS)

    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as filedata:
                return ast.literal_eval(filedata.read())
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Invalid secrets file format: {path}") from exc

    checked_paths = ", ".join(str(path) for path in candidate_paths)
    raise FileNotFoundError(
        f"Could not find secrets file. Checked: {checked_paths}. "
        f"You can also set {SECRETS_ENV_VAR}."
    )


data = load_config()
AUTHORIZED_CHAT_IDS = {data["chatNacho"]}
runScrapper = 0
movie = "mandalorian"
cinema = "18"


def is_authorized(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id in AUTHORIZED_CHAT_IDS)


def get_chrome_options() -> Options:
    options = Options()
    chrome_binary = os.getenv("CHROME_BINARY")

    if chrome_binary:
        options.binary_location = chrome_binary
    else:
        detected_binary = next((path for path in DEFAULT_CHROME_BINARY_PATHS if path.exists()), None)
        if detected_binary is not None:
            options.binary_location = str(detected_binary)

    for argument in (
        "--headless",
        "--no-sandbox",
        "--window-size=1920x1080",
        "--disable-dev-shm-usage",
        "--disable-browser-side-navigation",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--remote-debugging-port=9222",
    ):
        options.add_argument(argument)

    return options


def build_driver() -> webdriver.Chrome:
    configured_driver_path = os.getenv("CHROMEDRIVER_PATH")
    if configured_driver_path:
        service = Service(configured_driver_path)
    else:
        detected_driver = next((path for path in DEFAULT_CHROMEDRIVER_PATHS if path.exists()), None)
        if detected_driver is not None:
            service = Service(str(detected_driver))
        else:
            service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=get_chrome_options())
    driver.implicitly_wait(20)
    return driver


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    txt = "\n".join(
        (
            "/getIp - devuelve el ip del host",
            "/viewConfig - muestra la config actual",
            "/startScrapper - empieza el scrapper de cine",
            "/stopScrapper - para el scrapper de cine",
            "/updateMovie <pelicula> - actualiza la peli a buscar",
            "/updateCinema <cine> - actualiza el cine a buscar",
        )
    )
    await context.bot.send_message(chat_id=data["chatNacho"], text=txt)


def format_runtime_config() -> str:
    configured_secrets_path = os.getenv(SECRETS_ENV_VAR, "default paths")
    chrome_binary = os.getenv("CHROME_BINARY", "auto-detect")
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "auto-detect")

    return "\n".join(
        (
            "Config actual:",
            f"runScrapper: {runScrapper}",
            f"movie: {movie}",
            f"cinema: {cinema}",
            f"targetUrl: {TARGET_URL}",
            f"requestTimeout: {REQUEST_TIMEOUT}",
            f"secretsFile: {configured_secrets_path}",
            f"chromeBinary: {chrome_binary}",
            f"chromedriverPath: {chromedriver_path}",
        )
    )


async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    await context.bot.send_message(chat_id=data["chatNacho"], text=format_runtime_config())


async def stop_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global runScrapper
    runScrapper = 0

    for job in context.job_queue.get_jobs_by_name(SCRAPPER_JOB_NAME):
        job.schedule_removal()

    await context.bot.send_message(
        chat_id=data["chatNacho"],
        text=f"RunScrapper: {runScrapper} se paró la ejecución de scrapper",
    )


async def start_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global runScrapper
    runScrapper = 1

    if not context.job_queue.get_jobs_by_name(SCRAPPER_JOB_NAME):
        context.job_queue.run_repeating(
            scrapper_auto,
            interval=60.0,
            first=0.0,
            name=SCRAPPER_JOB_NAME,
        )

    await context.bot.send_message(
        chat_id=data["chatNacho"],
        text=f"RunScrapper: {runScrapper} comenzó ejecución de scrapper",
    )


async def update_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await context.bot.send_message(chat_id=data["chatNacho"], text="Uso: /updateMovie <pelicula>")
        return

    global movie
    movie = " ".join(context.args).strip().lower()
    await context.bot.send_message(chat_id=data["chatNacho"], text=f"movie actualizada a: {movie}")


async def update_cinema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await context.bot.send_message(chat_id=data["chatNacho"], text="Uso: /updateCinema <cine>")
        return

    global cinema
    cinema = context.args[0].strip()
    await context.bot.send_message(chat_id=data["chatNacho"], text=f"cinema actualizada a: {cinema}")


async def get_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    try:
        response = requests.get("https://api.ipify.org", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except RequestException as exc:
        LOGGER.warning("Could not fetch public IP: %s", exc)
        await context.bot.send_message(chat_id=data["chatNacho"], text="No pude obtener la IP pública.")
        return

    await context.bot.send_message(chat_id=data["chatNacho"], text=response.text)


async def scrapper_auto(context: ContextTypes.DEFAULT_TYPE):
    if runScrapper != 1:
        return

    driver = None
    try:
        driver = build_driver()
        driver.get(TARGET_URL)

        cinema_dropdown = Select(driver.find_element(By.ID, "ctl00_Contenido_lstCinemaFull"))
        cinema_dropdown.select_by_value(cinema)

        movies_locator = (By.ID, "ctl00_Contenido_lstMovies")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located(movies_locator))
        movies_dropdown = driver.find_element(*movies_locator)
        movie_options = movies_dropdown.find_elements(By.TAG_NAME, "option")

        movie_title = next(
            (option.text for option in movie_options if movie.lower() in option.text.lower()),
            "",
        )

        if movie_title:
            result = f"Hay entradas para {movie_title} {TARGET_URL}"
            LOGGER.info("Movie found: %s", movie_title)
            await context.bot.send_message(chat_id=data["chatPibes"], text=result)
    except Exception:
        LOGGER.exception("Error trayendo datos del sitio de cine")
    finally:
        if driver is not None:
            driver.quit()


def send_message(message: str):
    url = f"https://api.telegram.org/bot{data['botToken2']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except RequestException:
        LOGGER.exception("Could not send startup message to Telegram")


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    application = ApplicationBuilder().token(data["botToken2"]).build()

    application.add_handler(CommandHandler("getIp", get_ip))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("viewConfig", view_config))
    application.add_handler(CommandHandler("startScrapper", start_scrapper_auto))
    application.add_handler(CommandHandler("stopScrapper", stop_scrapper_auto))
    application.add_handler(CommandHandler("updateMovie", update_movie))
    application.add_handler(CommandHandler("updateCinema", update_cinema))

    send_message("Movie Scrapper Bot has just Started")
    application.run_polling()


if __name__ == '__main__':
    main()
