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

last_id = None
CHANNEL_ID = "1434326527075553452"

async def make_get_request(session, url):
    while True:
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    return await r.json()
                elif r.status == 429:
                    data = await r.json()
                    retry = data.get("retry_after", 1) + 0.1
                    logger.warning(f"Rate limited on {url}. Sleep {retry:.2f}s")
                    await asyncio.sleep(retry)
                else:
                    text = await r.text()
                    logger.error(f"Request failed: {r.status} {text}")
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Request exception: {e}")
            await asyncio.sleep(1)

async def monitor():
    global last_id
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "User-Agent": "DiscordBot (https://github.com/you, 1.0)"
    }
    async with aiohttp.ClientSession(headers=headers) as s:
        # Get last message with retry
        data = await make_get_request(s, f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1")
        if data:
            last_id = data[0]["id"]
            logger.info(f"Started. Last ID: {last_id}")

        while True:
            data = await make_get_request(s, f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?after={last_id}&limit=50")
            if data:
                for m in data:
                    await forward(m, s)
                    last_id = m["id"]
                if data:
                    logger.info(f"Forwarded {len(data)} messages")
            await asyncio.sleep(0.1)  # 10 req/s

async def forward(msg, s):
    payload = {
        "content": msg.get("content") or None,
        "username": msg["author"]["username"],
        "avatar_url": msg["author"].get("avatar") and f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png",
        "embeds": msg.get("embeds", []),
        "attachments": [{"url": a["url"]} for a in msg.get("attachments", [])] if msg.get("attachments") else []
    }
    while True:
        try:
            async with s.post(WEBHOOK_URL, json=payload) as r:
                if r.status == 204:
                    return
                elif r.status == 429:
                    data = await r.json()
                    retry = data.get("retry_after", 1) + 0.1
                    logger.warning(f"Webhook rate limited. Sleep {retry:.2f}s")
                    await asyncio.sleep(retry)
                else:
                    text = await r.text()
                    logger.warning(f"Webhook failed: {r.status} {text}")
                    return  # Don't retry on other errors
        except Exception as e:
            logger.error(f"Send error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(monitor())
