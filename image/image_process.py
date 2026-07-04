import imagehash
from PIL import Image

from image.ocr import ocr


HASH_SIZE = 16

def phash(image: Image.Image) -> imagehash.ImageHash:
    return imagehash.phash(image, hash_size=HASH_SIZE)

def dimensions(image: Image.Image) -> list[int]:
    return list(image.size)

async def scam_score(image: Image.Image) -> int:
    return await ocr(image)