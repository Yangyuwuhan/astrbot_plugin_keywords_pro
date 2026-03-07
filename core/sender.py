import urllib.parse
from collections.abc import Generator
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import logger


class MessageSender:
    def __init__(self, data_dir: Path, webui_base_url: str):
        self.data_dir = data_dir
        self.webui_base_url = webui_base_url.rstrip("/")

    def build_response_chains(self, response: dict) -> Generator[list, None, None]:
        chain_text_image = []

        if response.get("text"):
            chain_text_image.append(Comp.Plain(text=response["text"]))

        for img in response.get("image", []):
            if img:
                img_path = self.data_dir / img
                if img_path.exists():
                    chain_text_image.append(Comp.Image.fromFileSystem(str(img_path)))
                else:
                    logger.warning(f"图片文件不存在: {img_path}")

        if chain_text_image:
            yield chain_text_image

        for vid in response.get("video", []):
            if vid:
                yield [self._video_from_file(vid)]

    def _video_from_file(self, filename: str) -> Comp.Video:
        encoded = urllib.parse.quote(filename)
        video_url = f"{self.webui_base_url}/files/{encoded}"
        return Comp.Video.fromURL(url=video_url)
