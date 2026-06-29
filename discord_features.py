import re
import traceback
from typing import Union

import imagehash

import discord
from image import Downloader
from datetime import datetime, timezone, timedelta
from exceptions import SentryBotException

LAST_PINGED: dict = {} # Keeps track of how long ago a ping went out on server
DELAY_MINUTES: int = 5 # How long to wait between pings
TIMEOUT_FOR: int = 12 # How many hours to timeout users for (if the bot can)

url_regex = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,16}\b[-a-zA-Z0-9()@:%_+.,~#?&/=\[\]]*", flags=re.IGNORECASE)

async def check_message(message: discord.Message, downloader: Downloader) -> Union[None, imagehash.ImageHash]:
    pinged: Union[None, datetime] = LAST_PINGED.get(last_pinged_string(message), None)
    if pinged and datetime.now(tz=timezone.utc) - pinged < timedelta(minutes=DELAY_MINUTES): # Waaaay too soon to ping more.
        return None
    items_to_check = []
    if message.message_snapshots:
        for forwarded_message in message.message_snapshots:
            items_to_check += fetch_data(forwarded_message)
    else:
        items_to_check += fetch_data(message)
    for url in items_to_check:
        try:
            p_hash, dimensions = await downloader.get_hash(url)
            if await downloader.check_hash(p_hash, dimensions):
                return p_hash
        except SentryBotException:
            traceback.print_exc()
            break
    return None

def fetch_data(message: Union[discord.Message, discord.MessageSnapshot]) -> list:
    items_to_check = []
    items: discord.Attachment
    for items in message.attachments:
        if items.url:
            items_to_check.append(items.url)
    items: discord.Embed
    for items in message.embeds:
        if items.image.url:
            items_to_check.append(items.image.url)
        if items.thumbnail.url:
            items_to_check.append(items.thumbnail.url)
    items: str
    for items in url_regex.findall(message.content):
        items_to_check.append(items)
    return items_to_check

async def timeout_member(member: discord.Member) -> bool:
    try:
        await member.timeout(timedelta(hours=TIMEOUT_FOR), reason=f"Posted images that matched as crypto-scams. ({TIMEOUT_FOR} hours)")
    except (discord.Forbidden, discord.HTTPException, TypeError, ValueError):
        return False
    return True

def can_ban(member: discord.Member) -> bool:
    if member.bot:
        return False
    status = member.raw_status
    return bool(member.guild_permissions.ban_members) and (status.lower() == "online" or status.lower() == "idle")

def can_moderate(member: discord.Member) -> bool:
    return bool(member.guild_permissions.moderate_members) if member else False

# noinspection PyUnresolvedReferences
async def notify_staff(message: discord.Message, has_muted: bool = False) -> None:
    guild = message.guild
    global LAST_PINGED
    mods = []
    for member in guild.members:
        if can_ban(member):
            mods.append(member)
    message_out = "Yup, another crypto-image-scam\nPinging online/idle mods...\n"
    if mods:
        for member in mods:
            message_out += "- " + member.mention + "\n"
        if has_muted:
            message_out += f"Muted them for {TIMEOUT_FOR} hours (:\n"
        await message.reply(message_out)
        LAST_PINGED[last_pinged_string(message)] = datetime.now(tz=timezone.utc)

# noinspection PyUnresolvedReferences
def last_pinged_string(message: discord.Message) -> str:
    return f"{message.guild.id}|{message.author.id}"

def clean_last_pinged():
    global LAST_PINGED
    now = datetime.now(tz=timezone.utc)
    for key in list(LAST_PINGED.keys()):
        pinged: Union[None, datetime] = LAST_PINGED.get(key, None)
        if pinged and now - pinged > timedelta(minutes=DELAY_MINUTES):
            del LAST_PINGED[key]