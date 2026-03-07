import time
import urllib.parse
from pathlib import Path

from astrbot.api import logger


def safe_path_resolve(base_dir: str | Path, raw_path: str) -> Path | None:
    """
    安全解析路径，防止目录遍历攻击。
    返回解析后的Path对象，如果路径不安全或不存在则返回None。
    """
    raw_path = raw_path.lstrip("/")
    raw_path = urllib.parse.unquote(raw_path)
    if not raw_path:
        return None
    if (
        ".." in raw_path
        or raw_path.startswith(("/", "\\"))
        or ":" in raw_path
        or "\x00" in raw_path
    ):
        logger.warning(f"拒绝可疑路径: {raw_path!r}")
        return None
    base_dir = Path(base_dir).resolve()
    try:
        abs_path = (base_dir / raw_path).resolve()
        abs_path.relative_to(base_dir)
    except Exception:
        return None
    return abs_path if abs_path.exists() else None


def file_exists(base_dir: str | Path, filename: str) -> bool:
    if not filename:
        return False
    if ".." in filename or filename.startswith(("/", "\\")):
        return False
    file_path = Path(base_dir) / filename
    return file_path.is_file()


def normalize_media(resp: dict) -> None:
    """将单字符串的image/video/file转为列表"""
    for media in ["image", "video", "file"]:
        val = resp.get(media)
        if val is None:
            resp[media] = []
        elif isinstance(val, str):
            resp[media] = [val] if val else []
        elif not isinstance(val, list):
            resp[media] = []


def current_time_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
