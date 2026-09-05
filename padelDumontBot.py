import ast
import asyncio
import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import urllib.request
from urllib.parse import urlencode
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

SECRETS_ENV_VAR = "PADEL_BOT_SECRETS_FILE"
DEFAULT_SECRETS_PATHS = (
    Path(__file__).with_name("secrets.txt"),
    Path("/home/ubuntu/secrets.txt"),
    Path("/home/pi/secrets.txt"),
)

STATE_FILE = Path(__file__).with_name("padel_dumont_state.json")
CHECK_INTERVAL_SECONDS = 300.0
# Mutable at runtime via /sethorario and /setdias
TARGET_HOURS = {"21:00"}
TARGET_WEEKDAYS = {1, 2, 3}  # Python weekday: Mon=0...Sun=6; defaults Tue/Wed/Thu
BOOKING_DAYS_AHEAD = 6

def build_venue_url(date_str: str, hour: str) -> str:
    return (
        "https://atcsports.com.ar/venues/dumont-padel-caba"
        f"?sportIds=7&placeId=69y7mcxhn&dia={date_str}&horario={hour.replace(':', '%3A')}"
        "&locationName=Colegiales%2C+Ciudad+Aut%C3%B3noma+de+Buenos+Aires%2C+Argentina"
        "&placeSearched=69y7mcxhn"
    )

ATC_API_BASE = "https://alquilatucancha.com/api/v3/availability/sportclubs"
SPORTCLUB_ID = "2034"
_ATC_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://atcsports.com.ar",
    "Referer": "https://atcsports.com.ar/",
}

# ── Secrets ────────────────────────────────────────────────────────────────────

def load_config():
    configured_path = os.getenv(SECRETS_ENV_VAR)
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path).expanduser())
    candidates.extend(DEFAULT_SECRETS_PATHS)

    for path in candidates:
        if path.is_file():
            logger.info("Secrets cargados desde %s", path)
            with path.open(encoding="utf-8") as f:
                return ast.literal_eval(f.read())

    raise FileNotFoundError(
        f"No se encontró el archivo de secrets. Revisados: {', '.join(str(p) for p in candidates)}. "
        f"Podés configurar la ruta con la variable {SECRETS_ENV_VAR}."
    )


data = load_config()

# ── State ──────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_seen": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Date helpers ───────────────────────────────────────────────────────────────

DAY_NAMES = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}


def get_target_dates() -> list[date]:
    today = date.today()
    return [td for d in range(1, BOOKING_DAYS_AHEAD + 1) if (td := today + timedelta(days=d)).weekday() in TARGET_WEEKDAYS]


def day_label(d: date) -> str:
    return f"{DAY_NAMES[d.weekday()]} {d.strftime('%d/%m')}"

# ── Scraping ───────────────────────────────────────────────────────────────────


def _parse_availability(body: dict, hour: str) -> list[str]:
    available = []
    for court in body.get("available_courts", []):
        for slot in court.get("available_slots", []):
            if f"T{hour}-" in slot.get("start", ""):
                available.append(court["name"])
                break
    return available


def _fetch_availability(date_str: str) -> dict:
    url = f"{ATC_API_BASE}/{SPORTCLUB_ID}?date={date_str}"
    req = urllib.request.Request(url, headers=_ATC_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _scrape_slots_sync(date_str: str, hour: str) -> list[str]:
    body = _fetch_availability(date_str)
    return _parse_availability(body, hour)

# ── ThreadPool wrapper (async-safe) ────────────────────────────────────────────

def scrape_all_slots(target_dates: list[date]) -> dict[str, list[str]]:
    """Scrapes each (date, hour) pair; keys are 'YYYY-MM-DD|HH:MM'."""
    results = {}
    for d in target_dates:
        ds = d.strftime("%Y-%m-%d")
        for hour in sorted(TARGET_HOURS):
            key = f"{ds}|{hour}"
            try:
                results[key] = _scrape_slots_sync(ds, hour)
                logger.info("Scrape %s %s -> %d canchas", ds, hour, len(results[key]))
            except Exception as e:
                logger.error("Error scrapeando %s %s: %s", ds, hour, e)
                results[key] = []
    return results

# ── Change detection ───────────────────────────────────────────────────────────

def detect_new_slots(current_by_slot: dict, state: dict) -> list[tuple[str, str, str]]:
    """Returns (date_str, hour, court_name) triples for newly available slots."""
    last_seen = state.get("last_seen", {})
    new_slots = []
    for slot_key, courts in current_by_slot.items():
        date_str, hour = slot_key.split("|", 1)
        prev = set(last_seen.get(slot_key, []))
        for court in sorted(set(courts) - prev):
            new_slots.append((date_str, hour, court))
    return new_slots


# ── Monitoring flag ────────────────────────────────────────────────────────────

monitoring_active = True

# ── Async job ──────────────────────────────────────────────────────────────────

async def job_check_padel(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not monitoring_active:
        return

    target_dates = get_target_dates()
    if not target_dates:
        return

    logger.info("Chequeando %d fechas: %s", len(target_dates), [d.isoformat() for d in target_dates])

    state = load_state()

    current_by_slot = await asyncio.to_thread(scrape_all_slots, target_dates)

    new_slots = detect_new_slots(current_by_slot, state)

    if new_slots:
        logger.info("Nuevos turnos encontrados: %s", new_slots)
    else:
        logger.info("Sin cambios")

    for date_str, hour, court in new_slots:
        d = date.fromisoformat(date_str)
        booking_url = build_venue_url(date_str, hour)
        text = (
            f"🎾 Turno disponible en Dumont Padel!\n"
            f"📅 {day_label(d)} a las {hour}\n"
            f"🏟 {court}\n"
            f"🔗 {booking_url}"
        )
        await context.bot.send_message(chat_id=data["chatNacho"], text=text)

    # Trim to keep only currently monitored (date, hour) combinations
    state["last_seen"] = current_by_slot
    save_state(state)

# ── Bot commands ───────────────────────────────────────────────────────────────

def _authorized(update: Update) -> bool:
    return update.effective_chat.id == data["chatNacho"]


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await context.bot.send_message(chat_id=data["chatNacho"], text="Chequeando disponibilidad...")
    await job_check_padel(context)
    await context.bot.send_message(chat_id=data["chatNacho"], text="✅ Chequeo terminado.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    target_dates = get_target_dates()
    state = load_state()
    last_seen = state.get("last_seen", {})

    hours_str = ", ".join(sorted(TARGET_HOURS))
    day_names_str = ", ".join(DAY_NAMES[d] for d in sorted(TARGET_WEEKDAYS))
    lines = [
        f"Monitor: {'▶️ activo' if monitoring_active else '⏸ pausado'}",
        f"Horarios: {hours_str}  |  Días: {day_names_str}",
        "",
    ]
    for d in target_dates:
        ds = d.strftime("%Y-%m-%d")
        for hour in sorted(TARGET_HOURS):
            key = f"{ds}|{hour}"
            courts = last_seen.get(key, [])
            icon = "✅" if courts else "❌"
            detail = ", ".join(courts) if courts else "sin disponibilidad"
            lines.append(f"{icon} {day_label(d)} {hour}: {detail}")

    if not target_dates:
        lines.append(f"No hay fechas configuradas dentro de los próximos {BOOKING_DAYS_AHEAD} días.")

    await context.bot.send_message(chat_id=data["chatNacho"], text="\n".join(lines))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    global monitoring_active
    monitoring_active = True
    if context.job_queue:
        # Remove existing job to avoid duplicates, then re-add
        for job in context.job_queue.get_jobs_by_name("padel_check"):
            job.schedule_removal()
        context.job_queue.run_repeating(
            job_check_padel, interval=CHECK_INTERVAL_SECONDS, first=1.0, name="padel_check"
        )
    await context.bot.send_message(chat_id=data["chatNacho"], text="▶️ Monitor iniciado.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    global monitoring_active
    monitoring_active = False
    await context.bot.send_message(chat_id=data["chatNacho"], text="⏸ Monitor pausado.")


async def cmd_setdias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    global TARGET_WEEKDAYS
    if not context.args:
        names = ", ".join(DAY_NAMES[d] for d in sorted(TARGET_WEEKDAYS))
        await context.bot.send_message(chat_id=data["chatNacho"], text=f"📅 Días actuales: {names}")
        return
    try:
        nums = [int(a) for a in context.args]
        if not nums or any(n < 1 or n > 7 for n in nums):
            raise ValueError
        TARGET_WEEKDAYS = {n - 1 for n in nums}
        names = ", ".join(DAY_NAMES[d] for d in sorted(TARGET_WEEKDAYS))
        logger.info("Días actualizados a: %s", names)
        await context.bot.send_message(chat_id=data["chatNacho"], text=f"📅 Días configurados: {names}")
    except (ValueError, IndexError):
        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Uso: /setdias 2 3 4  (1=Lunes, 2=Martes, ..., 7=Domingo)",
        )


async def cmd_sethorario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    global TARGET_HOURS
    if not context.args:
        hours_str = ", ".join(sorted(TARGET_HOURS))
        await context.bot.send_message(chat_id=data["chatNacho"], text=f"🕐 Horarios actuales: {hours_str}")
        return
    try:
        hours = set()
        for arg in context.args:
            h, m = arg.split(":")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                raise ValueError
            hours.add(f"{int(h):02d}:{int(m):02d}")
        if not hours:
            raise ValueError
        TARGET_HOURS = hours
        hours_str = ", ".join(sorted(TARGET_HOURS))
        logger.info("Horarios actualizados a: %s", hours_str)
        await context.bot.send_message(chat_id=data["chatNacho"], text=f"🕐 Horarios configurados: {hours_str}")
    except (ValueError, IndexError, AttributeError):
        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Uso: /sethorario 21:00 22:30",
        )


async def cmd_rawcheck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    target_dates = get_target_dates()
    if not target_dates:
        await context.bot.send_message(chat_id=data["chatNacho"], text="Sin fechas configuradas.")
        return
    d = target_dates[0]
    hour = sorted(TARGET_HOURS)[0]
    ds = d.strftime("%Y-%m-%d")
    await context.bot.send_message(chat_id=data["chatNacho"], text=f"🔍 Raw scrape {ds} {hour}...")
    try:
        body = await asyncio.to_thread(_fetch_availability, ds)
    except Exception as e:
        await context.bot.send_message(chat_id=data["chatNacho"], text=f"Error en scrape: {e}")
        return
    courts = body.get("available_courts", [])
    lines = [f"{len(courts)} canchas, slots para {hour}:"]
    for court in courts:
        slots_at_hour = [s["start"] for s in court.get("available_slots", []) if f"T{hour}-" in s.get("start", "")]
        lines.append(f"  {court['name']}: {'✅ ' + str(len(slots_at_hour)) + ' slots' if slots_at_hour else '❌ sin slot'}")
    await context.bot.send_message(chat_id=data["chatNacho"], text="\n".join(lines))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    txt = (
        "/check            — forzar un chequeo ahora\n"
        "/status           — ver próximas fechas y disponibilidad\n"
        "/stop             — pausar el monitor automático\n"
        "/start            — reanudar el monitor automático\n"
        "/setdias 2 3 4    — configurar días (1=Lun...7=Dom)\n"
        "/sethorario 21:00 22:30 — configurar horarios a monitorear\n"
        "/rawcheck         — ver estructura JSON cruda de la API"
    )
    await context.bot.send_message(chat_id=data["chatNacho"], text=txt)

# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    application = ApplicationBuilder().token(data["padelBotToken"]).job_queue(JobQueue()).build()

    application.add_handler(CommandHandler("check", cmd_check))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("setdias", cmd_setdias))
    application.add_handler(CommandHandler("sethorario", cmd_sethorario))
    application.add_handler(CommandHandler("rawcheck", cmd_rawcheck))

    application.job_queue.run_repeating(
        job_check_padel, interval=CHECK_INTERVAL_SECONDS, first=10.0, name="padel_check"
    )

    _url = f"https://api.telegram.org/bot{data['padelBotToken']}/sendMessage?" + urlencode({"chat_id": data["chatNacho"], "text": "🎾 Padel Dumont Bot iniciado"})
    urllib.request.urlopen(_url, timeout=10)

    logger.info("Bot iniciado, polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
