# main.py
import asyncio
import aiohttp
import os
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("TOKEN and WEBHOOK required")

last_id = None
CHANNEL_ID = "1434326527075553452"

async def monitor():
    global last_id
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "User-Agent": "DiscordBot (https://github.com/you, 1.0)"
    }
    connector = aiohttp.TCPConnector(limit=10)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(headers=headers, connector=connector, timeout=timeout) as s:
        # Get last message
        async with s.get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1") as r:
            if r.status == 429:
                data = await r.json()
                retry = data.get("retry_after", 1)
                logger.warning(f"Rate limited. Waiting {retry}s")
                await asyncio.sleep(retry)
            elif r.status != 200:
                text = await r.text()
                logger.error(f"Init failed: {r.status} {text}")
                return
            else:
                data = await r.json()
                if data:
                    last_id = data[0]["id"]
                    logger.info(f"Started. Last ID: {last_id}")

        # Fast polling with smart backoff
        while True:
            try:
                start = time.time()
                async with s.get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?after={last_id}&limit=50") as r:
                    if r.status == 200:
                        msgs = await r.json()
                        for m in msgs:
                            await forward(m, s)
                            last_id = m["id"]
                        if msgs:
                            logger.info(f"Forwarded {len(msgs)} new messages")
                    elif r.status == 429:
                        data = await r.json()
                        retry = data.get("retry_after", 1) + 0.1
                        logger.warning(f"Rate limited. Sleep {retry:.2f}s")
                        await asyncio.sleep(retry)
                        continue
                    else:
                        logger.warning(f"Poll error: {r.status}")
                
                # Aim for ~10 requests/sec
                elapsed = time.time() - start
                wait = max(0.006, 0.1 - elapsed)
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"Exception: {e}")
                await asyncio.sleep(1)

async def forward(msg, s):
    payload = {
        "content": msg.get("content") or None,
        "username": msg["author"]["username"],
        "avatar_url": msg["author"].get("avatar") and f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png",
        "embeds": msg.get("embeds", []),
        "attachments": [{"url": a["url"]} for a in msg.get("attachments", [])] if msg.get("attachments") else []
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
