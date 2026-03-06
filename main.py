import asyncio
import json
import os
import random
import time
import urllib.parse

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .webui import WebServer


class KeywordsProPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        # 数据目录：AstrBot/data/keywords_data/
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "keywords_data",
        )
        self.data_dir = os.path.abspath(self.data_dir)
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"创建关键词数据目录: {self.data_dir}")

        self.keywords_file = os.path.join(self.data_dir, "keywords.json")
        self.keywords_data = self._load_keywords()
        self._validate_keywords_files()
        self.call_counter = []
        self._init_default_config()

        # WebUI 基础 URL，用于构造文件的 HTTP 地址（需外部可访问）
        self.webui_base_url = self.config.get(
            "webui_base_url", "http://127.0.0.1:5678"
        ).rstrip("/")

        self._keywords_lock = asyncio.Lock()

        self.web_server = WebServer(self, host="0.0.0.0", port=5678)
        asyncio.create_task(self._start_web_server())

    async def _start_web_server(self):
        await self.web_server.start()

    def _init_default_config(self):
        defaults = {
            "need_wake": False,
            "whitelist": [],
            "blacklist": [],
            "max_calls_per_minute": 30,
            "webui_password": "keywords@pro",
            "webui_base_url": "http://127.0.0.1:5678",  # 新增：文件访问基础 URL
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def _load_keywords(self):
        if os.path.exists(self.keywords_file):
            try:
                with open(self.keywords_file, encoding="utf-8") as f:
                    data = json.load(f)
                modified = False
                now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
                for kw, item in data.items():
                    responses = item.get("responses", [])
                    for resp in responses:
                        if "image" in resp and isinstance(resp["image"], str):
                            resp["image"] = [resp["image"]] if resp["image"] else []
                        if "video" in resp and isinstance(resp["video"], str):
                            resp["video"] = [resp["video"]] if resp["video"] else []
                    if "created_at" not in item:
                        item["created_at"] = now
                        modified = True
                    if "updated_at" not in item:
                        item["updated_at"] = now
                        modified = True
                if modified:
                    self._save_keywords(data)
                return data
            except Exception as e:
                logger.error(f"加载关键词文件失败: {e}")
                return {}
        else:
            now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            default_data = {
                "示例关键词": {
                    "aliases": ["例子", "示例"],
                    "responses": [
                        {"text": "这是一个示例回复", "image": [], "video": []},
                        {"text": "示例多张图片", "image": ["example.jpg"], "video": []},
                    ],
                    "created_at": now,
                    "updated_at": now,
                }
            }
            logger.info(f"关键词文件不存在，创建默认关键词数据: {self.keywords_file}")
            self._save_keywords(default_data)
            return default_data

    def _save_keywords(self, data):
        try:
            with open(self.keywords_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存关键词文件失败: {e}")

    def _validate_keywords_files(self):
        modified = False
        for keyword, data in self.keywords_data.items():
            responses = data.get("responses", [])
            for resp in responses:
                for media_type in ["image", "video"]:
                    files = resp.get(media_type)
                    if not files:
                        continue
                    if isinstance(files, str):
                        files = [files] if files else []
                        resp[media_type] = files
                    if not isinstance(files, list):
                        continue
                    original = files[:]
                    files[:] = [f for f in files if self._file_exists(f)]
                    if len(files) != len(original):
                        modified = True
                        removed = set(original) - set(files)
                        logger.warning(
                            f"关键词 [{keyword}] 的 {media_type} 文件不存在，已自动移除: {removed}"
                        )
        if modified:
            self._save_keywords(self.keywords_data)

    def _file_exists(self, filename: str) -> bool:
        if not filename:
            return False
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            return False
        file_path = os.path.join(self.data_dir, filename)
        return os.path.isfile(file_path)

    def _check_rate_limit(self):
        current_time = time.time()
        self.call_counter = [t for t in self.call_counter if current_time - t < 60]
        if len(self.call_counter) >= self.config.get("max_calls_per_minute", 30):
            return False
        self.call_counter.append(current_time)
        return True

    def _check_whitelist_blacklist(self, event):
        if event.is_private_chat():
            session_identifier = f"#{event.get_sender_id()}"
        else:
            group_id = event.get_group_id()
            if not group_id:
                return True
            session_identifier = f"@{group_id}"
        whitelist = self.config.get("whitelist", [])
        if whitelist and session_identifier not in whitelist:
            return False
        blacklist = self.config.get("blacklist", [])
        if session_identifier in blacklist:
            return False
        return True

    def _get_response_message(self, response):
        chain = []
        if "text" in response and response["text"]:
            chain.append(Comp.Plain(text=response["text"]))
        if "image" in response:
            images = response["image"]
            if isinstance(images, list):
                for image_path in images:
                    if image_path:
                        if not os.path.isabs(image_path):
                            image_path = os.path.join(self.data_dir, image_path)
                        chain.append(Comp.Image.fromFileSystem(image_path))
            elif images:
                image_path = images
                if not os.path.isabs(image_path):
                    image_path = os.path.join(self.data_dir, image_path)
                chain.append(Comp.Image.fromFileSystem(image_path))
        return chain

    def _video_from_file(self, filename: str) -> Comp.Video:
        """
        根据文件名构造可通过 Web 访问的视频组件。
        文件必须位于 data_dir 目录下。
        """
        encoded_filename = urllib.parse.quote(filename)
        video_url = f"{self.webui_base_url}/files/{encoded_filename}"
        return Comp.Video(file=video_url)

    def _get_video_message(self, response):
        """
        构造视频消息链，返回每个视频单独的消息链列表。
        使用 _video_from_file 方法生成视频组件。
        """
        chains = []
        if "video" in response:
            videos = response["video"]
            if isinstance(videos, list):
                for video_path in videos:
                    if video_path:
                        chain = []
                        filename = os.path.basename(video_path)
                        chain.append(self._video_from_file(filename))
                        chains.append(chain)
            elif videos:
                chain = []
                filename = os.path.basename(videos)
                chain.append(self._video_from_file(filename))
                chains.append(chain)
        return chains

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if self.config.get("need_wake", False) and not event.is_wake:
            return
        if not self._check_whitelist_blacklist(event):
            return
        if not self._check_rate_limit():
            return
        message_text = event.message_str.strip()
        matched_keyword = None
        matched_alias = None
        for keyword, data in self.keywords_data.items():
            if message_text == keyword:
                matched_keyword = keyword
                matched_alias = None
                break
            aliases = data.get("aliases", [])
            if message_text in aliases:
                matched_keyword = keyword
                matched_alias = message_text
                break
        if matched_keyword:
            event.call_llm = False
            if matched_alias:
                logger.info(
                    f"触发关键词: {matched_keyword} (通过别名: {matched_alias})"
                )
            else:
                logger.info(f"触发关键词: {matched_keyword}")
            keyword_data = self.keywords_data[matched_keyword]
            responses = keyword_data.get("responses", [])
            if not responses:
                return
            if len(responses) > 1:
                response = random.choice(responses)
            else:
                response = responses[0]
            message_chain = self._get_response_message(response)
            if message_chain:
                yield event.chain_result(message_chain)
            video_chains = self._get_video_message(response)
            for video_chain in video_chains:
                if video_chain:
                    yield event.chain_result(video_chain)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("keywords")
    async def list_keywords(self, event: AstrMessageEvent):
        if not self.keywords_data:
            yield event.plain_result("当前没有设置关键词")
            return
        result = []
        for keyword, data in self.keywords_data.items():
            aliases = data.get("aliases", [])
            if aliases:
                result.append(f"{keyword}（{', '.join(aliases)}）")
            else:
                result.append(keyword)
        yield event.plain_result("\n".join(result))

    async def terminate(self):
        if hasattr(self, "web_server"):
            await self.web_server.stop()
