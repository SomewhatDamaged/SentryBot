import asyncio
import traceback

import discord
from discord_features import check_message, notify_staff, clean_last_pinged
from threading import Lock
from image import Downloader

DOWNLOADER: Downloader

# Make a 'discord_token' file and put your token in it. Keep it safe.
TOKEN: str = open('./discord_token').read().strip()

# noinspection PyBroadException,PyMethodMayBeStatic
class MyClient(discord.Client):
    lock = Lock()
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.guild is None:
            return
        if message.author.bot:
            return
        if bool(message.author.guild_permissions.ban_members):
            for member in message.mentions:
                if member.id == self.user.id:
                    await message.reply(f"I hear you, {message.author.mention}!")
                    return
        global DOWNLOADER
        try:
            with self.lock:
                print(f'Message from {message.author}')
                if await check_message(message, DOWNLOADER):
                    clean_last_pinged()
                    await notify_staff(message)
                    return
                return
        except Exception:
            traceback.print_exc()


# noinspection PyDunderSlots,PyUnresolvedReferences,PyBroadException
async def bot_init():
    global DOWNLOADER
    DOWNLOADER = Downloader()
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True

    client = MyClient(intents=intents)
    try:
        await client.start(TOKEN, reconnect=True)
    except asyncio.exceptions.CancelledError:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        await DOWNLOADER.close()

if __name__ == '__main__':
    asyncio.run(bot_init())
