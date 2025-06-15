import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import datetime
import os
from keep_alive import run  # From your Flask keep_alive.py

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

FORBIDDEN_WORDS = ["fuck", "shit", "bitch", "asshole", "cunt"]
MOD_LOG_CHANNEL = "mod-logs"
AUTO_UNMUTE_TIME = 600  # 10 minutes

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

async def log_action(guild, embed):
    channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL)
    if channel:
        await channel.send(embed=embed)

async def send_dm(user, title, reason, moderator):
    try:
        embed = discord.Embed(title=title, color=discord.Color.red())
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=moderator, inline=False)
        embed.add_field(name="Note", value="Please stick to the rules. Thanks for understanding.", inline=False)
        embed.timestamp = datetime.datetime.now()
        await user.send(embed=embed)
    except:
        pass

async def auto_unmute(guild, user_id):
    await discord.utils.sleep_until(datetime.datetime.utcnow() + datetime.timedelta(seconds=AUTO_UNMUTE_TIME))
    member = guild.get_member(user_id)
    if member:
        mute_role = discord.utils.get(guild.roles, name="Muted")
        if mute_role in member.roles:
            await member.remove_roles(mute_role)
            embed = discord.Embed(title="🔊 User Automatically Unmuted",
                                  description=f"{member.mention} was automatically unmuted.",
                                  color=discord.Color.green())
            await log_action(guild, embed)

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    for guild in bot.guilds:
        embed = discord.Embed(title="🟢 Bot Restarted", description="Bot is back online and running.", color=discord.Color.green())
        embed.timestamp = datetime.datetime.now()
        await log_action(guild, embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    caps = sum(1 for c in message.content if c.isupper())
    if any(word in message.content.lower() for word in FORBIDDEN_WORDS) or (len(message.content) > 10 and caps / len(message.content) > 0.7):
        await message.delete()
        reason = "Inappropriate language or excessive capital letters"
        timestamp = datetime.datetime.utcnow().isoformat()
        await bot.db.execute("INSERT INTO warnings (user_id, mod, reason, timestamp) VALUES (?, ?, ?, ?)",
                             (message.author.id, "AutoMod", reason, timestamp))
        await bot.db.commit()
        await send_dm(message.author, "⚠️ Warning Issued", reason, "AutoMod")
        embed = discord.Embed(title="🚨 AutoMod Triggered", color=discord.Color.red())
        embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
        embed.add_field(name="Message", value=message.content, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.timestamp = datetime.datetime.now()
        await log_action(message.guild, embed)

    await bot.process_commands(message)

def is_mod():
    async def predicate(inter: discord.Interaction):
        perms = inter.user.guild_permissions
        return perms.kick_members or perms.ban_members
    return app_commands.check(predicate)

@bot.tree.command(name="ban", description="Ban a user")
@app_commands.describe(user="User to ban", reason="Reason for ban")
@is_mod()
async def ban(inter: discord.Interaction, user: discord.Member, reason: str):
    await user.ban(reason=reason)
    await send_dm(user, "🚫 You have been banned", reason, inter.user.name)
    embed = discord.Embed(title="🚫 User Banned", color=discord.Color.dark_red())
    embed.add_field(name="User", value=str(user), inline=False)
    embed.add_field(name="Moderator", value=str(inter.user), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = datetime.datetime.now()
    await log_action(inter.guild, embed)
    await inter.response.send_message(f"✅ {user} has been banned. Reason: {reason}")

@bot.tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason for kick")
@is_mod()
async def kick(inter: discord.Interaction, user: discord.Member, reason: str):
    await user.kick(reason=reason)
    await send_dm(user, "👢 You have been kicked", reason, inter.user.name)
    embed = discord.Embed(title="👢 User Kicked", color=discord.Color.orange())
    embed.add_field(name="User", value=str(user), inline=False)
    embed.add_field(name="Moderator", value=str(inter.user), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = datetime.datetime.now()
    await log_action(inter.guild, embed)
    await inter.response.send_message(f"👢 {user} has been kicked. Reason: {reason}")

@bot.tree.command(name="mute", description="Mute a user")
@app_commands.describe(user="User to mute", reason="Reason for mute")
@is_mod()
async def mute(inter: discord.Interaction, user: discord.Member, reason: str):
    mute_role = discord.utils.get(inter.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await inter.guild.create_role(name="Muted")
        for channel in inter.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await user.add_roles(mute_role)
    await send_dm(user, "🔇 You have been muted", reason, inter.user.name)
    embed = discord.Embed(title="🔇 User Muted", color=discord.Color.gold())
    embed.add_field(name="User", value=str(user), inline=False)
    embed.add_field(name="Moderator", value=str(inter.user), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = datetime.datetime.now()
    await log_action(inter.guild, embed)
    await inter.response.send_message(f"🔇 {user} has been muted. Reason: {reason}")
    bot.loop.create_task(auto_unmute(inter.guild, user.id))

@bot.tree.command(name="unmute", description="Unmute a user")
@app_commands.describe(user="User to unmute")
@is_mod()
async def unmute(inter: discord.Interaction, user: discord.Member):
    mute_role = discord.utils.get(inter.guild.roles, name="Muted")
    if mute_role and mute_role in user.roles:
        await user.remove_roles(mute_role)
        await inter.response.send_message(f"🔊 {user} has been unmuted.")

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(user="User to warn", reason="Reason")
@is_mod()
async def warn(inter: discord.Interaction, user: discord.Member, reason: str):
    timestamp = datetime.datetime.utcnow().isoformat()
    await bot.db.execute("INSERT INTO warnings (user_id, mod, reason, timestamp) VALUES (?, ?, ?, ?)",
                         (user.id, inter.user.name, reason, timestamp))
    await bot.db.commit()
    await send_dm(user, "⚠️ You have been warned", reason, inter.user.name)
    embed = discord.Embed(title="⚠️ User Warned", color=discord.Color.orange())
    embed.add_field(name="User", value=str(user), inline=False)
    embed.add_field(name="Moderator", value=str(inter.user), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = datetime.datetime.now()
    await log_action(inter.guild, embed)
    await inter.response.send_message(f"⚠️ {user} has been warned. Reason: {reason}")

@bot.tree.command(name="clearwarns", description="Clear user warnings")
@app_commands.describe(user="User to clear", all="Delete all warnings?")
@is_mod()
async def clearwarns(inter: discord.Interaction, user: discord.Member, all: bool = True):
    if all:
        await bot.db.execute("DELETE FROM warnings WHERE user_id = ?", (user.id,))
    else:
        await bot.db.execute("DELETE FROM warnings WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user.id,))
    await bot.db.commit()
    await inter.response.send_message(f"✅ Warnings {'cleared' if all else 'reduced by 1'} for {user}.")

@bot.tree.command(name="warnings", description="Show warnings for a user")
@app_commands.describe(user="User to check")
async def warnings(inter: discord.Interaction, user: discord.Member):
    cursor = await bot.db.execute("SELECT mod, reason, timestamp FROM warnings WHERE user_id = ?", (user.id,))
    rows = await cursor.fetchall()
    if not rows:
        return await inter.response.send_message("✅ No warnings found.")
    embed = discord.Embed(title=f"⚠️ Warnings for {user}", color=discord.Color.orange())
    for i, (mod, reason, time) in enumerate(rows, 1):
        dt = datetime.datetime.fromisoformat(time).strftime("%d.%m.%Y %H:%M")
        embed.add_field(name=f"{i}. {dt} by {mod}", value=reason, inline=False)
    await inter.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Get user info")
@app_commands.describe(user="User to get info for")
async def userinfo(inter: discord.Interaction, user: discord.Member = None):
    user = user or inter.user
    embed = discord.Embed(title=f"👤 Info for {user}", color=discord.Color.blurple())
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Joined", value=user.joined_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="Roles", value=", ".join([r.name for r in user.roles if r.name != "@everyone"]) or "None", inline=False)
    cursor = await bot.db.execute("SELECT mod, reason, timestamp FROM warnings WHERE user_id = ?", (user.id,))
    rows = await cursor.fetchall()
    if rows:
        for i, (mod, reason, time) in enumerate(rows, 1):
            dt = datetime.datetime.fromisoformat(time).strftime("%d.%m.%Y %H:%M")
            embed.add_field(name=f"Warning {i} - {dt}", value=f"{reason} (by {mod})", inline=False)
    await inter.response.send_message(embed=embed)

# Start the keep_alive web server for uptime pings
run()

# Run the bot using a secure environment token
bot.run(os.getenv("DISCORD_TOKEN"))
