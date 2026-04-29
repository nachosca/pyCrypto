import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

SECRETS_ENV_VAR = "FIGU_SCRAPPER_SECRETS_FILE"
DEFAULT_SECRETS_PATHS = (
    Path(__file__).with_name("secrets.txt"),
    Path("/home/ubuntu/secrets.txt"),
    Path("/home/pi/secrets.txt"),
)

TARGET_URL = "https://zonakids.com/productos/colecciones-2026/fifa-world-cup-2026"
JOB_NAME = "zonakids-change-monitor"
CHECK_INTERVAL_SECONDS = 90.0
REQUEST_TIMEOUT = 30
STATE_FILE = Path(__file__).with_name("zonakids_2026_state.json")

runScrapper = 0


def load_config():
    configured_path = os.getenv(SECRETS_ENV_VAR)
    candidate_paths = []

    if configured_path:
        candidate_paths.append(Path(configured_path).expanduser())

    candidate_paths.extend(DEFAULT_SECRETS_PATHS)

    for candidate_path in candidate_paths:
        if not candidate_path.is_file():
            continue

        with candidate_path.open(encoding="utf-8") as filedata:
            return ast.literal_eval(filedata.read())

    searched_paths = ", ".join(str(path) for path in candidate_paths)
    raise FileNotFoundError(
        f"Could not find secrets file. Checked: {searched_paths}. "
        f"Set {SECRETS_ENV_VAR} to override the location."
    )


data = load_config()


def normalize_text(value):
    return " ".join(value.split())


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def truncate_text(value, limit=1200):
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def build_page_snapshot(html):
    soup = BeautifulSoup(html, "html.parser")
    content_root = soup.select_one(".page-main") or soup.select_one("main") or soup.body or soup

    title = ""
    title_node = content_root.select_one("h1")
    if title_node is not None:
        title = normalize_text(title_node.get_text(" ", strip=True))

    empty_message = ""
    for text in content_root.stripped_strings:
        cleaned_text = normalize_text(text)
        if "No podemos encontrar productos" in cleaned_text:
            empty_message = cleaned_text
            break

    products = []
    for product_node in content_root.select(".product-item, .item.product.product-item"):
        parts = []
        for text in product_node.stripped_strings:
            cleaned_text = normalize_text(text)
            if cleaned_text and cleaned_text not in parts:
                parts.append(cleaned_text)
        if parts:
            products.append(" | ".join(parts))

    summary_lines = []
    if title:
        summary_lines.append(f"titulo: {title}")
    if empty_message:
        summary_lines.append(f"estado: {empty_message}")
    if products:
        summary_lines.extend(f"producto: {product}" for product in products)

    if not summary_lines:
        fallback_lines = []
        for text in content_root.stripped_strings:
            cleaned_text = normalize_text(text)
            if not cleaned_text:
                continue
            fallback_lines.append(cleaned_text)
            if len(fallback_lines) == 15:
                break
        summary_lines = fallback_lines

    summary = "\n".join(summary_lines)
    digest = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    return {"digest": digest, "summary": summary}


def fetch_page_snapshot():
    response = requests.get(TARGET_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return build_page_snapshot(response.text)


def format_change_message(previous_summary, current_summary):
    message = "Se detecto un cambio en Zonakids.\n"
    message += TARGET_URL
    message += "\n\nAntes:\n"
    message += truncate_text(previous_summary or "Sin estado guardado")
    message += "\n\nAhora:\n"
    message += truncate_text(current_summary)
    return message


def get_jobs(context):
    if context.job_queue is None:
        return []
    return context.job_queue.get_jobs_by_name(JOB_NAME)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help(update, context)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        txt = "/getIp - devuelve el ip del host"
        txt += chr(10)
        txt += "/startScrapper - empieza el monitor de cambios de Zonakids"
        txt += chr(10)
        txt += "/stopScrapper - para el monitor de cambios"
        txt += chr(10)
        txt += TARGET_URL
        await context.bot.send_message(chat_id=data["chatNacho"], text=txt)


async def stop_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        global runScrapper
        runScrapper = 0

        for job in get_jobs(context):
            job.schedule_removal()

        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Runfutures: " + str(runScrapper) + " se paro la ejecucion del monitor de Zonakids",
        )


async def start_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        if context.job_queue is None:
            await context.bot.send_message(
                chat_id=data["chatNacho"],
                text="JobQueue no configurado. Instala python-telegram-bot[job-queue] y reinicia.",
            )
            return

        global runScrapper
        runScrapper = 1

        for job in get_jobs(context):
            job.schedule_removal()

        context.job_queue.run_repeating(
            scrapper_auto,
            interval=CHECK_INTERVAL_SECONDS,
            first=0.0,
            name=JOB_NAME,
        )
        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Runfutures: " + str(runScrapper) + " comenzo el monitor de cambios de Zonakids",
        )


async def get_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        ip = requests.get("https://api.ipify.org", timeout=REQUEST_TIMEOUT).content.decode("utf8")
        await context.bot.send_message(chat_id=data["chatNacho"], text=ip)


async def scrapper_auto(context: ContextTypes.DEFAULT_TYPE):
    if runScrapper != 1:
        return

    try:
        current_snapshot = fetch_page_snapshot()
        previous_snapshot = load_state()

        if previous_snapshot.get("digest") and previous_snapshot["digest"] != current_snapshot["digest"]:
            await context.bot.send_message(
                chat_id=data["chatNacho"],
                text=format_change_message(previous_snapshot.get("summary", ""), current_snapshot["summary"]),
            )

        save_state(
            {
                "digest": current_snapshot["digest"],
                "summary": current_snapshot["summary"],
                "checked_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            }
        )
    except Exception as error:
        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Error revisando Zonakids. Checkea manualmente: " + TARGET_URL,
        )
        print("error trayendo datos.")
        print(error)


def send_message(message):
    url = f"https://api.telegram.org/bot{data['botToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}
    requests.get(url, params=params, timeout=REQUEST_TIMEOUT)


def main():
    global runScrapper

    application = ApplicationBuilder().token(data["botToken"]).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("getIp", get_ip))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("startScrapper", start_scrapper_auto))
    application.add_handler(CommandHandler("stopScrapper", stop_scrapper_auto))

    if application.job_queue is None:
        send_message("Figu Scrapper Bot started, pero JobQueue no esta disponible.")
    else:
        runScrapper = 1
        application.job_queue.run_repeating(
            scrapper_auto,
            interval=CHECK_INTERVAL_SECONDS,
            first=0.0,
            name=JOB_NAME,
        )
        send_message("Figu Scrapper Bot has just started y el monitor de Zonakids quedo activo.")

    application.run_polling()


if __name__ == '__main__':
    main()
