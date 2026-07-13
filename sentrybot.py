import asyncio
import logging
import os
import traceback

import discord
from discord_features import check_message, notify_staff, clean_last_pinged, can_moderate, can_ban, can_delete, can_kick, timeout_member, kick_member, ban_member, delete_message, get_urls
from asyncio import Lock
from image import Downloader
from mock_logging import MockLogger
from moderation import Moderated
from cloudflare import MyCloudflare


log = MockLogger()
log.info(f"Begin logging.")
# Make a 'discord_token' file and put your token in it. Keep it safe.
TOKEN: str = open('./discord_token').read().strip()


# noinspection PyBroadException,PyMethodMayBeStatic,PyUnresolvedReferences
class MyClient(discord.Client):
    lock = Lock()

    def __init__(self, downloader: Downloader, cloudflare: MyCloudflare, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_ctx_menu = [
            discord.app_commands.ContextMenu(
                name="Report Scam",
                callback=self.context_menu_report,
            )
        ]
        self.downloader: Downloader = downloader
        self.tree = discord.app_commands.CommandTree(self)
        for datum in self.source_ctx_menu:
            self.tree.add_command(datum)
        self.cloudflare = cloudflare

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        log.info(f'Logged on as {self.user}!')

    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def context_menu_report(self, interaction: discord.Interaction, message: discord.Message):
        try:
            if self.cloudflare is None:
                await interaction.response.send_message(content="Bot not configured for upload!", ephemeral=True)
                return
            await interaction.response.send_message(content="Working on it...", ephemeral=True)
            log.debug(f"Message: {message.content}")
            if message.guild is None:
                prefix = f"{message.channel.id}-{message.id}"
            else:
                prefix = f"{message.guild.id}-{message.channel.id}-{message.id}"
            log.debug(f"Prefix: {prefix}")
            if await self.cloudflare.has_folder('', delimiter='/') >= 500:
                await interaction.edit_original_response(content="Scam report storage full (500+)!")
                log.debug("500+ reports filed!")
                return
            if await self.cloudflare.has_folder(prefix):
                await interaction.edit_original_response(content="Message already reported!")
                log.debug("Already on R2!")
                return
            urls = await get_urls(message)
            i: int = 0
            for url in urls:
                try:
                    image: Image.Image = await self.downloader.download_image(url)
                    result = await self.cloudflare.send_to_s3(image=image, name=f"{prefix}/image{i}.png")
                    if not result:
                        log.error(f"Image upload error! URL: {url}")
                    else:
                        i = i + 1
                except Exception:
                    log.exception("Something went wrong!")
            if i:
                await interaction.edit_original_response(content="Done!")
            else:
                await interaction.edit_original_response(content="No images found!")
        except Exception:
            log.exception("Something went wrong!")
            await interaction.edit_original_response(content="This is bad! Something went wrong!")


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
    cloudflare = MyCloudflare()
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True
    client = MyClient(intents=intents, downloader=downloader, cloudflare=cloudflare)
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
