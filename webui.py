import asyncio
import hmac
import mimetypes
import os
import time
import uuid
from pathlib import Path
from urllib.parse import unquote

from aiohttp import web

from astrbot.api import logger


class WebServer:
    CLIENT_MAX_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
    }

    def __init__(self, plugin, host="0.0.0.0", port=5678):
        self.plugin = plugin
        self.host = host
        self.port = port
        self.app = web.Application(
            client_max_size=self.CLIENT_MAX_SIZE,
            middlewares=[self._error_middleware, self._auth_middleware],
        )
        self.runner = None
        self.site = None
        self._started = False
        # 静态文件目录：插件目录下的 webUI
        self.static_dir = Path(__file__).parent / "webUI"
        self._ensure_static_dir()
        self._cookie_name = "keywords_webui_session"
        self._sessions = {}
        self._last_cleanup = 0.0
        self._session_cleanup_interval = 300  # 5分钟
        self._setup_routes()

    def _ensure_static_dir(self):
        """确保静态文件目录存在，如果不存在则创建"""
        if not self.static_dir.exists():
            self.static_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建静态文件目录: {self.static_dir}")
        index_path = self.static_dir / "index.html"
        login_path = self.static_dir / "login.html"
        if not index_path.exists():
            logger.warning(f"index.html 不存在于 {index_path}，Web界面可能无法正常工作")
        if not login_path.exists():
            logger.warning(f"login.html 不存在于 {login_path}，Web界面可能无法正常工作")

    # ---------- 中间件 ----------
    async def _error_middleware(self, app, handler):
        async def middleware(request):
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                logger.error(f"WebUI 未处理错误: {e}", exc_info=True)
                if request.path.startswith("/api/"):
                    return self._err("Internal Server Error")
                return web.Response(text="500 Internal Server Error", status=500)

        return middleware

    async def _auth_middleware(self, app, handler):
        async def middleware(request):
            if request.method == "OPTIONS":
                return await handler(request)

            password = self.plugin.config.get("webui_password", "")
            if not password:
                # 无密码则不认证
                return await handler(request)

            path = request.path
            # 公开路径：登录页、认证API、静态资源、文件下载
            if (
                path in ("/", "/login.html", "/index.html")
                or path.startswith("/web/")
                or path.startswith("/auth/")
                or path.startswith("/files/")
            ):
                return await handler(request)

            # 其他API需要认证
            sid = request.cookies.get(self._cookie_name, "")
            now = time.time()
            # 清理过期会话
            if now - self._last_cleanup > self._session_cleanup_interval:
                expired = [k for k, v in self._sessions.items() if v < now]
                for k in expired:
                    self._sessions.pop(k, None)
                self._last_cleanup = now

            exp = self._sessions.get(sid)
            if not exp or exp < now:
                if sid:
                    self._sessions.pop(sid, None)
                if path.startswith("/api/"):
                    return self._err("Unauthorized", 401)
                raise web.HTTPUnauthorized(text="Unauthorized")
            return await handler(request)

        return middleware

    # ---------- 辅助方法 ----------
    def _ok(self, data=None, **kwargs):
        body = {"success": True}
        if data:
            body.update(data)
        if kwargs:
            body.update(kwargs)
        return web.json_response(body)

    def _err(self, msg, status=500):
        return web.json_response({"success": False, "error": msg}, status=status)

    def _resolve_safe_path(self, raw: str, base_dir: Path) -> Path | None:
        raw = raw.lstrip("/")
        raw = unquote(raw)  # 关键：URL 解码
        if not raw:
            return None
        """安全路径解析，防止目录遍历"""
        if ".." in raw or raw.startswith(("/", "\\")) or ":" in raw or "\x00" in raw:
            logger.warning(f"拒绝可疑路径: {raw!r}")
            return None
        base_dir = base_dir.resolve()
        try:
            abs_path = (base_dir / raw).resolve()
            abs_path.relative_to(base_dir)  # 确保在基目录内
        except Exception:
            return None
        return abs_path if abs_path.exists() else None

    # ---------- 路由设置 ----------
    def _setup_routes(self):
        # API 路由
        self.app.router.add_get("/api/keywords", self.handle_get_keywords)
        self.app.router.add_post("/api/keywords", self.handle_add_keyword)
        self.app.router.add_put("/api/keywords/{key}", self.handle_update_keyword)
        self.app.router.add_delete("/api/keywords/{key}", self.handle_delete_keyword)
        self.app.router.add_post("/api/upload", self.handle_upload_file)
        self.app.router.add_get("/api/files", self.handle_list_files)
        self.app.router.add_post(
            "/api/cleanup_unused_files", self.handle_cleanup_unused_files
        )  # 新增
        self.app.router.add_get("/auth/info", self.handle_auth_info)
        self.app.router.add_post("/auth/login", self.handle_auth_login)
        self.app.router.add_post("/auth/logout", self.handle_auth_logout)

        # 静态文件服务
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/index.html", self.handle_index)
        self.app.router.add_get("/login.html", self.handle_login)
        self.app.router.add_get("/web/{path:.*}", self.handle_web_static)
        # 文件下载（data_dir 中的文件）
        self.app.router.add_get("/files/{filename}", self.handle_file_download)

    # ---------- API 处理函数 ----------
    async def handle_get_keywords(self, request):
        async with self.plugin._keywords_lock:
            data = self.plugin.keywords_data
        return self._ok({"keywords": data})

    async def handle_add_keyword(self, request):
        try:
            payload = await request.json()
            key = payload.get("key", "").strip()
            if not key:
                return self._err("关键词不能为空", 400)
            data = payload.get("data", {})
            if not isinstance(data, dict):
                return self._err("数据格式错误", 400)

            async with self.plugin._keywords_lock:
                if key in self.plugin.keywords_data:
                    return self._err("关键词已存在", 409)
                # 设置时间字段
                now = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
                data["created_at"] = now
                data["updated_at"] = now
                self.plugin.keywords_data[key] = data
                self.plugin._save_keywords(self.plugin.keywords_data)
            return self._ok({"key": key})
        except Exception as e:
            logger.error(f"新增关键词失败: {e}")
            return self._err(str(e))

    async def handle_update_keyword(self, request):
        key = request.match_info.get("key", "").strip()
        if not key:
            return self._err("关键词无效", 400)
        try:
            payload = await request.json()
            new_data = payload.get("data", {})
            if not isinstance(new_data, dict):
                return self._err("数据格式错误", 400)

            async with self.plugin._keywords_lock:
                if key not in self.plugin.keywords_data:
                    return self._err("关键词不存在", 404)
                # 保留原有创建时间
                new_data["created_at"] = self.plugin.keywords_data[key].get(
                    "created_at"
                )
                # 更新修改时间
                new_data["updated_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime()
                )
                self.plugin.keywords_data[key] = new_data
                self.plugin._save_keywords(self.plugin.keywords_data)
            return self._ok()
        except Exception as e:
            logger.error(f"更新关键词失败: {e}")
            return self._err(str(e))

    async def handle_delete_keyword(self, request):
        key = request.match_info.get("key", "").strip()
        if not key:
            return self._err("关键词无效", 400)
        async with self.plugin._keywords_lock:
            if key not in self.plugin.keywords_data:
                return self._err("关键词不存在", 404)
            del self.plugin.keywords_data[key]
            self.plugin._save_keywords(self.plugin.keywords_data)
        return self._ok()

    async def handle_upload_file(self, request):
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != "file":
            return self._err("没有找到文件字段", 400)

        filename = field.filename
        if not filename:
            return self._err("文件名为空", 400)

        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return self._err(
                f"不支持的文件类型，允许: {', '.join(self.ALLOWED_EXTENSIONS)}", 400
            )

        safe_name = os.path.basename(filename)
        save_path = Path(self.plugin.data_dir) / safe_name
        # 确保在 data_dir 内
        try:
            save_path.resolve().relative_to(Path(self.plugin.data_dir).resolve())
        except ValueError:
            return self._err("非法文件名", 400)

        size = 0
        try:
            with open(save_path, "wb") as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return self._err("文件保存失败", 500)

        logger.info(f"文件上传成功: {save_path}, 大小: {size}")
        return self._ok({"filename": safe_name})

    async def handle_list_files(self, request):
        data_dir = Path(self.plugin.data_dir)
        files = []
        try:
            for entry in data_dir.iterdir():
                if entry.is_file():
                    files.append(entry.name)
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return self._err("无法读取文件列表")
        return self._ok({"files": files})

    async def handle_file_download(self, request):
        filename = request.match_info.get("filename", "")
        logger.debug(f"文件下载请求: {filename}")
        file_path = self._resolve_safe_path(filename, Path(self.plugin.data_dir))
        if not file_path or not file_path.is_file():
            logger.warning(f"文件不存在或路径非法: {filename}")
            raise web.HTTPNotFound()
        logger.debug(f"提供文件: {file_path}")
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
        return web.FileResponse(file_path, headers={"Content-Type": content_type})

    # ---------- 新增：清理未使用文件 ----------
    async def handle_cleanup_unused_files(self, request):
        """删除未被任何关键词回复引用的文件"""
        try:
            plugin = self.plugin
            async with plugin._keywords_lock:
                # 收集所有被引用的文件名
                used_files = set()
                for keyword, data in plugin.keywords_data.items():
                    responses = data.get("responses", [])
                    for resp in responses:
                        # 图片
                        images = resp.get("image", [])
                        if isinstance(images, list):
                            used_files.update(images)
                        elif isinstance(images, str) and images:
                            used_files.add(images)
                        # 视频
                        videos = resp.get("video", [])
                        if isinstance(videos, list):
                            used_files.update(videos)
                        elif isinstance(videos, str) and videos:
                            used_files.add(videos)

                # 获取 data_dir 中所有文件（排除 keywords.json）
                all_files = set()
                exclude_files = {"keywords.json"}
                for entry in os.listdir(plugin.data_dir):
                    if entry in exclude_files:
                        continue
                    file_path = os.path.join(plugin.data_dir, entry)
                    if os.path.isfile(file_path):
                        all_files.add(entry)

                # 计算未使用文件
                unused_files = all_files - used_files
                deleted = []
                for filename in unused_files:
                    file_path = os.path.join(plugin.data_dir, filename)
                    try:
                        os.remove(file_path)
                        deleted.append(filename)
                    except Exception as e:
                        logger.error(f"删除文件 {filename} 失败: {e}")

                logger.info(f"已删除未使用文件: {deleted}")
                return self._ok({"deleted": deleted, "count": len(deleted)})
        except Exception as e:
            logger.error(f"清理未使用文件失败: {e}", exc_info=True)
            return self._err(str(e))

    # ---------- 认证相关 ----------
    async def handle_auth_info(self, request):
        password = self.plugin.config.get("webui_password", "")
        return self._ok({"requires_auth": bool(password)})

    async def handle_auth_login(self, request):
        password = self.plugin.config.get("webui_password", "")
        if not password:
            return self._ok(requires_auth=False)

        payload = await request.json()
        provided = (payload.get("password") or "").strip()
        if not hmac.compare_digest(provided, password):
            return self._err("密码错误", 401)

        sid = uuid.uuid4().hex
        timeout = 3600  # 1小时
        exp = time.time() + timeout
        self._sessions[sid] = exp

        resp = self._ok(expires_at=int(exp))
        resp.set_cookie(
            self._cookie_name,
            sid,
            max_age=timeout,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        return resp

    async def handle_auth_logout(self, request):
        sid = request.cookies.get(self._cookie_name, "")
        if sid:
            self._sessions.pop(sid, None)
        resp = self._ok()
        resp.del_cookie(self._cookie_name, path="/")
        return resp

    # ---------- 静态页面 ----------
    async def handle_index(self, request):
        index_file = self.static_dir / "index.html"
        if not index_file.exists():
            return web.Response(
                text="<h1>index.html 未找到</h1>", content_type="text/html", status=404
            )
        try:
            content = await asyncio.to_thread(index_file.read_text, encoding="utf-8")
            return web.Response(text=content, content_type="text/html")
        except Exception as e:
            logger.error(f"读取 index.html 失败: {e}")
            return self._err("Internal Error", 500)

    async def handle_login(self, request):
        login_file = self.static_dir / "login.html"
        if not login_file.exists():
            return web.Response(
                text="<h1>login.html 未找到</h1>", content_type="text/html", status=404
            )
        try:
            content = await asyncio.to_thread(login_file.read_text, encoding="utf-8")
            return web.Response(text=content, content_type="text/html")
        except Exception as e:
            logger.error(f"读取 login.html 失败: {e}")
            return self._err("Internal Error", 500)

    async def handle_web_static(self, request):
        path = request.match_info.get("path", "")
        abs_path = self._resolve_safe_path(path, self.static_dir)
        if not abs_path or not abs_path.is_file():
            raise web.HTTPNotFound()
        content_type, _ = mimetypes.guess_type(str(abs_path))
        if not content_type:
            content_type = "application/octet-stream"
        try:
            if content_type.startswith("text/") or content_type in (
                "application/javascript",
                "application/json",
            ):
                text = await asyncio.to_thread(abs_path.read_text, encoding="utf-8")
                return web.Response(text=text, content_type=content_type)
            else:
                data = await asyncio.to_thread(abs_path.read_bytes)
                return web.Response(body=data, content_type=content_type)
        except Exception as e:
            logger.error(f"静态文件服务失败: {abs_path} - {e}")
            raise web.HTTPNotFound()

    # ---------- 服务器生命周期 ----------
    async def start(self):
        try:
            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            self._started = True
            logger.info(f"关键词管理 WebUI 已启动: http://{self.host}:{self.port}")
            if self.host == "0.0.0.0":
                logger.info(f"  → 本地访问: http://127.0.0.1:{self.port}")
            return True
        except OSError as e:
            if "Address already in use" in str(e):
                logger.error(f"端口 {self.port} 已被占用，请更换端口")
            else:
                logger.error(f"启动 WebUI 失败: {e}")
            return False
        except Exception as e:
            logger.error(f"启动 WebUI 异常: {e}", exc_info=True)
            return False

    async def stop(self):
        if not self._started:
            return
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self._started = False
        logger.info("关键词管理 WebUI 已停止")
