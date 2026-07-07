import asyncio
import functools
import logging
from typing import Union, Any

import boto3
import json
import os
import io
from PIL import Image

from mock_logging import MockLogger

log = logging.getLogger()
if log is not None:
    log = MockLogger()


class MyCloudflare:
    client: Union[Any, None] = None
    def __init__(self):
        if os.path.exists(".cloudflare_config.json"):
            with open(".cloudflare_config.json", "r") as config:
                self.cloudflare_config = json.load(config)
        else:
            log.error("Cloudflare config not found!")
            return
        try:
            self.client = boto3.client(
                service_name='s3',
                endpoint_url=self.cloudflare_config["S3_API_ENDPOINT"],
                aws_access_key_id=self.cloudflare_config["ACCESS_KEY_ID"],
                aws_secret_access_key=self.cloudflare_config["SECRET_ACCESS_KEY"],
                region_name="auto",
            )
        except Exception:
            log.error("Cloudflare config is bad!")
            self.client = None
            return

    def close(self):
        if self.client is not None:
            self.client.close()

    def send_to_s3_blocking(self, image: Image.Image, name: str) -> bool:
        try:
            io_image = io.BytesIO()
            image.save(io_image, format="PNG")
            io_image.seek(0)
            self.client.upload_fileobj(io_image, self.cloudflare_config["BUCKET_NAME"], name)
            return True
        except Exception:
            log.exception("Something went wrong!")
            return False

    async def send_to_s3(self, image: Image.Image, name: str) -> bool:
        assert self.client is not None, "Config issue!"
        loop = asyncio.get_event_loop()
        blocking_io = functools.partial(self.send_to_s3_blocking,image, name)
        return await loop.run_in_executor(None, blocking_io)

    def has_folder_blocking(self, name: str, delimiter: str) -> Union[None, int]:
        try:
            result = self.client.list_objects(Bucket=self.cloudflare_config["BUCKET_NAME"], Prefix=name, Delimiter=delimiter)
            if delimiter == '':
                if "Contents" in result and len(result["Contents"]) > 0:
                    return len(result["Contents"])
            elif delimiter == '/':
                if "CommonPrefixes" in result and len(result["CommonPrefixes"]) > 0:
                    return len(result["CommonPrefixes"])
        except Exception:
            log.exception("Something went wrong!")
        return False

    async def has_folder(self, name: str, delimiter: str = '') -> Union[None, int]:
        assert self.client is not None, "Config issue!"
        loop = asyncio.get_event_loop()
        blocking_io = functools.partial(self.has_folder_blocking,name, delimiter)
        return await loop.run_in_executor(None, blocking_io)

