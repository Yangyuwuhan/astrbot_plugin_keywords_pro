import asyncio
import json
import random
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .core import config as cfg
from .core import sender, utils, webui

# 兼容不同 AstrBot 版本，获取数据根目录
try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path

    _data_root = get_astrbot_data_path()
except ImportError:
    # 旧版本：基于插件位置推算（假设 AstrBot 根目录在 ../../）
    _base = Path(__file__).parent.parent.parent.parent  # 根据实际情况调整
    _data_root = _base / "data"
    logger.warning(f"使用备用数据目录: {_data_root}")


class KeywordsProPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        # 数据目录：AstrBot 数据根目录下的 keywords_data
        self.data_dir = Path(_data_root) / "keywords_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"关键词数据目录: {self.data_dir}")

        self.keywords_file = self.data_dir / "keywords.json"
        self.config_mgr = cfg.ConfigManager(self.config)
        self.keywords_data = self._load_keywords()
        self._validate_keywords_files()
        self.sender = sender.MessageSender(
            data_dir=self.data_dir, webui_base_url=self.config_mgr.get_webui_base_url()
        )
        self._keywords_lock = asyncio.Lock()

        self.web_server = webui.WebServer(self, host="0.0.0.0", port=5678)
        asyncio.create_task(self._start_web_server())

    async def _start_web_server(self):
        await self.web_server.start()

    def _load_keywords(self):
        if self.keywords_file.exists():
            try:
                with open(self.keywords_file, encoding="utf-8") as f:
                    data = json.load(f)
                modified = False
                now = utils.current_time_iso()
                for kw, item in data.items():
                    responses = item.get("responses", [])
                    for resp in responses:
                        utils.normalize_media(resp)
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
            now = utils.current_time_iso()
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
                    files = resp.get(media_type, [])
                    if not files:
                        continue
                    original = files[:]
                    files[:] = [f for f in files if utils.file_exists(self.data_dir, f)]
                    if len(files) != len(original):
                        modified = True
                        removed = set(original) - set(files)
                        logger.warning(
                            f"关键词 [{keyword}] 的 {media_type} 文件不存在，已自动移除: {removed}"
                        )
        if modified:
            self._save_keywords(self.keywords_data)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if self.config_mgr.get("need_wake", False) and not event.is_wake:
            return
        if not self.config_mgr.check_whitelist_blacklist(event):
            return
        if not self.config_mgr.check_rate_limit():
            return

        message_text = event.message_str.strip()
        matched_keyword = None
        matched_alias = None

        for keyword, data in self.keywords_data.items():
            if message_text == keyword:
                matched_keyword = keyword
                break
            if message_text in data.get("aliases", []):
                matched_keyword = keyword
                matched_alias = message_text
                break

        if matched_keyword:
            event.call_llm = False
            log_msg = f"触发关键词: {matched_keyword}"
            if matched_alias:
                log_msg += f" (通过别名: {matched_alias})"
            logger.info(log_msg)

            keyword_data = self.keywords_data[matched_keyword]
            responses = keyword_data.get("responses", [])
            if not responses:
                return

            response = random.choice(responses) if len(responses) > 1 else responses[0]
            for chain in self.sender.build_response_chains(response):
                if chain:
                    yield event.chain_result(chain)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("keywords")
    async def list_keywords(self, event: AstrMessageEvent):
        if not self.keywords_data:
            yield event.plain_result("当前没有设置关键词")
            return
        lines = []
        for keyword, data in self.keywords_data.items():
            aliases = data.get("aliases", [])
            lines.append(f"{keyword}（{', '.join(aliases)}）" if aliases else keyword)
        yield event.plain_result("\n".join(lines))

    async def terminate(self):
        if hasattr(self, "web_server"):
            await self.web_server.stop()
