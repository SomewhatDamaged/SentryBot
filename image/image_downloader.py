from typing import Union

import aiohttp
import io

import imagehash
from .image_process import phash
from .image_normalize import convert_to_png_async
from PIL import Image

# make your own useragent file that has your email in it
USER_AGENT: str = "SentryBot/" + open("./useragent").read().strip() + "/v1.0.0"


class Downloader:
    headers = {"User-Agent": USER_AGENT}

    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def download_image(self, url: str) -> Image.Image:
        async with self.session.get(url, headers=self.headers) as response:
            response.raise_for_status()
            buffer = io.BytesIO(await response.read())
            buffer = await convert_to_png_async(buffer)
            image = Image.open(buffer)
            return image

    async def http_get(self, url: str) -> aiohttp.ClientResponse:
        async with self.session.get(url, headers=self.headers) as response:
            return response

    async def http_head(self, url: str) -> aiohttp.ClientResponse:
        async with self.session.head(url, headers=self.headers) as response:
            return response

    async def check_hash(self, p_hash: Union[imagehash.ImageHash, str]) -> bool:
        response = await self.http_head(f"https://api.excessive.space/v1/hashcompare?hash={str(p_hash)}")
        response_lookup = {
            200: True,  # Image is in the hashes
            404: False  # Image is not in the hashes
        }
        status = response_lookup.get(response.status, response.status)  # default to cover 5xx and such
        if isinstance(status, bool):
            return status
        raise ValueError(f"Website returned status '{status}' instead of 200 or 404")

    async def get_hash(self, url: str) -> imagehash.ImageHash:
        image = await self.download_image(url)
        return phash(image)
