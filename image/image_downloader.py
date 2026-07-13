from typing import Union

import aiohttp
import io

import imagehash

from mock_logging import MockLogger
from .image_process import phash, dimensions
from .image_normalize import convert_to_png_async
from PIL import Image
from sentrybot_exceptions import SentryBotException, NotImageException, URLException
from .split_images import split_two_images_async

log = MockLogger()


# make your own useragent file that has your email in it

HOW_CLOSE: int = 4 # This is a measure of how similar images should be. If they match exactly, or are within 3 distance, it will always be 8-10
#                    If the image has had a little more editing done, and the dimensions are almost the same, it will give a scale:
#                    1-2 — large hamming distance and large dimension change
#                    3-4 — hamming distance less than 10 and dimensions close
#                    5-6 — hamming distance close (4-6) and dimensions almost exactly same

class Downloader:

    def __init__(self, useragent: str):
        self.session = aiohttp.ClientSession()
        self.headers = {"User-Agent": useragent}

    async def close(self):
        await self.session.close()

    async def download_image(self, url: str) -> io.BytesIO:
        async with self.session.get(url, headers=self.headers) as response:
            try:
                response.raise_for_status()
            except aiohttp.client_exceptions.ClientResponseError:
                raise URLException(url)
            if "content-type" in response.headers and not response.headers["content-type"].startswith("image/"):
                raise NotImageException(url)
            buffer = io.BytesIO(await response.read())
            buffer = await convert_to_png_async(buffer)
            return buffer

    async def http_get(self, url: str) -> tuple[aiohttp.ClientResponse, Union[list, dict]]:
        async with self.session.get(url, headers=self.headers) as response:
            return response, await response.json()

    async def http_head(self, url: str) -> aiohttp.ClientResponse:
        async with self.session.head(url, headers=self.headers) as response:
            return response

    async def check_hash(self, p_hash: Union[imagehash.ImageHash, str], image_dimensions: list[int]) -> bool:
        url = f"https://api.excessive.space/v1/scamscore?hash={str(p_hash)}&dimensions={image_dimensions[0]},{image_dimensions[1]}"
        response, data = await self.http_get(url)
        if response.status == 404:
            return False
        if "result" in data and int(data["result"]) >= HOW_CLOSE:
            return True
        if "result" in data:
            return False
        raise SentryBotException(f"Website returned status '{response.status}' instead of 200 or 404", {})

    async def get_hash(self, url: str) -> list[tuple[imagehash.ImageHash, list[int], str]]:
        image = await self.download_image(url)
        output: list[tuple[imagehash.ImageHash, list[int], str]] = []
        images = await split_two_images_async(image)
        for data in images:
            image = Image.open(data["image"])
            result = (phash(image), dimensions(image), data["type"])
            output.append(result)
        return output
