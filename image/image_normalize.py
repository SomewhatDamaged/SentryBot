from wand.image import Image
from io import BytesIO
import asyncio

async def convert_to_png_async(image_in) -> BytesIO:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, convert_to_png, image_in)

def convert_to_png(image_in: BytesIO) -> BytesIO:
    image_out = BytesIO()
    with Image(file=image_in) as image:
        image.convert("PNG")
        image.save(image_out)
    image_out.seek(0)
    return image_out