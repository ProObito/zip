from datetime import datetime
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import logging

logging.basicConfig(level=logging.INFO)

class Bot(Client):

    def __init__(self):
        super().__init__(
            name="renamer",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME
        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", 8080).start()
        print(f"{me.first_name} ɪꜱ ꜱᴛᴀʀᴛᴇᴅ.....⚡️")
        for id in Config.ADMIN:
            try:
                await self.send_message(id, f"**{me.first_name} ɪꜱ ꜱᴛᴀʀᴛᴇᴅ.....⚡️**")
            except:
                pass

Bot().run()
