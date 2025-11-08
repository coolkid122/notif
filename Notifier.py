# main.py
import asyncio
import aiohttp
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("TOKEN and WEBHOOK required")

CHANNEL_ID = "1434326527075553452"
last_id = None
session = None
backoff = 0

async def init_session():
    global session
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "User-Agent": "DiscordBot (https://github.com/you, 1.0)"
    }
    session = aiohttp.ClientSession(headers=headers)

async def safe_get(url):
    global backoff
    while True:
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    backoff = 0
                    return await r.json()
                elif r.status == 429:
                    data = await r.json()
                    retry = data.get("retry_after", 1) + 0.2
                    backoff = min(backoff + retry, 30)
                    logger.warning(f"Rate limited. Backoff {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                else:
                    backoff = min(backoff + 2, 30)
                    text = await r.text()
                    logger.error(f"GET {r.status}: {text}")
                    await asyncio.sleep(backoff)
        except Exception as e:
            backoff = min(backoff + 5, 30)
            logger.error(f"GET error: {e}")
            await asyncio.sleep(backoff)

async def safe_post(payload):
    while True:
        try:
            async with session.post(WEBHOOK_URL, json=payload) as r:
                if r.status == 204:
                    return True
                elif r.status == 429:
                    data = await r.json()
                    retry = data.get("retry_after", 1) + 0.2
                    logger.warning(f"Webhook rate limit. Wait {retry:.2f}s")
                    await asyncio.sleep(retry)
                else:
                    text = await r.text()
                    logger.warning(f"Webhook {r.status}: {text}")
                    return False
        except Exception as e:
            logger.error(f"POST error: {e}")
            await asyncio.sleep(5)

async def monitor():
    global last_id
    await init_session()

    # Initial fetch
    data = await safe_get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1")
    if data:
        last_id = data[0]["id"]
        logger.info(f"Monitoring channel after message ID: {last_id}")

    # Poll with increasing backoff
    while True:
        data = await safe_get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?after={last_id}&limit=50")
        if data:
            for m in data:
                payload = {
                    "content": m.get("content") or None,
                    "username": m["author"]["username"],
                    "avatar_url": m["author"].get("avatar") and f"https://cdn.discordapp.com/avatars/{m['author']['id']}/{m['author']['avatar']}.png",
                    "embeds": m.get("embeds", []),
                    "attachments": [{"url": a["url"]} for a in m.get("attachments", [])] if m.get("attachments") else []
                }
                await safe_post(payload)
                last_id = m["id"]
            if data:
                logger.info(f"Forwarded {len(data)} new message(s)")
        # Wait at least 5 seconds between polls
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(monitor())
