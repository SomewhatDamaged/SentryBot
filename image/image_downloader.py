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
import os
import json

log = MockLogger()

AI_MODEL = "@cf/moondream/moondream3.1-9B-A2B"
PROMPT = """OCR this image. Output in JSON format:
{
  'text': a field that contains all the recognizable text
  'scam': with the json values of \"false\" if it's not likely a scam, \"true\" if it is a scam
}"""


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
        self.headers = {"User-Agent": useragent}
        if os.path.exists(".cloudflare_config.json"):
            with open(".cloudflare_config.json", "r") as config:
                self.cloudflare_config = json.load(config)
        if os.path.exists("keywords.json"):
            with open("keywords.json", "r") as file:
                self.keywords = json.load(file)

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

    async def get_hash(self, url: str) -> tuple[list[tuple[imagehash.ImageHash, list[int], str]],Union[dict, None]]:
        image = await self.download_image(url)
        log.debug("Trying OCR")
        ocr_data = await self.ocr(image)
        log.debug(f"OCR Result: {ocr_data}")
        hash_data: list[tuple[imagehash.ImageHash, list[int], str]] = []
        images = await split_two_images_async(image)
        for data in images:
            image = Image.open(data["image"])
            result = (phash(image), dimensions(image), data["type"])
            hash_data.append(result)
        return hash_data, ocr_data

    async def ocr(self, image: io.BytesIO) -> Union[dict, None]:
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
            "Content-Type": "application/json"
        }
        data = {
            "image": data_url,
            "task": "query",
            "question": PROMPT,
            "stream": True,
            "reasoning": True,
        }

        output: dict = {
            "answer":
                {
                    "text": "",
                    "scam": False
                },
            "reasoning": "",
            "score": 0
        }
        try:
            response = await self.session.post(url, json=data, headers=headers)
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
                                    values = json.loads(data_chunk["output"][-1]["answer"])
                                    log.debug(values)
                                    output["answer"]["text"] = normalize_to_str(values.get("text", ""))
                                    output["answer"]["scam"] = normalize_to_bool(values.get("scam", False))
                                    json.loads(data_chunk["output"][-1]["answer"])
                                    output["reasoning"] = data_chunk["output"][-1]["reasoning"]["text"]
                                    output["score"] = self.keyword_score(output["answer"]["text"])
                                    break
                            except json.JSONDecodeError:
                                continue
                return output
            else:
                response_text = await response.text()
                log.error(f"❌ Cloudflare REST API Error [HTTP {response.status}]: {response_text}")
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            log.exception(f"❌ Network execution failed while processing aiohttp request: {e}")
        return None

    def keyword_score(self, text: str) -> int:
        score = 0
        text = text.lower()
        for words in self.keywords:
            if words in text:
                score += 1
        return score

def normalize_to_bool(data: Any) -> bool:
    if isinstance(data, bool):
        return data
    if isinstance(data, str):
        if data.lower() == "true":
            return True
    return False

def normalize_to_str(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        return data.decode('utf-8')
    if isinstance(data, list):
        return " ".join(data)
    return str(data)