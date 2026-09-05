import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from telegram.error import Conflict, NetworkError
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

SECRETS_ENV_VAR = "FIGU_SCRAPPER_SECRETS_FILE"
ENABLE_POLLING_ENV_VAR = "FIGU_SCRAPPER_ENABLE_POLLING"
DEFAULT_SECRETS_PATHS = (
    Path(__file__).with_name("secrets.txt"),
    Path("/home/ubuntu/secrets.txt"),
    Path("/home/pi/secrets.txt"),
)

ZONAKIDS_URL = "https://zonakids.com/productos/colecciones-2026/fifa-world-cup-2026"
TARGET_URL = ZONAKIDS_URL  # backward compat alias
MELI_PRODUCT_URLS = [
    "https://articulo.mercadolibre.com.ar/MLA-1771170583-album-tapa-dura-panini-mundial-fifa-2026-tienda-oficial-_JM",
    "https://articulo.mercadolibre.com.ar/MLA-3346142478-album-tapa-dorada-panini-copa-mundial-fifa-2026-_JM",
]
JOB_NAME = "zonakids-change-monitor"
CHECK_INTERVAL_SECONDS = 90.0
REQUEST_TIMEOUT = 30
STATE_FILE = Path(__file__).with_name("zonakids_2026_state.json")
_MLA_ID_RE = re.compile(r"MLA-?(\d+)")
MELI_PRODUCT_STATE_FILES = {
    url: Path(__file__).with_name("meli_product_" + _MLA_ID_RE.search(url).group(1) + "_state.json")
    for url in MELI_PRODUCT_URLS
}
FINGERPRINT_VERSION = 4
SKIPPED_FINGERPRINT_TAGS = {"script", "style", "noscript", "template"}
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

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


def normalize_attribute(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(item) for item in value)
    return normalize_text(str(value))


def normalize_class_attribute(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        classes = [normalize_text(str(item)) for item in value if normalize_text(str(item))]
        return " ".join(sorted(dict.fromkeys(classes)))
    return normalize_text(str(value))


def normalize_price(value):
    cleaned = normalize_text(value)
    if not cleaned:
        return ""
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace("\u00a0", "")
    return cleaned


def infer_status(text):
    lowered = normalize_text(text).lower()
    if not lowered:
        return ""
    if (
        "avisame" in lowered
        or "av\u00edsame" in lowered
        or "agotado" in lowered
        or "agotada" in lowered
        or "sin stock" in lowered
        or "no disponible" in lowered
        or "disabled" in lowered
    ):
        return "sin_stock"
    if (
        "agregar al carrito" in lowered
        or "anadir al carrito" in lowered
        or "a\u00f1adir al carrito" in lowered
        or "comprar" in lowered
    ):
        return "disponible"
    return lowered


def extract_status_text(product_node):
    raw_candidates = []
    status_selectors = [
        ".actions-primary button",
        ".actions-primary .action",
        ".stock",
        ".availability",
        ".product-item-actions button",
        ".product-item-actions .action",
    ]

    for selector in status_selectors:
        for node in product_node.select(selector):
            class_value = normalize_class_attribute(node.get("class"))
            if class_value:
                raw_candidates.append(class_value)

            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                raw_candidates.append(text)

            for attr in ("value", "aria-label", "title", "data-label", "data-testid"):
                attr_value = normalize_attribute(node.get(attr))
                if attr_value:
                    raw_candidates.append(attr_value)

    unique_candidates = []
    for candidate in raw_candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)

    priority_keywords = [
        "av\u00edsame",
        "avisame",
        "sin stock",
        "agotado",
        "agotada",
        "no disponible",
        "disabled",
        "agregar al carrito",
        "a\u00f1adir al carrito",
        "anadir al carrito",
        "comprar",
    ]
    for candidate in unique_candidates:
        lowered = candidate.lower()
        if any(keyword in lowered for keyword in priority_keywords):
            return candidate

    return " | ".join(unique_candidates[:3])


def env_var_enabled(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_state(path=None):
    target_file = path if path is not None else STATE_FILE
    if not target_file.exists():
        return {}

    try:
        return json.loads(target_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state, path=None):
    target_file = path if path is not None else STATE_FILE
    target_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def truncate_text(value, limit=1200):
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def build_content_fingerprint(content_root):
    fingerprint_parts = []

    for node in content_root.descendants:
        tag_name = getattr(node, "name", None)

        if tag_name is None:
            text = normalize_text(str(node))
            if text:
                fingerprint_parts.append(f"text:{text}")
            continue

        if tag_name in SKIPPED_FINGERPRINT_TAGS:
            continue

        if tag_name == "a":
            href = normalize_attribute(node.get("href"))
            if href:
                fingerprint_parts.append(f"href:{href}")
            continue

        if tag_name == "input":
            input_type = normalize_attribute(node.get("type")).lower()
            if input_type == "hidden":
                continue

        if tag_name in {"button", "input", "option"}:
            class_value = normalize_class_attribute(node.get("class"))
            if class_value:
                fingerprint_parts.append(f"{tag_name}:class:{class_value}")

            label = normalize_attribute(
                node.get("value") or node.get("aria-label") or node.get("title")
            )
            if label:
                fingerprint_parts.append(f"{tag_name}:{label}")

            data_testid = normalize_attribute(node.get("data-testid"))
            if data_testid:
                fingerprint_parts.append(f"{tag_name}:data-testid:{data_testid}")

            if node.has_attr("disabled"):
                fingerprint_parts.append(f"{tag_name}:disabled")

    return "\n".join(fingerprint_parts)


def pick_catalog_content_root(soup):
    candidate_roots = [
        soup.select_one("main"),
        soup.select_one(".products.wrapper"),
        soup.select_one(".page-main"),
        soup.body,
        soup,
    ]

    best_root = None
    best_count = -1
    for candidate in candidate_roots:
        if candidate is None:
            continue

        product_count = len(candidate.select(".product-item, .item.product.product-item, li.product-item"))
        if product_count > best_count:
            best_root = candidate
            best_count = product_count

    return best_root or soup


def build_page_snapshot(html):
    soup = BeautifulSoup(html, "html.parser")
    content_root = pick_catalog_content_root(soup)
    fingerprint = build_content_fingerprint(content_root)

    title = ""
    title_node = soup.select_one(".page-main h1") or soup.select_one("h1")
    if title_node is not None:
        title = normalize_text(title_node.get_text(" ", strip=True))

    empty_message = ""
    for text in content_root.stripped_strings:
        cleaned_text = normalize_text(text)
        if "No podemos encontrar productos" in cleaned_text:
            empty_message = cleaned_text
            break

    products = []
    product_nodes = content_root.select(
        ".product-item, .item.product.product-item, li.product-item"
    )
    for product_node in product_nodes:
        name_node = (
            product_node.select_one(".product-item-link")
            or product_node.select_one(".product.name.product-item-name a")
            or product_node.select_one("h2 a")
            or product_node.select_one("a")
        )
        name = ""
        if name_node is not None:
            name = normalize_text(name_node.get_text(" ", strip=True))

        href = ""
        if name_node is not None:
            href = normalize_attribute(name_node.get("href"))
        if href:
            href = urljoin(TARGET_URL, href)

        price = ""
        price_node = product_node.select_one(".price-wrapper")
        if price_node is not None:
            amount = normalize_attribute(price_node.get("data-price-amount"))
            if amount:
                price = f"${amount}"

        if not price:
            for candidate in product_node.select(".price"):
                candidate_text = normalize_price(candidate.get_text(" ", strip=True))
                if candidate_text:
                    price = candidate_text
                    break

        status_text = extract_status_text(product_node)

        status = infer_status(status_text)

        product_key_source = href or name
        if not product_key_source:
            continue

        products.append(
            {
                "key": product_key_source,
                "name": name,
                "url": href,
                "price": price,
                "status": status,
                "status_text": status_text,
            }
        )

    if not products:
        product_lines = []
        for script in soup.select("script[type='application/ld+json']"):
            script_text = script.string or script.get_text(" ", strip=True)
            if not script_text:
                continue

            script_text = script_text.strip()
            try:
                payload = json.loads(script_text)
            except json.JSONDecodeError:
                continue

            candidates = payload if isinstance(payload, list) else [payload]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("@type") not in {"Product", "ItemList"}:
                    continue

                if candidate.get("@type") == "Product":
                    product_lines.append(candidate)
                else:
                    elements = candidate.get("itemListElement", [])
                    for element in elements:
                        if isinstance(element, dict):
                            item = element.get("item")
                            if isinstance(item, dict):
                                product_lines.append(item)

        for item in product_lines:
            name = normalize_text(str(item.get("name", "")))
            href = normalize_attribute(item.get("url"))
            if href:
                href = urljoin(TARGET_URL, href)

            offers = item.get("offers") if isinstance(item, dict) else None
            price = ""
            status = ""
            status_text = ""
            if isinstance(offers, dict):
                price = normalize_price(str(offers.get("price", "")))
                if price:
                    price = f"${price}"
                status_text = normalize_text(str(offers.get("availability", "")))
                status = infer_status(status_text)

            product_key_source = href or name
            if not product_key_source:
                continue

            products.append(
                {
                    "key": product_key_source,
                    "name": name,
                    "url": href,
                    "price": price,
                    "status": status,
                    "status_text": status_text,
                }
            )

    deduped_products = {}
    for product in products:
        key = product["key"]
        deduped_products[key] = product

    products = sorted(deduped_products.values(), key=lambda item: item["key"])

    products_count = None
    count_match = re.search(
        r"(\d+)\s+(productos|items)", content_root.get_text(" ", strip=True), flags=re.I
    )
    if count_match:
        products_count = int(count_match.group(1))

    summary_lines = []
    if title:
        summary_lines.append(f"titulo: {title}")
    if empty_message:
        summary_lines.append(f"estado: {empty_message}")
    if products_count is not None:
        summary_lines.append(f"cantidad: {products_count}")
    if products:
        summary_lines.extend(
            "producto: "
            + " | ".join(
                part
                for part in [
                    product.get("name", ""),
                    product.get("price", ""),
                    product.get("status") or product.get("status_text", ""),
                    product.get("url", ""),
                ]
                if part
            )
            for product in products
        )

    if not summary_lines:
        fallback_lines = []
        for text in content_root.stripped_strings:
            cleaned_text = normalize_text(text)
            if not cleaned_text:
                continue
            fallback_lines.append(cleaned_text)
            if len(fallback_lines) == 40:
                break
        summary_lines = fallback_lines

    summary = "\n".join(summary_lines)
    product_fingerprint_lines = [
        "|".join(
            [
                product.get("key", ""),
                product.get("name", ""),
                product.get("price", ""),
                product.get("status", ""),
                product.get("status_text", ""),
                product.get("url", ""),
            ]
        )
        for product in products
    ]
    # Only include the raw DOM fallback when no structured products were found.
    # Including it unconditionally causes ghost changes from dynamic page content
    # (tracking scripts, CSRF tokens, etc.) even when product data is identical.
    if products:
        digest_parts = [
            f"title:{title}",
            f"empty:{empty_message}",
            f"count:{len(products)}",
            *product_fingerprint_lines,
        ]
    else:
        digest_parts = [
            f"title:{title}",
            f"empty:{empty_message}",
            f"count:{products_count if products_count is not None else ''}",
            f"fallback:{fingerprint or summary}",
        ]
    digest_source = "\n".join(digest_parts)
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    return {
        "digest": digest,
        "summary": summary,
        "fingerprint_version": FINGERPRINT_VERSION,
        "products": products,
        "products_count": products_count,
    }


def fetch_page_snapshot():
    response = requests.get(TARGET_URL, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return build_page_snapshot(response.text)





def build_meli_product_snapshot(html, url):
    soup = BeautifulSoup(html, "html.parser")

    title_node = soup.select_one(".ui-pdp-title") or soup.select_one("h1")
    title = normalize_text(title_node.get_text(" ", strip=True)) if title_node is not None else ""

    price = ""
    fraction_node = soup.select_one(".andes-money-amount__fraction")
    if fraction_node is not None:
        fraction = normalize_price(fraction_node.get_text(" ", strip=True))
        if fraction:
            cents_node = soup.select_one(".andes-money-amount__cents")
            if cents_node is not None:
                price = f"${fraction},{normalize_price(cents_node.get_text(' ', strip=True))}"
            else:
                price = f"${fraction}"

    page_text = normalize_text(soup.get_text(" ", strip=True)).lower()
    status_text = ""
    if "este producto no est\u00e1 disponible" in page_text or "este producto no esta disponible" in page_text:
        status_text = "Este producto no est\u00e1 disponible"
    else:
        buy_button = (
            soup.select_one(".ui-pdp-action--primary")
            or soup.select_one("button.andes-button--loud")
        )
        if buy_button is not None:
            status_text = normalize_text(buy_button.get_text(" ", strip=True))
        if not status_text:
            for candidate in ["Agregar al carrito", "Comprar ahora", "Sin stock", "Agotado"]:
                if candidate.lower() in page_text:
                    status_text = candidate
                    break

    status = infer_status(status_text) if status_text else ""

    products = []
    if title or status:
        products.append({
            "key": url,
            "name": title,
            "url": url,
            "price": price,
            "status": status,
            "status_text": status_text,
        })

    summary_lines = []
    if title:
        summary_lines.append(f"titulo: {title}")
    if price:
        summary_lines.append(f"precio: {price}")
    if status or status_text:
        summary_lines.append(f"estado: {status or status_text}")
    summary_lines.append(f"url: {url}")
    summary = "\n".join(summary_lines)

    product_fingerprint_lines = [
        "|".join([p.get("key", ""), p.get("name", ""), p.get("price", ""), p.get("status", ""), p.get("status_text", "")])
        for p in products
    ]
    digest_source = "\n".join([
        f"title:{title}",
        f"status:{status}",
        f"price:{price}",
        *product_fingerprint_lines,
    ])
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    return {
        "digest": digest,
        "summary": summary,
        "fingerprint_version": FINGERPRINT_VERSION,
        "products": products,
        "products_count": len(products) if products else None,
    }


def _playwright_fetch_html(url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HTTP_HEADERS["User-Agent"],
            locale="es-AR",
            extra_http_headers={
                "Accept-Language": HTTP_HEADERS["Accept-Language"],
            },
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=REQUEST_TIMEOUT * 1000)
        try:
            html = page.content()
        except Exception:
            page.wait_for_timeout(3000)
            html = page.content()
        browser.close()
    return html


def fetch_meli_product_snapshot(url):
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        html = executor.submit(_playwright_fetch_html, url).result()
    return build_meli_product_snapshot(html, url)


def only_notify_stock_available(previous_snapshot, current_snapshot):
    previous_products = {p["key"]: p for p in previous_snapshot.get("products", []) if p.get("key")}
    current_products = {p["key"]: p for p in current_snapshot.get("products", []) if p.get("key")}
    for key, curr in current_products.items():
        prev = previous_products.get(key)
        if prev is None:
            continue
        prev_status = prev.get("status") or prev.get("status_text", "")
        curr_status = curr.get("status") or curr.get("status_text", "")
        if prev_status == "sin_stock" and curr_status == "disponible":
            return True
    return False


SCRAPE_TARGETS = [
    {
        "name": "Zonakids",
        "url": ZONAKIDS_URL,
        "state_file": STATE_FILE,
        "fetch": fetch_page_snapshot,
    },
    *[
        {
            "name": "MercadoLibre MLA" + _MLA_ID_RE.search(url).group(1),
            "url": url,
            "state_file": MELI_PRODUCT_STATE_FILES[url],
            "fetch": lambda u=url: fetch_meli_product_snapshot(u),
            "notify_filter": only_notify_stock_available,
            "silent_errors": True,
        }
        for url in MELI_PRODUCT_URLS
    ],
]


def format_change_message(previous_summary, current_summary):
    message = "Se detecto un cambio en Zonakids.\n"
    message += TARGET_URL
    if previous_summary == current_summary:
        message += "\n\nEl fingerprint del contenido cambio aunque el resumen textual quedo igual."
    message += "\n\nAntes:\n"
    message += truncate_text(previous_summary or "Sin estado guardado")
    message += "\n\nAhora:\n"
    message += truncate_text(current_summary)
    return message


def build_product_change_lines(previous_snapshot, current_snapshot):
    previous_products = {
        item.get("key"): item for item in previous_snapshot.get("products", []) if item.get("key")
    }
    current_products = {
        item.get("key"): item for item in current_snapshot.get("products", []) if item.get("key")
    }

    lines = []

    added_keys = sorted(set(current_products) - set(previous_products))
    removed_keys = sorted(set(previous_products) - set(current_products))
    shared_keys = sorted(set(previous_products) & set(current_products))

    for key in added_keys:
        product = current_products[key]
        lines.append(
            "Nuevo: "
            + " | ".join(
                part
                for part in [
                    product.get("name", ""),
                    product.get("price", ""),
                    product.get("status") or product.get("status_text", ""),
                ]
                if part
            )
        )

    for key in removed_keys:
        product = previous_products[key]
        lines.append(
            "Eliminado: "
            + " | ".join(
                part
                for part in [
                    product.get("name", ""),
                    product.get("price", ""),
                    product.get("status") or product.get("status_text", ""),
                ]
                if part
            )
        )

    for key in shared_keys:
        previous = previous_products[key]
        current = current_products[key]

        changes = []
        if previous.get("price", "") != current.get("price", ""):
            changes.append(f"precio {previous.get('price', '')} -> {current.get('price', '')}")

        previous_status = previous.get("status") or previous.get("status_text", "")
        current_status = current.get("status") or current.get("status_text", "")
        if previous_status != current_status:
            changes.append(f"estado {previous_status} -> {current_status}")

        if previous.get("name", "") != current.get("name", ""):
            changes.append(f"nombre {previous.get('name', '')} -> {current.get('name', '')}")

        if changes:
            lines.append(f"Actualizado: {current.get('name', key)} ({'; '.join(changes)})")

    previous_count = previous_snapshot.get("products_count")
    current_count = current_snapshot.get("products_count")
    if previous_count is not None and current_count is not None and previous_count != current_count:
        lines.append(f"Cantidad visible: {previous_count} -> {current_count}")

    return lines


def format_detailed_change_message(previous_snapshot, current_snapshot, url=None, site_name="Zonakids"):
    lines = [f"Se detecto un cambio en {site_name}.", url or TARGET_URL]

    change_lines = build_product_change_lines(previous_snapshot, current_snapshot)
    if change_lines:
        lines.append("")
        lines.append("Cambios detectados:")
        lines.extend(f"- {line}" for line in change_lines[:25])

    lines.append("")
    lines.append("Antes:")
    lines.append(truncate_text(previous_snapshot.get("summary", "") or "Sin estado guardado"))
    lines.append("")
    lines.append("Ahora:")
    lines.append(truncate_text(current_snapshot.get("summary", "")))
    return "\n".join(lines)


def get_jobs(context):
    if context.job_queue is None:
        return []
    return context.job_queue.get_jobs_by_name(JOB_NAME)


def evaluate_change_for(url, state_file, fetch_fn, site_name, notify_filter=None):
    current_snapshot = fetch_fn()
    previous_snapshot = load_state(state_file)
    can_compare_snapshots = (
        previous_snapshot.get("fingerprint_version") == current_snapshot["fingerprint_version"]
        and previous_snapshot.get("digest")
    )

    change_message = None
    if can_compare_snapshots and previous_snapshot["digest"] != current_snapshot["digest"]:
        if notify_filter is None or notify_filter(previous_snapshot, current_snapshot):
            change_message = format_detailed_change_message(previous_snapshot, current_snapshot, url, site_name)

    next_state = {
        "digest": current_snapshot["digest"],
        "summary": current_snapshot["summary"],
        "fingerprint_version": current_snapshot["fingerprint_version"],
        "products": current_snapshot.get("products", []),
        "products_count": current_snapshot.get("products_count"),
        "checked_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    return change_message, next_state


def run_scrapper_cycle(send_notification):
    for target in SCRAPE_TARGETS:
        try:
            change_message, next_state = evaluate_change_for(
                target["url"], target["state_file"], target["fetch"], target["name"],
                notify_filter=target.get("notify_filter"),
            )
            if change_message:
                send_notification(change_message)
            save_state(next_state, target["state_file"])
        except Exception as error:
            import traceback
            if not target.get("silent_errors"):
                send_notification(
                    f"Error revisando {target['name']}. Checkea manualmente: {target['url']}\n{traceback.format_exc()[-800:]}"
                )
            print(f"error en {target['name']}:")
            traceback.print_exc()


async def run_scrapper_cycle_async(send_notification):
    for target in SCRAPE_TARGETS:
        try:
            change_message, next_state = evaluate_change_for(
                target["url"], target["state_file"], target["fetch"], target["name"],
                notify_filter=target.get("notify_filter"),
            )
            if change_message:
                await send_notification(change_message)
            save_state(next_state, target["state_file"])
        except Exception as error:
            import traceback
            if not target.get("silent_errors"):
                await send_notification(
                    f"Error revisando {target['name']}. Checkea manualmente: {target['url']}\n{traceback.format_exc()[-800:]}"
                )
            print(f"error en {target['name']}:")
            traceback.print_exc()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help(update, context)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in [data["chatNacho"]]:
        txt = "/getIp - devuelve el ip del host"
        txt += chr(10)
        txt += "/startScrapper - empieza el monitor de cambios"
        txt += chr(10)
        txt += "/stopScrapper - para el monitor de cambios"
        txt += chr(10)
        txt += ZONAKIDS_URL
        for meli_url in MELI_PRODUCT_URLS:
            txt += chr(10)
            txt += meli_url
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
        async def send_async_notification(message):
            await context.bot.send_message(chat_id=data["chatNacho"], text=message)

        await run_scrapper_cycle_async(send_async_notification)
    except Exception as error:
        await context.bot.send_message(
            chat_id=data["chatNacho"],
            text="Error revisando Zonakids. Checkea manualmente: " + TARGET_URL,
        )
        print("error trayendo datos.")
        print(error)


def send_message(message):
    url = f"https://api.telegram.org/bot{data['botScrapperToken']}/sendMessage"
    params = {"chat_id": data["chatNacho"], "text": message}
    requests.get(url, params=params, timeout=REQUEST_TIMEOUT)


async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    print("telegram runtime error:")
    print(error)

    if isinstance(error, NetworkError):
        return


def run_autonomous_monitor():
    global runScrapper

    runScrapper = 1
    send_message("Figu Scrapper Bot started. Monitoreando: Zonakids + 2 productos MercadoLibre (modo autonomo).")

    while True:
        if runScrapper == 1:
            try:
                run_scrapper_cycle(send_message)
            except Exception as error:
                send_message("Error revisando Zonakids. Checkea manualmente: " + TARGET_URL)
                print("error trayendo datos.")
                print(error)

        time.sleep(CHECK_INTERVAL_SECONDS)


def run_polling_bot():
    global runScrapper

    application = ApplicationBuilder().token(data["botScrapperToken"]).build()

    application.add_error_handler(telegram_error_handler)
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
        send_message("Figu Scrapper Bot started. Monitoreando: Zonakids + 2 productos MercadoLibre.")

    try:
        application.run_polling(bootstrap_retries=5)
    except Conflict:
        # Another process is consuming getUpdates for this token.
        # Keep change monitoring alive in autonomous mode to avoid silent downtime.
        send_message(
            "Conflicto de polling detectado (otra instancia usa getUpdates). "
            "Cambio a modo autonomo para mantener monitoreo de Zonakids."
        )
        run_autonomous_monitor()
    except NetworkError:
        send_message(
            "Telegram devolvio un error de red temporal durante polling. "
            "Cambio a modo autonomo para mantener monitoreo."
        )
        run_autonomous_monitor()


def main():
    if env_var_enabled(ENABLE_POLLING_ENV_VAR):
        run_polling_bot()
        return

    run_autonomous_monitor()


if __name__ == '__main__':
    main()
