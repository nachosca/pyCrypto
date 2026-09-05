import ast
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import requests
from requests import RequestException
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

LOGGER = logging.getLogger(__name__)
API_BASE_URL = "https://api.voyalcine.net"
STATE_FILE = Path(__file__).with_name("cine_scrapper_state.json")
SCRAPPER_JOB_NAME = "scrapper_auto"
CHECK_INTERVAL_SECONDS = 60.0
REQUEST_TIMEOUT = 15
IMAX_TREE_ID = "3250"


data = ast.literal_eval(Path(__file__).with_name("secrets.txt").read_text(encoding="utf-8"))
AUTHORIZED_CHAT_IDS = {data["chatNacho"]}
runScrapper = False


def default_state() -> dict:
    return {"version": 1, "initialized": False, "known_films": {}, "selected_films": [], "selected_cinemas": [], "showtimes": {}}


def load_state() -> dict:
    if not STATE_FILE.exists():
        return default_state()
    try:
        with STATE_FILE.open(encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("No pude leer el estado %s: %s", STATE_FILE, exc)
        return default_state()
    result = default_state()
    result.update(state)
    return result


def save_state(state: dict) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f"{STATE_FILE.stem}-", suffix=".tmp", dir=STATE_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(temp_name, STATE_FILE)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def is_authorized(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id in AUTHORIZED_CHAT_IDS)


def api_get(path: str):
    response = requests.get(f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError(f"Unexpected API response for {path}")
    return payload


def active_items(payload: list, active_key: str) -> dict[str, dict]:
    return {str(item["id"]): item for item in payload if isinstance(item, dict) and item.get(active_key, True) and item.get("id") is not None}


def tree_cinema_id(cinema: dict) -> str:
    if "imax" in str(cinema.get("ciN_Name", "")).lower():
        return IMAX_TREE_ID
    if cinema.get("ciN_EwaveId") is None:
        raise ValueError(f"Cinema {cinema.get('id')} has no ciN_EwaveId")
    return str(cinema["ciN_EwaveId"])


def normalize_showtimes(payload: dict) -> dict[str, list[dict[str, str]]]:
    normalized = {}
    for day, cinemas in (payload.get("days") or {}).items():
        entries = []
        for cinema in cinemas or []:
            for movie_format in cinema.get("formats") or []:
                format_name = str(movie_format.get("formatDescription") or "Sin formato")
                for performance in movie_format.get("performances") or []:
                    if performance.get("showTime"):
                        entries.append({"format": format_name, "time": str(performance["showTime"])})
        if entries:
            pairs = sorted({(item["format"], item["time"]) for item in entries})
            normalized[day] = [{"format": fmt, "time": time} for fmt, time in pairs]
    return normalized


def showtime_changes(previous: dict, current: dict) -> tuple[list[str], list[str]]:
    previous_items = {(day, item["format"], item["time"]) for day, items in previous.items() for item in items}
    current_items = {(day, item["format"], item["time"]) for day, items in current.items() for item in items}
    return (
        sorted("{} {} {}".format(*item) for item in current_items - previous_items),
        sorted("{} {} {}".format(*item) for item in previous_items - current_items),
    )


def format_change_message(film: dict, cinema: dict, added: list[str], removed: list[str]) -> str:
    lines = [f"Cambios en {film['name']} - {cinema['ciN_Name']}"]
    if added:
        lines.append("Agregados:\n" + "\n".join(f"+ {item}" for item in added))
    if removed:
        lines.append("Eliminados:\n" + "\n".join(f"- {item}" for item in removed))
    return "\n".join(lines)


def format_initial_schedule_message(film: dict, cinema: dict, showtimes: dict) -> str:
    lines = [f"Horarios actuales de {film['name']} - {cinema['ciN_Name']}"]
    if not showtimes:
        lines.append("No hay funciones disponibles.")
        return "\n".join(lines)

    for day, entries in showtimes.items():
        lines.append(day + ":")
        lines.extend(f"  {entry['time']} ({entry['format']})" for entry in entries)
    return "\n".join(lines)


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await send(update, context, "\n".join((
        "/cinemas - lista cines activos", "/films [texto] - lista películas activas",
        "/addFilm <id> /removeFilm <id>", "/addCinema <id> /removeCinema <id>",
        "/subscriptions - muestra la selección actual", "/clearFilms /clearCinemas - limpia selecciones",
        "/viewConfig - muestra el estado", "/startScrapper /stopScrapper - activa o detiene el monitor",
    )))


async def list_cinemas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    try:
        cinemas = active_items(await asyncio.to_thread(api_get, "/cinemas"), "ciN_Active")
        text = "\n".join(f"{cinema_id}: {cinema['ciN_Name']}" for cinema_id, cinema in sorted(cinemas.items())) or "No hay cines activos."
        await send(update, context, text)
    except (RequestException, ValueError) as exc:
        LOGGER.warning("No pude listar cines: %s", exc)
        await send(update, context, "No pude obtener los cines.")


async def list_films(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    search = " ".join(context.args).strip().lower()
    try:
        films = active_items(await asyncio.to_thread(api_get, "/films/"), "dB_Active")
        selected = [film for film in films.values() if not search or search in film["name"].lower()]
        text = "\n".join(f"{film['id']}: {film['name']}" for film in sorted(selected, key=lambda item: item["name"].lower())) or "No encontré películas."
        await send(update, context, text)
    except (RequestException, ValueError) as exc:
        LOGGER.warning("No pude listar películas: %s", exc)
        await send(update, context, "No pude obtener las películas.")


async def notify_new_subscriptions(state: dict, kind: str, added_ids: list[str], context: ContextTypes.DEFAULT_TYPE) -> None:
    if not added_ids:
        return

    films = active_items(await asyncio.to_thread(api_get, "/films/"), "dB_Active")
    cinemas = active_items(await asyncio.to_thread(api_get, "/cinemas"), "ciN_Active")
    film_ids = added_ids if kind == "films" else state["selected_films"]
    cinema_ids = added_ids if kind == "cinemas" else state["selected_cinemas"]
    notifications = []

    for film_id in film_ids:
        film = films.get(str(film_id))
        if not film:
            continue
        for cinema_id in cinema_ids:
            cinema = cinemas.get(str(cinema_id))
            if not cinema:
                continue
            key = f"{film_id}:{cinema_id}"
            payload = await asyncio.to_thread(api_get, f"/films/{film_id}/tree/{tree_cinema_id(cinema)}")
            current = normalize_showtimes(payload)
            state["showtimes"][key] = current
            notifications.append(format_initial_schedule_message(film, cinema, current))

    if notifications:
        save_state(state)
        for notification in notifications:
            await context.bot.send_message(chat_id=data["chatNacho"], text=notification)


async def change_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, add: bool):
    if not is_authorized(update):
        return
    command = "add" if add else "remove"
    noun = "Film" if kind == "films" else "Cinema"
    if not context.args or any(not argument.isdigit() for argument in context.args):
        await send(update, context, f"Uso: /{command}{noun} <id> [id...]")
        return
    try:
        payload = await asyncio.to_thread(api_get, "/films/" if kind == "films" else "/cinemas")
        available = active_items(payload, "dB_Active") if kind == "films" else active_items(payload, "ciN_Active")
    except (RequestException, ValueError) as exc:
        LOGGER.warning("No pude validar selección: %s", exc)
        await send(update, context, "No pude validar el catálogo.")
        return
    state = load_state()
    current = set(state[f"selected_{kind}"])
    valid = [str(argument) for argument in context.args if str(argument) in available]
    invalid = [str(argument) for argument in context.args if str(argument) not in available]
    if add:
        current.update(valid)
    else:
        current.difference_update(valid)
    state[f"selected_{kind}"] = sorted(current, key=int)
    save_state(state)
    if add:
        try:
            await notify_new_subscriptions(state, kind, valid, context)
        except (RequestException, ValueError, KeyError) as exc:
            LOGGER.warning("No pude obtener los horarios de la nueva suscripción: %s", exc)
    message = f"Selección {kind} {'agregadas' if add else 'quitadas'}: {', '.join(valid) or 'ninguna'}"
    if invalid:
        message += f"\nIDs inválidos: {', '.join(invalid)}"
    await send(update, context, message)


async def subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    state = load_state()
    await send(update, context, "Películas: {}\nCines: {}".format(
        ", ".join(state["selected_films"]) or "ninguna", ", ".join(state["selected_cinemas"]) or "ninguno",
    ))


async def clear_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
    if not is_authorized(update):
        return
    state = load_state()
    state[f"selected_{kind}"] = []
    save_state(state)
    await send(update, context, f"Selección de {kind} limpiada.")


async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    state = load_state()
    await send(update, context, "\n".join((
        f"runScrapper: {runScrapper}", f"películas seleccionadas: {len(state['selected_films'])}",
        f"cines seleccionados: {len(state['selected_cinemas'])}", f"estado inicializado: {state['initialized']}",
        f"intervalo: {CHECK_INTERVAL_SECONDS:g}s",
    )))


async def stop_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    global runScrapper
    runScrapper = False
    for job in context.job_queue.get_jobs_by_name(SCRAPPER_JOB_NAME):
        job.schedule_removal()
    await send(update, context, "Monitor de cine detenido.")


async def start_scrapper_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    global runScrapper
    runScrapper = True
    if not context.job_queue.get_jobs_by_name(SCRAPPER_JOB_NAME):
        context.job_queue.run_repeating(scrapper_auto, interval=CHECK_INTERVAL_SECONDS, first=0, name=SCRAPPER_JOB_NAME)
    await send(update, context, "Monitor de cine iniciado.")


async def scrapper_auto(context: ContextTypes.DEFAULT_TYPE):
    if not runScrapper:
        return
    try:
        films = active_items(await asyncio.to_thread(api_get, "/films/"), "dB_Active")
        cinemas = active_items(await asyncio.to_thread(api_get, "/cinemas"), "ciN_Active")
        state = load_state()
        previous_films = state["known_films"]
        new_films = [film for film_id, film in films.items() if film_id not in previous_films]
        state["known_films"] = {film_id: film["name"] for film_id, film in films.items()}
        notifications = [] if not state["initialized"] else [f"Nueva película: {film['name']} (ID {film['id']})" for film in new_films]
        for film_id in state["selected_films"]:
            film = films.get(str(film_id))
            if not film:
                continue
            for cinema_id in state["selected_cinemas"]:
                cinema = cinemas.get(str(cinema_id))
                if not cinema:
                    continue
                key = f"{film_id}:{cinema_id}"
                payload = await asyncio.to_thread(api_get, f"/films/{film_id}/tree/{tree_cinema_id(cinema)}")
                current = normalize_showtimes(payload)
                has_previous = key in state["showtimes"]
                previous = state["showtimes"].get(key, {})
                added, removed = showtime_changes(previous, current)
                if state["initialized"] and not has_previous:
                    notifications.append(format_initial_schedule_message(film, cinema, current))
                elif state["initialized"] and (added or removed):
                    notifications.append(format_change_message(film, cinema, added, removed))
                state["showtimes"][key] = current
        state["initialized"] = True
        save_state(state)
        for notification in notifications:
            await context.bot.send_message(chat_id=data["chatNacho"], text=notification)
    except (RequestException, ValueError, KeyError) as exc:
        LOGGER.warning("Error actualizando el monitor de cine: %s", exc)


async def send_startup_message(application):
    try:
        await application.bot.send_message(chat_id=data["chatNacho"], text="Movie Scrapper Bot has just Started")
    except TelegramError:
        LOGGER.exception("Could not send startup message to Telegram")


def main():
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    application = ApplicationBuilder().token(data["botToken2"]).post_init(send_startup_message).build()
    handlers = {
        "help": help_command, "cinemas": list_cinemas, "films": list_films,
        "addFilm": lambda update, context: change_selection(update, context, "films", True),
        "removeFilm": lambda update, context: change_selection(update, context, "films", False),
        "addCinema": lambda update, context: change_selection(update, context, "cinemas", True),
        "removeCinema": lambda update, context: change_selection(update, context, "cinemas", False),
        "subscriptions": subscriptions, "clearFilms": lambda update, context: clear_selection(update, context, "films"),
        "clearCinemas": lambda update, context: clear_selection(update, context, "cinemas"), "viewConfig": view_config,
        "startScrapper": start_scrapper_auto, "stopScrapper": stop_scrapper_auto,
    }
    for command, handler in handlers.items():
        application.add_handler(CommandHandler(command, handler))
    application.run_polling()


if __name__ == "__main__":
    main()