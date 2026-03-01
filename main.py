import json
import os
import random
import time

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star


class KeywordsProPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        # 初始化数据目录
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "keywords_data",
        )
        # 检查并创建目录
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"创建关键词数据目录: {self.data_dir}")
        self.keywords_file = os.path.join(self.data_dir, "keywords.json")
        # 初始化关键词数据
        self.keywords_data = self._load_keywords()
        # 初始化调用计数器
        self.call_counter = []
        # 初始化默认配置
        self._init_default_config()

    def _init_default_config(self):
        """初始化默认配置"""
        # 是否需要唤醒机器人
        if "need_wake" not in self.config:
            self.config["need_wake"] = False
        # 白名单和黑名单
        if "whitelist" not in self.config:
            self.config["whitelist"] = []
        if "blacklist" not in self.config:
            self.config["blacklist"] = []
        # 1分钟内最多调用次数
        if "max_calls_per_minute" not in self.config:
            self.config["max_calls_per_minute"] = 30

    def _load_keywords(self):
        """加载关键词数据"""
        if os.path.exists(self.keywords_file):
            try:
                with open(self.keywords_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载关键词文件失败: {e}")
                return {}
        else:
            # 初始化默认关键词数据
            default_data = {
                "示例关键词": {
                    "aliases": ["例子", "示例"],
                    "responses": [
                        {"text": "这是一个示例回复", "image": "", "video": ""},
                        {"text": "示例多张图片", "image": ["", ""], "video": ""},
                        {"text": "示例多个视频", "image": "", "video": ["", ""]},
                    ],
                }
            }
            logger.info(f"关键词文件不存在，创建默认关键词数据: {self.keywords_file}")
            self._save_keywords(default_data)
            return default_data

    def _save_keywords(self, data):
        """保存关键词数据"""
        try:
            with open(self.keywords_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存关键词文件失败: {e}")

    def _check_rate_limit(self):
        """检查调用频率限制"""
        current_time = time.time()
        # 清理过期的调用记录
        self.call_counter = [t for t in self.call_counter if current_time - t < 60]

        # 检查总调用次数
        if len(self.call_counter) >= self.config.get("max_calls_per_minute", 30):
            return False

        # 记录本次调用
        self.call_counter.append(current_time)
        return True

    def _check_whitelist_blacklist(self, event):
        """检查白名单和黑名单"""
        # 获取会话标识
        if event.is_private_chat():
            session_identifier = f"#{event.get_sender_id()}"
        else:
            group_id = event.get_group_id()
            if not group_id:
                return True
            session_identifier = f"@{group_id}"

        # 检查白名单
        whitelist = self.config.get("whitelist", [])
        if whitelist:
            if session_identifier not in whitelist:
                return False

        # 检查黑名单
        blacklist = self.config.get("blacklist", [])
        if session_identifier in blacklist:
            return False

        return True

    def _get_response_message(self, response):
        """根据响应配置生成消息链"""
        from astrbot.api.message_components import BaseMessageComponent

        chain: list[BaseMessageComponent] = []
        # 处理文本
        if "text" in response and response["text"]:
            chain.append(Comp.Plain(text=response["text"]))
        # 处理图片
        if "image" in response:
            # 检查是否为图片数组
            images = response["image"]
            if isinstance(images, list):
                # 处理多张图片
                for image_path in images:
                    if image_path:
                        if not os.path.isabs(image_path):
                            image_path = os.path.join(self.data_dir, image_path)
                        chain.append(Comp.Image.fromFileSystem(image_path))
            elif images:
                # 处理单张图片
                image_path = images
                if not os.path.isabs(image_path):
                    image_path = os.path.join(self.data_dir, image_path)
                chain.append(Comp.Image.fromFileSystem(image_path))
        return chain

    def _get_video_message(self, response):
        """根据响应配置生成视频消息链"""
        from astrbot.api.message_components import BaseMessageComponent

        chains = []
        # 处理视频
        if "video" in response:
            videos = response["video"]
            if isinstance(videos, list):
                # 处理多个视频
                for video_path in videos:
                    if video_path:
                        chain: list[BaseMessageComponent] = []
                        if not os.path.isabs(video_path):
                            video_path = os.path.join(self.data_dir, video_path)
                        chain.append(Comp.Video(file=video_path))
                        chains.append(chain)
            elif videos:
                # 处理单个视频
                chain: list[BaseMessageComponent] = []
                video_path = videos
                if not os.path.isabs(video_path):
                    video_path = os.path.join(self.data_dir, video_path)
                chain.append(Comp.Video(file=video_path))
                chains.append(chain)
        return chains

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """消息处理函数"""
        # 检查是否需要唤醒
        if self.config.get("need_wake", False) and not event.is_wake:
            return

        # 检查白名单和黑名单
        if not self._check_whitelist_blacklist(event):
            return

        # 检查调用频率
        if not self._check_rate_limit():
            return

        # 获取消息文本
        message_text = event.message_str.strip()

        # 查找匹配的关键词
        matched_keyword = None
        matched_alias = None
        for keyword, data in self.keywords_data.items():
            # 检查关键词本身
            if message_text == keyword:
                matched_keyword = keyword
                matched_alias = None
                break
            # 检查别名
            aliases = data.get("aliases", [])
            if message_text in aliases:
                matched_keyword = keyword
                matched_alias = message_text
                break

        if matched_keyword:
            # 阻止LLM
            event.call_llm = False

            # 输出触发关键词的日志
            if matched_alias:
                logger.info(
                    f"触发关键词: {matched_keyword} (通过别名: {matched_alias})"
                )
            else:
                logger.info(f"触发关键词: {matched_keyword}")

            # 获取回复配置
            keyword_data = self.keywords_data[matched_keyword]
            responses = keyword_data.get("responses", [])

            if not responses:
                return

            # 根据responses长度自动判断模式
            if len(responses) > 1:
                # 多个回复，使用随机模式
                response = random.choice(responses)
            else:
                # 单个回复，使用固定模式
                response = responses[0]

            # 生成消息链
            message_chain = self._get_response_message(response)
            if message_chain:
                yield event.chain_result(message_chain)

            # 处理视频（单独发送）
            video_chains = self._get_video_message(response)
            for video_chain in video_chains:
                if video_chain:
                    yield event.chain_result(video_chain)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("keywords")
    async def list_keywords(self, event: AstrMessageEvent):
        """列出所有关键词及其别名"""
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
        """插件终止时执行"""
        pass
