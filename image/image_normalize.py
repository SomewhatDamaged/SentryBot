from typing import Union

from wand.image import Image
from io import BytesIO
import asyncio

from sentrybot_exceptions import SentryBotException

async def convert_to_png_async(image_in) -> BytesIO:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, convert_to_png, image_in)
    if isinstance(result, BytesIO):
        return result
    elif isinstance(result, str):
        raise SentryBotException(result)
    else:
        raise SentryBotException("Could not convert to PNG")

def convert_to_png(image_in: BytesIO) -> Union[BytesIO, None, str]:
    try:
        image_out = BytesIO()
        with Image(file=image_in) as image:
            check_format(image.mimetype, image.format)
            image.convert("PNG")
            image.save(image_out)
        image_out.seek(0)
        return image_out
    except ValueError as e:
        if str(e).startswith("Forbidden file format detected: "):
            return str(e)
    except Exception:
        return None

def check_format(image_mime: Union[str,None], image_format: Union[str,None]):
    """Will raise a ValueError if image_mime or image_format are not supported"""
    forbidden_formats = []
    forbidden_formats += ["HEIF", "HEIC", "AVIF"] # Because XKCD https://xkcd.com/2347/ and https://heif-heist.com/
    image_format = image_format.upper() if image_format else ""
    image_mime = image_mime.upper() if image_mime else ""
    for formats in forbidden_formats:
        if formats in image_mime or formats in image_format:
            raise ValueError(f"Forbidden file format detected: {formats}")