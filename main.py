import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import datetime
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class ModBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = None

    async def setup_hook(self):
        await self.connect_db()
        await self.create_tables()
        await self.tree.sync()

    async def connect_db(self):
        self.db = await aiosqlite.connect("warnings.db")

    async def create_tables(self):
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER,
                mod TEXT,
                reason TEXT,
                timestamp TEXT
            )
        """)
        await self.db.commit()

bot = ModBot()

@bot.event
async def on_ready():
    print(f"Bot {bot.user} is ready.")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
