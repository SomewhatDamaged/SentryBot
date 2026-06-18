import imagehash
from PIL import Image

HASH_SIZE = 16

def phash(image: Image.Image) -> imagehash.ImageHash:
    return imagehash.phash(image, hash_size=HASH_SIZE)
