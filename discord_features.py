import logging
import re
from typing import Union

import imagehash

import discord

from image import Downloader
from datetime import datetime, timezone, timedelta
from exceptions import SentryBotException, NotImageException, URLException
from mock_logging import MockLogger
from moderation import Moderated

log = logging.getLogger()
if log is not None:
    log = MockLogger()

LAST_PINGED: dict = {} # Keeps track of how long ago a ping went out on server
DELAY_MINUTES: int = 5 # How long to wait between pings
TIMEOUT_FOR: int = 12 # How many hours to timeout users for (if the bot can)

url_regex = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,16}\b[-a-zA-Z0-9()@:%_+.,~#?&/=\[\]]*", flags=re.IGNORECASE)

async def get_urls(message: discord.Message) -> list:
    items_to_check = []
    if message.message_snapshots:
        for forwarded_message in message.message_snapshots:
            items_to_check += fetch_data(forwarded_message)
    else:
        items_to_check += fetch_data(message)
    items_to_check = list(set(items_to_check))
    return items_to_check


async def check_message(message: discord.Message, downloader: Downloader) -> Union[None, imagehash.ImageHash]:
    items_to_check = await get_urls(message)
    log.debug(f"{items_to_check = }")
    for url in items_to_check:
        try:
            log.info(f"Checking {url}")
            p_hash, dimensions = await downloader.get_hash(url)
            if await downloader.check_hash(p_hash, dimensions):
                return p_hash
        except NotImageException:
            log.info(f"URL not an image: {url}")
            continue
        except URLException:
            log.info(f"Dead URL: {url}")
        except SentryBotException:
            log.exception(f"URL: {url}")
        except Exception:
            log.exception(f"URL: {url}")
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

async def timeout_member(member: discord.Member, message: discord.Message) -> bool:
    try:
        if not too_recent(member): # Waaaay too soon to notify more.
            success_one = await send_message(target=member, content=f"You are being timed out for sending crypto-scam images. If this was in error, please contact a moderator of {member.guild.name} to remove it.")
            success_two = await send_message(target=member, reference=message.to_reference(type=discord.MessageReferenceType.forward))
            if not success_one and not success_two:
                log.exception(f"Unable to send 'timeout user' message to {member.display_name} ({message.author.id})")
            await member.timeout(timedelta(hours=TIMEOUT_FOR), reason=f"SentyBot(Automated): Posted images that matched as crypto-scams. ({TIMEOUT_FOR} hours)")
    except (discord.Forbidden, discord.HTTPException, TypeError, ValueError):
        log.exception()
        return False
    return True

async def ban_member(member: discord.Member, message: discord.Message) -> bool:
    try:
        if not too_recent(member): # Waaaay too soon to notify more.
            success_one = await send_message(target=member, content=f"You are being banned for sending crypto-scam images. If this was in error, please contact a moderator of {member.guild.name} to remove it.")
            success_two = await send_message(target=member, reference=message.to_reference(type=discord.MessageReferenceType.forward))
            if not success_one and not success_two:
                log.exception(f"Unable to send 'banned user' message to {member.display_name} ({message.author.id})")
            await member.ban(delete_message_seconds=60, reason="SentyBot(Automated): Sending crypto-scam messages. Deleted last 1min of messages.")
    except (discord.Forbidden, discord.HTTPException, discord.NotFound, ValueError, TypeError):
        log.exception()
        return False
    return True

async def kick_member(member: discord.Member, message: discord.Message) -> bool:
    try:
        if not too_recent(member): # Waaaay too soon to notify more.
            success_one = await send_message(target=member, content=f"You are being kicked for sending crypto-scam images. If this was in error, please rejoin {member.guild.name}.")
            success_two = await send_message(target=member, reference=message.to_reference(type=discord.MessageReferenceType.forward))
            if not success_one and not success_two:
                log.exception(f"Unable to send 'kicked user' message to {member.display_name} ({message.author.id})")
            await member.kick(reason="SentyBot(Automated): Sending crypto-scam messages. Deleted last 1min of messages.")
    except (discord.Forbidden, discord.HTTPException, discord.NotFound, ValueError):
        log.exception()
        return False
    return True

async def delete_message(message: discord.Message, moderated: Moderated) -> bool:
    author = message.author
    assert isinstance(author, discord.Member)
    try:
        if not too_recent(author) and not moderated.moderated: # Waaaay too soon to notify more.
            success_one = await send_message(target=author, content=f"Your message has been deleted as it was detected to have crypto-scam images. If this was in error, please contact a moderator of {message.guild}.")
            success_two = await send_message(target=author, reference=message.to_reference(type=discord.MessageReferenceType.forward))
            if not success_one and not success_two:
                log.error(f"Unable to send 'deleted message' message to {message.author.display_name} ({message.author.id})")
        await message.delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        log.exception()
        return False
    return True

def is_moderator(member: discord.Member) -> bool:
    if member.bot:
        return False
    status = member.raw_status
    return bool(member.guild_permissions.ban_members) and (status.lower() == "online" or status.lower() == "idle")

def can_moderate(member: discord.Member) -> bool:
    return bool(member.guild_permissions.moderate_members) if member else False

def can_kick(member: discord.Member) -> bool:
    return bool(member.guild_permissions.kick_members) if member else False

def can_ban(member: discord.Member) -> bool:
    return bool(member.guild_permissions.ban_members) if member else False

def can_delete(member: discord.Member, message: discord.Message) -> bool:
    return bool(message.channel.permissions_for(member).manage_messages) if member and message else False

# noinspection PyUnresolvedReferences
async def notify_staff(message: discord.Message, moderated: Moderated) -> None:
    guild = message.guild
    channel = message.channel
    author = message.author
    assert isinstance(author, discord.Member)
    if too_recent(author): # Waaaay too soon to ping more.
        return
    mods = []
    for member in guild.members:
        if is_moderator(member):
            mods.append(member)
    message_out = "Yup, another crypto-image-scam\nPinging online/idle mods...\n"
    if mods:
        for member in mods:
            message_out += "- " + member.mention + "\n"
        if moderated.banned:
            message_out += f"Banned {author.mention}\n"
        elif moderated.kicked:
            message_out += f"Kicked {author.mention}\n"
        elif moderated.muted:
            message_out += f"Muted them for {TIMEOUT_FOR} hours (:\n"
        if moderated.deleted:
            message_out += f"Deleted {author.mention}'s (scam) messages\n"
        if not moderated.deleted:
            await message.reply(message_out, silent=False if moderated.banned or moderated.kicked else True)
        else:
            await channel.send(message_out, silent=True)
        global LAST_PINGED
        LAST_PINGED[last_pinged_string(author)] = datetime.now(tz=timezone.utc)
    if not moderated.moderated:
        success_one = await send_message(target=author, content="You are sending crypto-scam messages! Please secure your account!")
        success_two = await send_message(target=author, reference=message.to_reference(type=discord.MessageReferenceType.forward))
        if not success_one or not success_two:
            log.error(f"Unable to send 'deleted message' message to {message.author.display_name} ({message.author.id})")

# noinspection PyUnresolvedReferences
def last_pinged_string(author:discord.Member) -> str:
    return f"{author.guild.id}|{author.id}"

def clean_last_pinged():
    global LAST_PINGED
    now = datetime.now(tz=timezone.utc)
    for key in list(LAST_PINGED.keys()):
        pinged: Union[None, datetime] = LAST_PINGED.get(key, None)
        if pinged and now - pinged > timedelta(minutes=DELAY_MINUTES):
            del LAST_PINGED[key]

async def send_message(target: discord.Member, *args, **kwargs) -> bool:
    try:
        await target.send(*args, **kwargs)
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound, TypeError, ValueError):
        return False

def too_recent(author: discord.Member) -> bool:
    global LAST_PINGED
    pinged: Union[None, datetime] = LAST_PINGED.get(last_pinged_string(author), None)
    if pinged and datetime.now(tz=timezone.utc) - pinged < timedelta(minutes=DELAY_MINUTES):  # Waaaay too soon
        return True
    return False