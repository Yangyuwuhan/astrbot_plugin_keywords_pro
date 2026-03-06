import time
from collections import deque
from typing import Dict, Any


class ConfigManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._init_defaults()
        self.call_timestamps = deque()

    def _init_defaults(self):
        defaults = {
            "need_wake": False,
            "whitelist": [],
            "blacklist": [],
            "max_calls_per_minute": 30,
            "webui_password": "keywords@pro",
            "webui_base_url": "http://127.0.0.1:5678",
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def check_whitelist_blacklist(self, event) -> bool:
        if event.is_private_chat():
            session_identifier = f"#{event.get_sender_id()}"
        else:
            group_id = event.get_group_id()
            if not group_id:
                return True
            session_identifier = f"@{group_id}"

        whitelist = self.get("whitelist", [])
        if whitelist and session_identifier not in whitelist:
            return False
        blacklist = self.get("blacklist", [])
        if session_identifier in blacklist:
            return False
        return True

    def check_rate_limit(self) -> bool:
        now = time.time()
        while self.call_timestamps and now - self.call_timestamps[0] > 60:
            self.call_timestamps.popleft()
        if len(self.call_timestamps) >= self.get("max_calls_per_minute", 30):
            return False
        self.call_timestamps.append(now)
        return True

    def get_webui_base_url(self) -> str:
        return self.get("webui_base_url", "http://127.0.0.1:5678").rstrip("/")
