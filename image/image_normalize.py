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
            detected_format = str(image.format).upper() if image.format else ""
            detected_mime = str(image.mimetype).lower() if image.mimetype else ""
            if (
                    "HEIC" in detected_format or
                    "HEIF" in detected_format or
                    "AVIF" in detected_format or
                    "heif" in detected_mime or
                    "heic" in detected_mime or
                    "avif" in detected_mime
            ):
                detected_formats = detected_format if detected_format else detected_mime
                raise ValueError(f"Forbidden file format detected: {detected_formats}")
                # Because XKCD https://xkcd.com/2347/ and https://heif-heist.com/
            image.convert("PNG")
            image.save(image_out)
        image_out.seek(0)
        return image_out
    except ValueError as e:
        if str(e).startswith("Forbidden file format detected: "):
            return str(e)
    except Exception:
        return None