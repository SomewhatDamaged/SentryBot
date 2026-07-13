import asyncio
from io import BytesIO

import cv2
import numpy as np

from mock_logging import MockLogger

log = MockLogger()

def is_much_wider_than_tall(img: np.ndarray) -> bool:
    height, width, _ = img.shape
    return True if (width > (height * 1.4) ) else False

def split_two_images(image: BytesIO) -> list[BytesIO]:
    try:
        img = cv2.imdecode(np.frombuffer(image.read(), np.uint8), 1)
        if not is_much_wider_than_tall(img):
            return [image]
        height, width, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        start_col = int(width * 0.20)
        end_col = int(width * 0.80)
        smoothed_gray = cv2.GaussianBlur(gray, (15, 1), 0)
        column_brightness = np.mean(smoothed_gray[:, start_col:end_col], axis=0)
        brightness_gradients = np.abs(np.diff(column_brightness))
        best_relative_cut = np.argmax(brightness_gradients)
        cut_x = start_col + best_relative_cut
        crops = [img[0:height, 0:cut_x], img[0:height, cut_x:width]]
        output: list[BytesIO] = [image]
        for crop in crops:
            image_out = cv2.imencode(".png", crop)[1].tobytes()
            output.append(BytesIO(image_out))
        return output
    except Exception:
        log.exception()
        return [image]

async def split_two_images_async(image: BytesIO) -> list[BytesIO]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, split_two_images, image)