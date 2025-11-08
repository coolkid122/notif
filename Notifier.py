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

async def monitor():
    global last_id
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "User-Agent": "DiscordBot (https://github.com/you, 1.0)"
    }
    channel_id = "1434326527075553452"  # ← Hardcoded, no env, no var
    async with aiohttp.ClientSession(headers=headers) as s:
        async with s.get(f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=1") as r:
            if r.status != 200:
                text = await r.text()
                logger.error(f"Init failed: {r.status} {text}")
                return
            data = await r.json()
            if data:
                last_id = data[0]["id"]
                logger.info(f"Started. Last ID: {last_id}")

        while True:
            try:
                async with s.get(f"https://discord.com/api/v9/channels/{channel_id}/messages?after={last_id}&limit=50") as r:
                    if r.status == 200:
                        msgs = await r.json()
                        for m in msgs:
                            await forward(m, s)
                            last_id = m["id"]
                            logger.info(f"Forwarded: {m['id']}")
                    else:
                        logger.warning(f"Poll error: {r.status}")
            except Exception as e:
                logger.error(f"Poll exception: {e}")
            await asyncio.sleep(1)

async def forward(msg, s):
    payload = {
        "content": msg.get("content") or None,
        "username": msg["author"]["username"],
        "avatar_url": msg["author"].get("avatar") and f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png",
        "embeds": msg.get("embeds", []),
        "attachments": msg.get("attachments", []) and [{"url": a["url"]} for a in msg["attachments"]]
    }
    try:
        async with s.post(WEBHOOK_URL, json=payload) as r:
            if r.status != 204:
                text = await r.text()
                logger.warning(f"Webhook failed: {r.status} {text}")
    except Exception as e:
        logger.error(f"Send error: {e}")

if __name__ == "__main__":
    asyncio.run(monitor())
