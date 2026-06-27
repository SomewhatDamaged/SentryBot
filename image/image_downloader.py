from typing import Union

import aiohttp
import io

import imagehash
from .image_process import phash, dimensions
from .image_normalize import convert_to_png_async
from PIL import Image

# make your own useragent file that has your email in it
USER_AGENT: str = "SentryBot/" + open("./useragent").read().strip() + "/v1.0.0"
HOW_CLOSE: int = 4 # This is a measure of how similar images should be. If they match exactly, or are within 3 distance, it will always be 8-10
#                    If the image has had a little more editing done, and the dimensions are almost the same, it will give a scale:
#                    0-2 — large hamming distance and large dimension change
#                    3-4 — hamming distance less than 10 and dimensions close
#                    5-6 — hamming distance close (4-6) and dimensions almost exactly same

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

    async def http_get(self, url: str) -> tuple[aiohttp.ClientResponse, Union[list, dict]]:
        async with self.session.get(url, headers=self.headers) as response:
            return response, await response.json()

    async def http_head(self, url: str) -> aiohttp.ClientResponse:
        async with self.session.head(url, headers=self.headers) as response:
            return response

    async def check_hash(self, p_hash: Union[imagehash.ImageHash, str], dimensions: list[int]) -> bool:
        url = f"https://api.excessive.space/v1/scamscore?hash={str(p_hash)}&dimensions={dimensions[0]},{dimensions[1]}"
        print("DEBUG " + f"{url = }")
        response, data = await self.http_get(url)
        print("DEBUG " + f"{data = }")
        print("DEBUG " + f"{response.status = }")
        if response.status == 404:
            print("DEBUG " + "MISS")
            return False
        if "result" in data and int(data["result"]) >= HOW_CLOSE:
            print("DEBUG " + "HIT")
            return True
        raise ValueError(f"Website returned status '{response.status}' instead of 200 or 404")

    async def get_hash(self, url: str) -> tuple[imagehash.ImageHash, list]:
        image = await self.download_image(url)
        return phash(image), dimensions(image)

