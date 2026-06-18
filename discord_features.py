from typing import Union

import imagehash

import discord
from image import Downloader
from datetime import datetime, timezone, timedelta

LAST_PINGED: dict = {} # Keeps track of how long ago a ping went out on server
DELAY_MINUTES: int = 5 # How long to wait between pings

async def check_message(message: discord.Message, downloader: Downloader) -> Union[None, imagehash.ImageHash]:
    pinged: Union[None, datetime] = LAST_PINGED.get(last_pinged_string(message), None)
    if pinged and datetime.now(tz=timezone.utc) - pinged < timedelta(minutes=DELAY_MINUTES): # Waaaay too soon to ping more.
        return None
    items_to_check = []
    for items in message.attachments + message.embeds:
        if items.url:
            items_to_check.append(items.url)
    for url in items_to_check:
        p_hash = await downloader.get_hash(url)
        if await downloader.check_hash(p_hash):
            return p_hash
    return None

def can_ban(member: discord.Member) -> bool:
    if member.bot:
        return False
    status = member.raw_status
    return bool(member.guild_permissions.ban_members) and (status.lower() == "online" or status.lower() == "idle")

async def notify_staff(message: discord.Message):
    guild = message.guild
    global LAST_PINGED
    mods = []
    for member in guild.members:
        if can_ban(member):
            mods.append(member)
    message_out = "Yup, another 4-image-scam\nPinging online/idle mods...\n"
    if mods:
        for member in mods:
            message_out += "- " + member.mention + "\n"
        await message.reply(message_out)
        LAST_PINGED[last_pinged_string(message)] = datetime.now(tz=timezone.utc)

def last_pinged_string(message: discord.Message) -> str:
    return f"{message.guild.id}|{message.author.id}"

def clean_last_pinged():
    global LAST_PINGED
    now = datetime.now(tz=timezone.utc)
    for key in list(LAST_PINGED.keys()):
        pinged: Union[None, datetime] = LAST_PINGED.get(key, None)
        if pinged and now - pinged > timedelta(minutes=DELAY_MINUTES):
            del LAST_PINGED[key]