import asyncio
import traceback

import discord
from discord_features import check_message, notify_staff, clean_last_pinged, can_moderate, timeout_member
from threading import Lock
from image import Downloader

# Make a 'discord_token' file and put your token in it. Keep it safe.
TOKEN: str = open('./discord_token').read().strip()


# noinspection PyBroadException,PyMethodMayBeStatic,PyUnresolvedReferences
class MyClient(discord.Client):
    lock = Lock()

    def __init__(self, downloader: Downloader, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.downloader: Downloader = downloader

    async def on_ready(self):
        print(f'Logged on as {self.user}!')

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
            with self.lock:
                if await check_message(message, self.downloader):
                    has_muted = False
                    if me and can_moderate(me):
                        await timeout_member(message.author)
                        has_muted = True
                    clean_last_pinged()
                    await notify_staff(message, has_muted)
                    return
                return
        except Exception:
            traceback.print_exc()


# noinspection PyDunderSlots,PyUnresolvedReferences,PyBroadException
async def bot_init():
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
