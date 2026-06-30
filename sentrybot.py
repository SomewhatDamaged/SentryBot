import asyncio
import logging
import os
import traceback

import discord
from attr import setters

from discord_features import check_message, notify_staff, clean_last_pinged, can_moderate, can_ban, can_delete, can_kick, timeout_member, kick_member, ban_member, delete_message
from asyncio import Lock
from image import Downloader
from mock_logging import MockLogger
from moderation import Moderated

try:
    from logging_journald import JournaldLogHandler, check_journal_stream
    # Use python default handler
    LOG_HANDLERS = None

    log = logging.getLogger()
    if os.path.exists("./.debug"):
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    if (
        # Check if program running as systemd service
        check_journal_stream() or
        # Check if journald socket is available
        JournaldLogHandler.SOCKET_PATH.exists()
    ):
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s",
            datefmt="[%d/%m/%Y %H:%M]",
        )
        journald_handler = JournaldLogHandler()
        journald_handler.setFormatter(fmt)
        log.addHandler(journald_handler)

        LOG_HANDLERS = [JournaldLogHandler()]

    log.info(f"Begin loggin. Level: {log.level}")
except ModuleNotFoundError:
    log = MockLogger()

# Make a 'discord_token' file and put your token in it. Keep it safe.
TOKEN: str = open('./discord_token').read().strip()

# noinspection PyBroadException,PyMethodMayBeStatic,PyUnresolvedReferences
class MyClient(discord.Client):
    lock = Lock()

    def __init__(self, downloader: Downloader, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.downloader: Downloader = downloader

    async def on_ready(self):
        log.info(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.guild is None:
            return
        if message.author.bot:
            return
        me = await message.guild.fetch_member(self.user.id)
        if bool(message.author.guild_permissions.ban_members):
            for member in message.mentions:
                if member.id == self.user.id:
                    await message.reply(f"I hear you, {message.author.mention}!")
                    return
        try:
            async with self.lock:
                if await check_message(message, self.downloader):
                    moderated = Moderated()
                    if me and can_ban(me):
                        await ban_member(message.author, message)
                        moderated.banned = True
                        moderated.deleted = True
                    elif me and can_kick(me):
                        await kick_member(message.author, message)
                        moderated.kicked = True
                    elif me and can_moderate(me):
                        await timeout_member(message.author, message)
                        moderated.muted = True
                    if me and can_delete(me, message):
                        await delete_message(message, moderated)
                        moderated.deleted = True
                    clean_last_pinged()
                    await notify_staff(message, moderated)
                    return
                return
        except Exception:
            log.exception("Something went wrong!")


# noinspection PyDunderSlots,PyUnresolvedReferences,PyBroadException
async def bot_init():
    log.info("Initializing bot...")
    downloader = Downloader(useragent="SentryBot/" + open("./useragent").read().strip() + "/v1.1.1")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True

    client = MyClient(intents=intents, downloader=downloader)
    try:
        await client.start(TOKEN, reconnect=True)
    except asyncio.exceptions.CancelledError:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        await downloader.close()

if __name__ == '__main__':
    asyncio.run(bot_init())
