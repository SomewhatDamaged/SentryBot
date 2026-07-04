import asyncio
import functools
import os
from io import BytesIO
from PIL import Image
import easyocr
import logging
from mock_logging import MockLogger

log = logging.getLogger()
if log is not None:
    log = MockLogger()


async def ocr(image: Image.Image) -> int:
    if not os.path.exists(".models"):
        os.mkdir(".models")
    if not os.path.exists(".network"):
        os.mkdir(".network")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    loop = asyncio.get_event_loop()
    blocking_io = functools.partial(blocking_ocr, image=image_bytes)
    result = await loop.run_in_executor(None, blocking_io)
    scam_score: int = 0 # Let's just make a metric!
    for datum in result:
        if "mrbeast" in datum.lower():
            scam_score += 10
        if "elon musk" in datum.lower():
            scam_score += 10
        if "cryptocurrency" in datum.lower():
            scam_score += 10
        if "casino" in datum.lower():
            scam_score += 5
        if "giving away" in datum.lower():
            scam_score += 5
        if "withdrawal" in datum.lower() and "successfull" in datum.lower():
            scam_score += 10
        if "money" in datum.lower() and "transfer" in datum.lower():
            scam_score += 10
        if "crypto" in datum.lower():
            scam_score += 5
        if "vip-club" in datum.lower():
            scam_score += 10
        if "promo code" in datum.lower():
            scam_score += 5
    return scam_score

def blocking_ocr(image: BytesIO) -> list:
    reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=".models", user_network_directory=".network", verbose=False)
    try:
        return reader.readtext(image=image.getvalue(), detail=0)
    except Exception:
        return []
