from contextlib import asynccontextmanager
from html import escape
import logging
from fastapi import FastAPI, Request, Response
import httpx
import os

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

http_client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient()
    log.info("started")
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

TELEGRAM_MAX_LENGTH = 4096


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/webhook/sentry")
async def sentry_webhook(req: Request):
    try:
        data = await req.json()
    except Exception:
        log.exception("failed to parse sentry payload")
        return Response(content="invalid json", status_code=400)
    log.debug("sentry payload: %s", data)
    text = _format_sentry(data)
    return await _send(text)


@app.post("/webhook/raw")
async def raw_webhook(req: Request):
    try:
        data = await req.json()
    except Exception:
        log.exception("failed to parse raw payload")
        return Response(content="invalid json", status_code=400)
    log.debug("raw payload: %s", data)
    text = data.get("text") or data.get("message") or str(data)
    return await _send(text)


async def _send(text: str):
    if len(text) > TELEGRAM_MAX_LENGTH:
        text = text[: TELEGRAM_MAX_LENGTH - 1] + "\u2026"
    resp = await http_client.post(
        TELEGRAM_API,
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
    )
    if resp.status_code != 200:
        log.error("telegram error %s: %s", resp.status_code, resp.text)
        return Response(content=resp.text, status_code=502)
    log.info("sent: %s", text[:120])
    return {"ok": True}


def _format_sentry(data: dict) -> str:
    event = data.get("data", {}).get("event", data.get("event"))

    # Issue alerts
    if isinstance(event, dict):
        metadata = event.get("metadata", {})
        error_type = escape(metadata.get("type", event.get("title", "No title")))
        error_value = escape(metadata.get("value", ""))
        rule = escape(data.get("data", {}).get("triggered_rule", ""))
        url = event.get("web_url", data.get("url", ""))
        parts = [f'<b>{error_type}</b> (<a href="{url}">link</a>)' if url else f"<b>{error_type}</b>"]
        if error_value:
            parts.append(f"<i>{error_value}</i>")
        if rule:
            parts.append(rule)
        return "\n".join(parts)

    # Metric alerts
    if "metric_alert" in data:
        alert = data["metric_alert"]
        title = escape(alert.get("title", "Metric alert"))
        status = escape(data.get("description_title", ""))
        text = escape(data.get("description_text", ""))
        parts = [f"<b>{title}</b>"]
        if status:
            parts.append(status)
        if text:
            parts.append(text)
        return "\n".join(parts)

    # Fallback
    message = data.get("message") or data.get("text")
    if message:
        return escape(message)
    return escape(str(data))[:TELEGRAM_MAX_LENGTH]
