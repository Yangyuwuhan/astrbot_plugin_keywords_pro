import random
import urllib.parse
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import astrbot.api.message_components as Comp


class MessageSender:
    def __init__(self, plugin_data_dir: Path, webui_base_url: str):
        self.plugin_data_dir = plugin_data_dir
        self.webui_base_url = webui_base_url.rstrip("/")

    def _replace_variables(self, text: str) -> str:
        """替换文本中的变量"""
        now = datetime.now()

        # 星期几中文映射
        weekdays = [
            "星期一",
            "星期二",
            "星期三",
            "星期四",
            "星期五",
            "星期六",
            "星期日",
        ]
        day_of_week = weekdays[now.weekday()]

        # 替换变量
        text = text.replace("{time}", now.strftime("%H:%M:%S"))
        text = text.replace("{date}", now.strftime("%Y-%m-%d"))
        text = text.replace("{datetime}", now.strftime("%Y-%m-%d %H:%M:%S"))
        text = text.replace("{random}", str(random.randint(1, 100)))
        text = text.replace("{day_of_week}", day_of_week)

        return text

    def build_response_chains(
        self, response: dict, keyword: str = ""
    ) -> Generator[list, None, None]:
        chain_text_image = []

        if response.get("text"):
            # 替换文本中的变量
            text = self._replace_variables(response["text"])
            chain_text_image.append(Comp.Plain(text=text))

        # 确定当前关键词的目录（不再直接使用本地路径，而是通过URL访问）

        for img in response.get("image", []):
            if img:
                # 使用URL方式访问图片，解决跨平台访问问题
                encoded_filename = urllib.parse.quote(img)
                if keyword:
                    encoded_keyword = urllib.parse.quote(keyword)
                    image_url = f"{self.webui_base_url}/files/{encoded_filename}?keyword={encoded_keyword}"
                else:
                    image_url = f"{self.webui_base_url}/files/{encoded_filename}"
                chain_text_image.append(Comp.Image.fromURL(url=image_url))

        if chain_text_image:
            yield chain_text_image

        for vid in response.get("video", []):
            if vid:
                yield [self._video_from_file(vid, keyword)]

        for file in response.get("file", []):
            if file:
                yield [self._file_from_file(file, keyword)]

    def _video_from_file(self, filename: str, keyword: str = "") -> Comp.Video:
        encoded_filename = urllib.parse.quote(filename)
        if keyword:
            encoded_keyword = urllib.parse.quote(keyword)
            video_url = f"{self.webui_base_url}/files/{encoded_filename}?keyword={encoded_keyword}"
        else:
            video_url = f"{self.webui_base_url}/files/{encoded_filename}"
        return Comp.Video.fromURL(url=video_url)

    def _file_from_file(self, filename: str, keyword: str = "") -> Comp.File:
        encoded_filename = urllib.parse.quote(filename)
        if keyword:
            encoded_keyword = urllib.parse.quote(keyword)
            file_url = f"{self.webui_base_url}/files/{encoded_filename}?keyword={encoded_keyword}"
        else:
            file_url = f"{self.webui_base_url}/files/{encoded_filename}"
        return Comp.File(name=filename, url=file_url)
