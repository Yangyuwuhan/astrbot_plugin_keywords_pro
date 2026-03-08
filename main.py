import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

from croniter import croniter

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .core import config as cfg
from .core import sender, utils, webui


class KeywordsProPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

        _data_root = get_astrbot_data_path()
        # 数据目录：遵循 AstrBot 插件存储规范，存储于 data/plugin_data/{plugin_name}/ 目录下
        plugin_data_path = (
            Path(_data_root)
            / "plugin_data"
            / (self.name if hasattr(self, "name") else "astrbot_plugin_keywords_pro")
        )
        self.data_dir = plugin_data_path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"关键词数据目录: {self.data_dir}")

        self.config_mgr = cfg.ConfigManager(self.config)
        self.keywords_data = self._load_keywords()
        self._validate_keywords_files()
        self.sender = sender.MessageSender(
            plugin_data_dir=self.data_dir,
            webui_base_url=self.config_mgr.get_webui_base_url(),
        )
        self._keywords_lock = asyncio.Lock()
        self._scheduler_lock = asyncio.Lock()
        self.cron_jobs: dict[str, asyncio.Task] = {}

        self.web_server = webui.WebServer(self, host="0.0.0.0", port=5678)
        asyncio.create_task(self._start_web_server())

        asyncio.create_task(self._schedule_cron_jobs())

    async def _start_web_server(self):
        await self.web_server.start()

    def _load_keywords(self):
        """加载关键词数据，并确保每个关键词拥有必要字段"""
        default_cron_config = {"cron_expression": "", "whitelist": [], "blacklist": []}
        data = {}

        # 遍历关键词目录
        for keyword_dir in self.data_dir.iterdir():
            if keyword_dir.is_dir():
                keyword = keyword_dir.name
                keyword_file = keyword_dir / "keywords.json"
                if keyword_file.exists():
                    try:
                        with open(keyword_file, encoding="utf-8") as f:
                            keyword_data = json.load(f)
                        # 确保必要字段存在
                        modified = False
                        now = utils.current_time_iso()
                        if "created_at" not in keyword_data:
                            keyword_data["created_at"] = now
                            modified = True
                        if "updated_at" not in keyword_data:
                            keyword_data["updated_at"] = now
                            modified = True
                        if "need_wake" not in keyword_data:
                            keyword_data["need_wake"] = True
                            modified = True
                        if "regex_match" not in keyword_data:
                            keyword_data["regex_match"] = False
                            modified = True
                        if "cron_enabled" not in keyword_data:
                            keyword_data["cron_enabled"] = False
                            modified = True
                        if "cron_config" not in keyword_data:
                            keyword_data["cron_config"] = default_cron_config.copy()
                            modified = True
                        if "aliases" not in keyword_data:
                            keyword_data["aliases"] = []
                            modified = True
                        if "responses" not in keyword_data:
                            keyword_data["responses"] = []
                            modified = True
                        if "enabled" not in keyword_data:
                            keyword_data["enabled"] = True
                            modified = True
                        # 标准化媒体字段
                        responses = keyword_data.get("responses", [])
                        for resp in responses:
                            utils.normalize_media(resp)
                        if modified:
                            self._save_keyword(keyword, keyword_data)
                        data[keyword] = keyword_data
                    except Exception as e:
                        logger.error(f"加载关键词 {keyword} 文件失败: {e}")

        # 如果没有关键词，创建默认关键词
        if not data:
            now = utils.current_time_iso()
            default_keyword = "示例关键词"
            default_data = {
                "aliases": ["例子", "示例"],
                "responses": [
                    {"text": "这是一个示例回复", "image": [], "video": []},
                    {"text": "示例多张图片", "image": ["example.jpg"], "video": []},
                ],
                "created_at": now,
                "updated_at": now,
                "need_wake": True,  # 默认需要唤醒
                "regex_match": False,
                "cron_enabled": False,
                "cron_config": default_cron_config,
                "enabled": True,  # 默认启用
            }
            self._save_keyword(default_keyword, default_data)
            data[default_keyword] = default_data

        return data

    def _save_keyword(self, keyword: str, data: dict):
        """保存单个关键词的数据"""
        keyword_dir = self.data_dir / keyword
        keyword_dir.mkdir(parents=True, exist_ok=True)
        keyword_file = keyword_dir / "keywords.json"
        try:
            with open(keyword_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存关键词 {keyword} 文件失败: {e}")

    def _save_keywords(self, data):
        """保存所有关键词数据"""
        for keyword, keyword_data in data.items():
            self._save_keyword(keyword, keyword_data)

    def _validate_keywords_files(self):
        modified = False
        for keyword, data in self.keywords_data.items():
            keyword_dir = self.data_dir / keyword
            responses = data.get("responses", [])
            for resp in responses:
                for media_type in ["image", "video", "file"]:
                    files = resp.get(media_type, [])
                    if not files:
                        continue
                    original = files[:]
                    files[:] = [f for f in files if utils.file_exists(keyword_dir, f)]
                    if len(files) != len(original):
                        modified = True
                        removed = set(original) - set(files)
                        logger.warning(
                            f"关键词 [{keyword}] 的 {media_type} 文件不存在，已自动移除: {removed}"
                        )
        if modified:
            self._save_keywords(self.keywords_data)

    # ---------- 消息处理 ----------
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """处理用户消息，匹配关键词并回复"""
        # 全局黑白名单、限流检查
        if not self.config_mgr.check_whitelist_blacklist(event):
            return
        if not self.config_mgr.check_rate_limit():
            return

        message_text = event.message_str.strip()
        if not message_text:
            return

        matched_keyword = None
        matched_alias = None
        keyword_data = None

        # 判断机器人是否被唤醒（优先使用 is_at_or_wake_command，否则用 is_wake）
        is_awake = getattr(event, "is_at_or_wake_command", event.is_wake)

        for keyword, data in self.keywords_data.items():
            # 检查是否启用
            if not data.get("enabled", True):
                continue
            # 检查是否需要唤醒
            if data.get("need_wake", True) and not is_awake:
                continue

            # 检查是否匹配（正则或精确）
            if data.get("regex_match", False):
                # 包含匹配
                try:
                    import re

                    # 检查关键词
                    if re.search(keyword, message_text):
                        matched_keyword = keyword
                        keyword_data = data
                        break
                    # 检查别名
                    for alias in data.get("aliases", []):
                        if re.search(alias, message_text):
                            matched_keyword = keyword
                            matched_alias = alias
                            keyword_data = data
                            break
                    else:
                        # 如果没有匹配到别名，继续下一个关键词
                        continue
                    break
                except re.error as e:
                    logger.error(f"正则表达式错误 [{keyword}]: {e}")
                    continue
            else:
                # 精确匹配
                if message_text == keyword:
                    matched_keyword = keyword
                    keyword_data = data
                    break
                if message_text in data.get("aliases", []):
                    matched_keyword = keyword
                    matched_alias = message_text
                    keyword_data = data
                    break

        if matched_keyword:
            event.call_llm = False
            log_msg = f"触发关键词: {matched_keyword}"
            if matched_alias:
                log_msg += f" (通过别名: {matched_alias})"
            logger.info(log_msg)

            responses = keyword_data.get("responses", [])
            if not responses:
                return

            response = random.choice(responses) if len(responses) > 1 else responses[0]
            for chain in self.sender.build_response_chains(response, matched_keyword):
                if chain:
                    yield event.chain_result(chain)

    # ---------- 指令 ----------
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("keywords")
    async def list_keywords(self, event: AstrMessageEvent):
        """列出所有关键词"""
        if not self.keywords_data:
            yield event.plain_result("当前没有设置关键词")
            return
        lines = []
        for keyword, data in self.keywords_data.items():
            aliases = data.get("aliases", [])
            lines.append(f"{keyword}（{', '.join(aliases)}）" if aliases else keyword)
        yield event.plain_result("\n".join(lines))

    # ---------- 定时任务调度 ----------
    async def _schedule_cron_jobs(self):
        async with self._scheduler_lock:
            for job in self.cron_jobs.values():
                job.cancel()
            self.cron_jobs.clear()
            for keyword, data in self.keywords_data.items():
                if data.get("cron_enabled", False):
                    self._add_cron_job(keyword, data)

    async def _reschedule_cron_jobs(self):
        await self._schedule_cron_jobs()

    def _add_cron_job(self, keyword: str, data: dict):
        cron_config = data.get("cron_config", {})
        expr = cron_config.get("cron_expression", "")
        if not expr:
            return

        async def cron_task():
            try:
                await self._execute_cron(keyword, data)
            except Exception as e:
                logger.error(f"定时任务执行失败 [{keyword}]: {e}")

        async def schedule_loop():
            while True:
                now = datetime.now()
                try:
                    iter = croniter(expr, now)
                    next_time = iter.get_next(datetime)
                except Exception as e:
                    logger.error(f"Cron表达式解析失败 [{keyword}]: {expr} - {e}")
                    break
                wait_seconds = (next_time - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                asyncio.create_task(cron_task())

        task = asyncio.create_task(schedule_loop())
        self.cron_jobs[keyword] = task

    async def _execute_cron(self, keyword: str, data: dict):
        cron_config = data.get("cron_config", {})
        whitelist = cron_config.get("whitelist") or []
        blacklist = cron_config.get("blacklist") or []

        if not whitelist:
            return

        responses = data.get("responses", [])
        if not responses:
            return
        response = random.choice(responses) if len(responses) > 1 else responses[0]

        for target in whitelist:
            if target in blacklist:
                continue
            if not self._is_allowed_by_global(target):
                continue

            if target.startswith("#"):
                uid = target[1:]
                # 私聊消息类型，使用 MessageType 枚举值
                msg_type = "FriendMessage"
                umo = f"aiocqhttp:{msg_type}:{uid}"
                logger.debug(f"构造私聊 unified_msg_origin: {umo}")
            elif target.startswith("@"):
                gid = target[1:]
                # 群聊消息类型，使用 MessageType 枚举值
                msg_type = "GroupMessage"
                umo = f"aiocqhttp:{msg_type}:{gid}"
                logger.debug(f"构造群聊 unified_msg_origin: {umo}")
            else:
                logger.warning(f"无效的目标会话标识: {target}")
                continue

            # 尝试使用不同的平台 ID 格式发送消息
            platform_ids = []
            # 首先尝试使用配置的平台 ID
            for platform in self.context.platform_manager.get_insts():
                if platform.meta().name == "aiocqhttp":
                    platform_ids.append(platform.meta().id)

            # 尝试向每个可能的平台 ID 发送消息
            sent = False
            for platform_id in platform_ids:
                try:
                    # 重新构造 unified_msg_origin
                    new_umo = f"{platform_id}:{msg_type}:{uid if target.startswith('#') else gid}"
                    for chain_components in self.sender.build_response_chains(
                        response, keyword
                    ):
                        if chain_components:
                            # 将消息组件列表转换为 MessageChain 对象
                            message_chain = MessageChain(chain=chain_components)
                            result = await self.context.send_message(
                                new_umo, message_chain
                            )
                            if result:
                                sent = True
                    if sent:
                        break
                except Exception as e:
                    logger.error(f"发送消息到平台 {platform_id} 失败: {e}")

            if not sent:
                logger.warning(
                    f"无法发送定时消息到目标 {target}，没有找到可用的 aiocqhttp 平台"
                )

            await asyncio.sleep(0.5)

    def _is_allowed_by_global(self, session_identifier: str) -> bool:
        whitelist = self.config_mgr.get("whitelist") or []
        blacklist = self.config_mgr.get("blacklist") or []
        if whitelist and session_identifier not in whitelist:
            return False
        if session_identifier in blacklist:
            return False
        return True

    async def terminate(self):
        async with self._scheduler_lock:
            for job in self.cron_jobs.values():
                job.cancel()
            self.cron_jobs.clear()
        if hasattr(self, "web_server"):
            await self.web_server.stop()
