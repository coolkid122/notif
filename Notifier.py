# main.py
import asyncio
import aiohttp
import os

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "1434326527075553452")
WEBHOOK_URL = os.getenv("WEBHOOK")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("Set TOKEN and WEBHOOK env vars")

last_id = None

async def monitor():
    global last_id
    headers = {"Authorization": f"Bot {TOKEN}"}
    async with aiohttp.ClientSession(headers=headers) as s:
        async with s.get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1") as r:
            if r.status == 200:
                data = await r.json()
                if data: last_id = data[0]["id"]
        while True:
            async with s.get(f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?after={last_id}&limit=50") as r:
                if r.status == 200:
                    msgs = await r.json()
                    for m in msgs:
                        await forward(m, s)
                        last_id = m["id"]
            await asyncio.sleep(0.05)

async def forward(msg, s):
    payload = {
        "content": msg.get("content"),
        "username": msg["author"]["username"],
        "avatar_url": f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png" if msg["author"].get("avatar") else None,
        "embeds": msg.get("embeds", []),
        "attachments": [{"url": a["url"]} for a in msg.get("attachments", [])]
    }
    async with s.post(WEBHOOK_URL, json=payload): pass

if __name__ == "__main__":
    asyncio.run(monitor())
