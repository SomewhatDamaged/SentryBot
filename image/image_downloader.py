import asyncio
from typing import Union, Any

import aiohttp
import io

import imagehash
import base64

from mock_logging import MockLogger
from .image_process import phash, dimensions
from .image_normalize import convert_to_png_async
from PIL import Image
from sentrybot_exceptions import SentryBotException, NotImageException, URLException
from .split_images import split_two_images_async
from .compare import TextCompare
import os
import json

log = MockLogger()

AI_MODEL = "@cf/moondream/moondream3.1-9B-A2B"
PROMPT = """OCR this image. Only output the OCRed text."""
POLLING_DELAY = 5 # polling delay to get new scam strings in minutes

# make your own useragent file that has your email in it

HOW_CLOSE: int = 4 # This is a measure of how similar images should be. If they match exactly, or are within 3 distance, it will always be 8-10
#                    If the image has had a little more editing done, and the dimensions are almost the same, it will give a scale:
#                    1-2 — large hamming distance and large dimension change
#                    3-4 — hamming distance less than 10 and dimensions close
#                    5-6 — hamming distance close (4-6) and dimensions almost exactly same

class Downloader:
    cloudflare_config: Union[dict, None] = None
    keywords: list[str] = []
    def __init__(self, useragent: str):
        self.session = aiohttp.ClientSession()
        self.headers = {"user-agent": useragent}
        if os.path.exists(".cloudflare_config.json"):
            with open(".cloudflare_config.json", "r") as config:
                self.cloudflare_config = json.load(config)
        if os.path.exists("keywords.json"):
            with open("keywords.json", "r") as file:
                self.keywords = json.load(file)
        self.text_hashing = TextCompare()


    async def close(self):
        await self.session.close()

    async def update_string_hashes(self):
        while True:
            try:
                url = "https://api.excessive.space/v1/scam_strings_list"
                response, data = await self.http_get(url)
                if response.status != 200:
                    raise SentryBotException(f"scam_string_list endpoint seems broken (status: {response.status})")
                if data and isinstance(data, list):
                    self.text_hashing.build_hash_index(data)
                    self.text_hashing.known_scams = data
                else:
                    raise SentryBotException("scam_string_list endpoint isn't returning a list!")
            except Exception:
                log.exception("Exception raised in update_string_hashes")
            await asyncio.sleep(POLLING_DELAY * 60)

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

    async def http_post(self, url: str, headers: dict, data: dict) -> aiohttp.ClientResponse:
        headers = {**self.headers, **headers}
        return await self.session.post(url, headers=headers, json=data)

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

    async def get_hash(self, url: str) -> tuple[list[tuple[imagehash.ImageHash, list[int], str]],Union[dict, None]]:
        image = await self.download_image(url)
        ocr_result = self.analyze_ocr(await self.ocr(image))
        hash_data: list[tuple[imagehash.ImageHash, list[int], str]] = []
        images = await split_two_images_async(image)
        for data in images:
            image = Image.open(data["image"])
            result = (phash(image), dimensions(image), data["type"])
            hash_data.append(result)
        return hash_data, ocr_result

    async def ocr(self, image: io.BytesIO) -> Union[str, None]:
        if self.cloudflare_config is None:
            return None
        if 'ACCOUNT_ID' not in self.cloudflare_config:
            return None
        if 'CLOUDFLARE_API_TOKEN' not in self.cloudflare_config:
            return None

        image.seek(0)
        raw_image_bytes = image.getvalue()
        base64_encoded = base64.b64encode(raw_image_bytes).decode('utf-8')
        data_url = f"data:image/png;base64,{base64_encoded}"

        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_config['ACCOUNT_ID']}/ai/run/{AI_MODEL}"
        headers = {
            "Authorization": f"Bearer {self.cloudflare_config['CLOUDFLARE_API_TOKEN']}",
            "cf-aig-gateway-id": self.cloudflare_config['GATEWAY_ID'],
            "Content-Type": "application/json"
        }
        data = {
            "image": data_url,
            "task": "query",
            "question": PROMPT,
            "stream": True,
            "reasoning": True,
        }
        try:
            response = await self.http_post(url, data=data, headers=headers)
            if response.status == 200:
                async with asyncio.timeout(8):
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data_chunk = json.loads(data_str)
                                # Capture the text characters/words
                                if "output" in data_chunk:
                                    output: str = normalize_to_str(data_chunk["output"][-1].get("answer", ""))
                                    return output.replace("\n", " ")
                            except json.JSONDecodeError:
                                continue
            else:
                response_text = await response.text()
                log.error(f"Cloudflare REST API Error [HTTP {response.status}]: {response_text}")
        except asyncio.TimeoutError:
            return None
        except Exception:
            log.exception(f"Something fucked up while processing aiohttp request")
        return None

    def analyze_ocr(self, text: Union[str, None]) -> dict:
        if text is None:
            return {"match": False}
        hit, hit_string, distance = self.text_hashing.check_against_hash_index(text)
        if not hit:
            return {"match": False}
        return {
            "match": True,
            "match_string": hit_string,
            "distance": distance
        }

def normalize_to_str(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        return data.decode('utf-8')
    if isinstance(data, list):
        return " ".join(data)
    return str(data)