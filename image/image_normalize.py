from typing import Union

from wand.image import Image
from io import BytesIO
import asyncio

from exceptions import SentryBotException

async def convert_to_png_async(image_in) -> BytesIO:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, convert_to_png, image_in)
    if result is not None:
        return result
    else:
        raise SentryBotException("Could not convert to PNG")

def convert_to_png(image_in: BytesIO) -> Union[BytesIO, None]:
    try:
        image_out = BytesIO()
        with Image(file=image_in) as image:
            image.convert("PNG")
            image.save(image_out)
        image_out.seek(0)
        return image_out
    except Exception:
        return None