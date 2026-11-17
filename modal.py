from io import BytesIO

from discord import ui
import discord

class ImageSet(ui.Modal, title='Process Upload'):
    images = ui.MediaGallery()

    def __init__(self, images: list[BytesIO]):
        image_list: list[discord.MediaGalleryItem] = []
        for i, image in enumerate(images):
            image_item = discord.File(image, filename=f"image-{i}")
            image_list.append(discord.MediaGalleryItem(image_item))
        self.images = ui.MediaGallery(*image_list)
