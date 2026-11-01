import asyncio
import tracemalloc
from datetime import datetime, timezone, timedelta
from typing import NamedTuple, Union
from asyncio import Lock, create_task, sleep

from image import Downloader
from moderation import Moderated
from discord_features import notify_staff, can_moderate, can_ban, can_delete, can_kick, timeout_member, kick_member, ban_member, delete_message

import discord
import os
import psutil
import time

from sentrybot_exceptions import NotImageException, URLException, SentryBotException

from my_logging import make_logger, process_exception

log = make_logger()

EMAIL = open("./useragent").read().strip()
VERSION = open("./version").read().strip()

pid = os.getpid()
process_info = psutil.Process(pid)

class MemoryStats(NamedTuple):
    memory_used: int
    memory_free: int

def memory_stats() -> MemoryStats:
    memory_bytes = process_info.memory_info().rss
    total_bytes = psutil.virtual_memory().total
    return MemoryStats(memory_bytes, total_bytes)


class TaskMemAverage:
    average_mem_per_task: int = 0
    last_ten_tasks: list[int] = []

    def add(self, memory_used: int):
        if memory_used == 0:
            return
        self.last_ten_tasks.append(memory_used)
        while len(self.last_ten_tasks) > 10:
            self.last_ten_tasks.pop(0)
        self.average_mem_per_task = int(sum(self.last_ten_tasks) / len(self.last_ten_tasks))

    @property
    def memory_info(self) -> MemoryStats:
        memory_data = memory_stats()
        return memory_data

    @property
    def proceed(self):
        if self.average_mem_per_task == 0:
            return True
        memory_data = memory_stats()
        return max(self.last_ten_tasks) * 2.0 < memory_data.memory_free

class TaskTimeAverage:
    average_time_per_task: float = 0
    last_ten_tasks: list[float] = []

    def add(self, time_used: float):
        self.last_ten_tasks.append(time_used)
        while len(self.last_ten_tasks) > 10:
            self.last_ten_tasks.pop(0)
        self.average_time_per_task = float(sum(self.last_ten_tasks) / len(self.last_ten_tasks))

class ProcessingQueue:
    queue = []
    actioned: dict[str,str] = {}
    processing_mutex = Lock()
    queue_mutex = Lock()
    actioning_mutex = Lock()
    mem_tracker = TaskMemAverage()
    time_tracker = TaskTimeAverage()
    bot: discord.ClientUser = None
    cleanup: asyncio.Task = None

    def __init__(self, bot: discord.ClientUser|None = None, downloader: Downloader|None = None):
        if bot is None:
            raise TypeError("bot cannot be None")
        if downloader is None:
            raise TypeError("downloader cannot be None")
        self.bot = bot
        self.downloader = downloader
        self.cleanup = create_task(self.clean_actioned())

    async def add(self, message: discord.Message, urls: list):
        create_task(self._add(message, urls))

    async def _add(self, message: discord.Message, urls: list):
        async with self.queue_mutex:
            self.queue.append({"message": message, "urls": urls})
        if self.queue_mutex.locked():
            return
        create_task(self._process_queue())

    async def _get(self) -> dict:
        async with self.queue_mutex:
            return self.queue.pop(0)

    async def _process_queue(self):
        if len(self.queue) == 0:
            return
        tasks: list[asyncio.Task] = []
        async with self.processing_mutex:
            while len(self.queue) > 0:
                datum: dict = await self._get()
                for url in datum["urls"]:
                    while not self.mem_tracker.proceed or len(tasks) >= 4:
                        await sleep(0.2)
                        tasks = self.check_tasks(tasks)
                    await sleep(0.5)
                    tasks.append(create_task(self.process_image(datum["message"], url)))

    def check_tasks(self, tasklist: list[asyncio.Task]):
        tasks_out: list[asyncio.Task] = []
        for task in tasklist:
            if not task.done():
                tasks_out.append(task)
        return tasks_out

    async def process_image(self, message: discord.Message, url: str):
        try:
            if not isinstance(message.author, discord.Member):
                return
            member: discord.Member = message.author
            guild: discord.Guild = member.guild
            if self.is_actioned(member = member, guild=guild):
                return
            start = time.time()
            tracemalloc.start()
            tracemalloc.reset_peak()
            # begin task here
            data = await self._process_image(url)
            # end task
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            end = time.time()
            self.time_tracker.add(end - start)
            self.mem_tracker.add(peak)
            if data is not None and data:
                create_task(self.action(message, data))
        except asyncio.CancelledError:
            raise
        except Exception:
            process_exception(f"Error processing {url}")

    async def _process_image(self, url: str) -> Union[None, str, dict]:
        try:
            log.info(f"Checking {url}")
            image_metadata, ocr_data = await self.downloader.get_hash_and_ocr(url)
            for p_hash, dimensions, image_type in image_metadata:
                if await self.downloader.check_hash(p_hash, dimensions):
                    log.info(f"Found {p_hash} in {image_type} with dimensions {dimensions} in {url}")
                    return 'pHash'
            if isinstance(ocr_data, dict) and ocr_data["match"]:
                log.info(f"Match from OCR.\nMatching string: {ocr_data['match_string']}")
                log.info(f"Distance: {ocr_data['distance']}")
                return ocr_data
        except NotImageException:
            log.info(f"URL not an image: {url}")
        except URLException:
            log.info(f"Dead URL: {url}")
        except SentryBotException:
            process_exception(f"URL: {url}")
        except asyncio.TimeoutError:
            log.info(f"Timeout: {url}")
        except asyncio.CancelledError:
            raise
        except Exception:
            process_exception(f"URL: {url}")
        log.info(f"Nothing found in {url}")
        return None

    async def action(self, message: discord.Message, data: Union[str, dict]):
        if not isinstance(message.guild, discord.Guild):
            return
        if not isinstance(message.author, discord.Member):
            return
        member: discord.Member = message.author
        guild: discord.Guild = member.guild
        me = await message.guild.fetch_member(self.bot.id)
        async with self.actioning_mutex:
            moderated = Moderated()
            moderated.source = data if isinstance(data, dict) else {}, 'OCR' if isinstance(data, dict) else data
            if not self.is_actioned(member = message.author, guild = guild, message = message):
                if me and can_ban(me):
                    await ban_member(message.author, message, moderated)
                    moderated.banned = True
                    moderated.deleted = True
                elif me and can_kick(me):
                    await kick_member(message.author, message, moderated)
                    moderated.kicked = True
                elif me and can_moderate(me):
                    worked = await timeout_member(message.author, message, moderated)
                    if worked:
                        moderated.muted = True
                    else:
                        moderated.muted_err = True
                if me and can_delete(me, message):
                    await delete_message(message, moderated)
                    moderated.deleted = True
            if not self.is_actioned(member = message.author, guild = guild):
                await notify_staff(message, moderated)
            now = datetime.now(tz=timezone.utc)
            self.actioned[now.isoformat()] = f"{member.id}|{message.id}|{guild.id}"

    async def clean_actioned(self):
        while True:
            await sleep(60 * 10)
            async with self.actioning_mutex:
                expired = datetime.now(tz=timezone.utc)
                for key in list(self.actioned.keys()):
                    pinged: datetime = datetime.fromisoformat(key)
                    if pinged and expired - pinged > timedelta(minutes=10):
                        del self.actioned[key]

    def is_actioned(self, member: discord.Member, guild: discord.Guild, message: discord.Message|None = None) -> bool:
        if message is not None:
            return f"{member.id}|{message.id}|{guild.id}" in self.actioned.values()
        for _, action in self.actioned.items():
            if not action.startswith(str(member.id)):
                continue
            if not action.endswith(str(guild.id)):
                continue
            return True
        return False