import asyncio
import io
import traceback
import os

import discord
from discord_features import check_message, notify_staff, clean_last_pinged, can_moderate, can_ban, can_delete, can_kick, timeout_member, kick_member, ban_member, delete_message, get_urls
from asyncio import Lock
from image import Downloader
from mock_logging import MockLogger
from moderation import Moderated
from cloudflare import MyCloudflare
from sentrybot_exceptions import SentryBotException, NotImageException, URLException


log = MockLogger()
log.info(f"Begin logging.")
# Make a 'discord_token' file and put your token in it. Keep it safe.
TOKEN: str = open('./discord_token').read().strip()
# How long for the check of new images on Cloudflare R2 to wait. Default: 5 minutes
SLEEP_TIME: int = int(os.environ.get('SLEEP_TIME', 300))


# noinspection PyBroadException,PyMethodMayBeStatic,PyUnresolvedReferences
class MyClient(discord.Client):
    lock: asyncio.Lock = Lock()

    def __init__(self, downloader: Downloader, cloudflare: MyCloudflare, *args, **kwargs):
        """If you don't know what this does, you're too new to be looking around Python code."""
        super().__init__(*args, **kwargs)
        self.source_ctx_menu = [
            discord.app_commands.ContextMenu(
                name="Report Scam",
                callback=self.context_menu_report,
            ),
            discord.app_commands.ContextMenu(
                name="Check Scam",
                callback=self.context_menu_inspect,
            )
        ]
        self.downloader: Downloader = downloader
        self.tree = discord.app_commands.CommandTree(self)
        for datum in self.source_ctx_menu:
            self.tree.add_command(datum)
        self.cloudflare = cloudflare
        self.app_info: Union[discord.AppInfo, None] = None
        self.owner: Union[discord.User, None] = None

    async def setup_command_hook(self):
        """Runs when the bot is pinged and "sync commands" is sent."""
        await self.tree.sync()

    async def on_ready(self):
        """This runs as soon as the bot is logged in and ready to do work."""
        log.info(f'Logged on as {self.user}!')
        self.app_info = await self.application_info()
        self.owner: discord.User = self.app_info.owner
        await self.check_for_new()

    async def get_stored(self, name: str = "") -> int:
        """Gets number of stored FOLDERS (not individual images)"""
        if self.cloudflare is None:
            raise ValueError("Storage not configured!")
        value = await self.cloudflare.has_folder(name=name, delimiter='/')
        if value is None:
            raise ValueError("Storage error!")
        return value if value else 0

    async def snooze(self):
        """Eepy time"""
        await asyncio.sleep(SLEEP_TIME)

    def valid_embed(self, embed: dict) -> bool:
        """Is this an embed I sent?"""
        try:
            if "flags" not in embed or int(embed["flags"]) != 0:
                return False
            if "type" not in embed or str(embed["type"]) != "rich":
                return False
            if "description" not in embed or not (str(embed["description"]).startswith("There ") and str(embed["description"]).endswith(" to process!")):
                return False
            if len(embed) != 3:
                return False
        except Exception:
            return False
        return True

    async def remove_old(self, old_message: Union[discord.Message, None] = None, skip_message: Union[discord.Message, None] = None):
        """Removes old messages from DMs"""
        if isinstance(old_message, discord.Message):
            await self.delete_message(old_message)
        else:
            async for message in self.owner.history(limit=100):
                if skip_message and message.id == skip_message.id:
                    continue
                if len(message.embeds) != 1:
                    continue
                if not self.valid_embed(message.embeds[0].to_dict()):
                    continue
                await self.delete_message(message)

    async def delete_message(self, message:discord.Message):
        """Because regular delete is for losers who care about its success or failure.
        Move fast; break everything."""
        try:
            await message.delete()
        except Exception:
            pass

    async def check_for_new(self):
        """Checks storage. Notifies owner of bot if it has any image sets reported.
        Cleans up after itself (not an electrician)."""
        last_message: Union[discord.Message, None] = None
        notify: int = -1
        while True:
            try:
                if notify == -1:
                    notify = 0
                else:
                    await self.snooze()
                if self.cloudflare is None:
                    continue
                new_notify = await self.get_stored()
                if new_notify == notify:
                    continue
                elif new_notify == 0:
                    notify = 0
                    await self.remove_old()
                    continue
                elif new_notify <= notify:
                    notify = new_notify
                    continue
                embed = discord.Embed(description=f"There {'is' if new_notify == 1 else 'are'} {new_notify} new image {'set' if new_notify == 1 else 'sets'} to process!")
                new_message = await self.owner.send(embed=embed)
                await self.remove_old(last_message, new_message)
                last_message = new_message
                notify = new_notify
            except asyncio.exceptions.CancelledError:
                pass
            except Exception:
                traceback.print_exc()


    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def context_menu_report(self, interaction: discord.Interaction, message: discord.Message):
        try:
            if self.cloudflare is None:
                await interaction.response.send_message(content="Bot not configured for upload!", ephemeral=True)
                return
            await interaction.response.send_message(content="Working on it...", ephemeral=True)
            if message.guild is None:
                prefix = f"{message.channel.id}-{message.id}"
            else:
                prefix = f"{message.guild.id}-{message.channel.id}-{message.id}"
            if await self.get_stored() >= 500:
                await interaction.edit_original_response(content="Scam report storage full (500+)!")
                log.debug("500+ reports filed!")
                return
            if await self.get_stored(prefix):
                await interaction.edit_original_response(content="Message already reported!")
                log.debug("Already on R2!")
                return
            urls = await get_urls(message)
            i: int = 0
            for url in urls:
                try:
                    image: io.BytesIO = await self.downloader.download_image(url)
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

    @discord.app_commands.allowed_installs(guilds=True, users=True)
    @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def context_menu_inspect(self, interaction: discord.Interaction, message: discord.Message):
        embeds: list[discord.Embed] = []
        message_content = ""
        try:
            await interaction.response.send_message(content="Working on it...", ephemeral=True)
            items_to_check = await get_urls(message)
            message_content = "Items to check:\n```\n"
            for item in items_to_check:
                message_content += f"{item.rsplit('/', 1)[1]}\n"
            message_content += "\n```"
            await interaction.edit_original_response(content=message_content)
            something_found = False
            not_found_main = False
            for url in items_to_check:
                try:
                    embeds.append(discord.Embed(description=f"\n### Checking {url}\n"))
                    if len(embeds) > 10:
                        raise SentryBotException("Too many images to check. What happened?!")
                    await interaction.edit_original_response(content=message_content, embeds=embeds)
                    embeds[-1].description += "```\n"
                    image_metadata = await self.downloader.get_hash(url)
                    if len(image_metadata) > 1:
                        sub_message = ">>>Checking for cropped images<<<\n"
                    else:
                        sub_message = ""
                    for p_hash, dimensions, image_type in image_metadata:
                        if await self.downloader.check_hash(p_hash, dimensions):
                            embeds[-1].description += f"Found {p_hash} in {image_type} with dimensions {dimensions}\n"
                            await interaction.edit_original_response(content=message_content, embeds=embeds)
                            something_found = True
                        else:
                            embeds[-1].description += f"Not found {p_hash} in {image_type} with dimensions {dimensions}\n"
                            await interaction.edit_original_response(content=message_content, embeds=embeds)
                            if image_type == "orig":
                                not_found_main = True
                        if image_type == "orig":
                            embeds[-1].description += sub_message
                except NotImageException:
                    embeds[-1].description += f"URL not an image"
                    await interaction.edit_original_response(content=message_content, embeds=embeds)
                    continue
                except URLException:
                    embeds[-1].description += f"Dead URL"
                    await interaction.edit_original_response(content=message_content, embeds=embeds)
                except SentryBotException as e:
                    log.exception(f"URL: {url}")
                    embed = discord.Embed(description=f"Something crashed!\n{e}")
                    await interaction.edit_original_response(content=message_content, embed=embed)
                    return
                except Exception:
                    log.exception(f"URL: {url}")
                    embeds[-1].description += f"Something crashed!"
                    await interaction.edit_original_response(content=message_content, embeds=embeds)
                finally:
                    embeds[-1].description += "\n```"

        except Exception:
            log.exception("Something went wrong!")
            message_content = "\n### This is bad! Something went wrong!"
            await interaction.edit_original_response(content=message_content)
            return
        await interaction.edit_original_response(content=None, embeds=embeds)
        if something_found and not_found_main:
            await interaction.followup.send("^^^^ Please report this message! ^^^^", wait=True, ephemeral=True)


    async def on_message(self, message):
        if message.guild is None:
            return
        if message.author.bot:
            return
        me = await message.guild.fetch_member(self.user.id)
        if bool(message.author.guild_permissions.ban_members):
            for member in message.mentions:
                if member.id == self.user.id:
                    if "sync commands" in message.content and message.author.id == self.application.owner.id:
                        log.info(f"Trying to sync commands for: {message.author}")
                        await self.setup_command_hook()
                        await message.reply(f"Synced commands, {message.author.mention}!")
                        return
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
    downloader = Downloader(useragent="SentryBot/" + open("./useragent").read().strip() + "/v1.1.2")
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
