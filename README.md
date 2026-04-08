# telegram-webhook-proxy

Lightweight proxy that forwards webhook payloads to Telegram. Keeps bot token and chat ID on the server side, so they never appear in external services like Sentry.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/sentry` | Parses Sentry alert payload and forwards a formatted message |
| POST | `/webhook/raw` | Forwards `text` or `message` field as-is |
| GET | `/health` | Health check |

## Setup

```yaml
# compose.yml
services:
  proxy:
    image: ghcr.io/feshchenkod/telegram-webhook-proxy:latest
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
```

```bash
cp .env.example .env  # fill in your values
docker compose up -d
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Target chat/group ID |
