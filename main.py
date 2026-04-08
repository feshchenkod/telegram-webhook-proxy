from contextlib import asynccontextmanager
from html import escape
import logging
from fastapi import FastAPI, Request, Response
import httpx
import os

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
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
    # Issue alerts
    if "event" in data:
        title = escape(data.get("event", {}).get("title", "No title"))
        project = escape(data.get("project_name", data.get("project", "")))
        url = data.get("url", "")
        level = data.get("event", {}).get("level", "error")
        parts = [f"<b>[{level.upper()}]</b> {title}"]
        if project:
            parts.append(f"Project: {project}")
        if url:
            parts.append(f"<a href=\"{url}\">View in Sentry</a>")
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
        return message
    return str(data)
