# 关键词 PRO

关键词回复 PRO，支持多种模式，并提供WebUI管理

## 功能特点

- **多种回复类型**：当配置多个回复时，机器人会随机选择一条发送；当只配置一个回复时，机器人会固定发送该内容
- **多种回复形式**：可同时回复 文字+图片+视频+文件
- **别名**：每个关键词可以设置多个别名
- **黑白名单**：支持全局黑白名单和关键词单独的黑白名单
- **频率限制**：可设置1分钟内最多被调用的次数，防止过度调用
- **WebUI管理界面**：提供图形化界面管理关键词配置，支持在线预览和编辑
- **定时任务**：支持Cron表达式设置定时发送消息
- **正则匹配**：支持正则匹配，实现更灵活的关键词触发
- **文件清理**：可清理未被引用的文件，节省存储空间
- **可选唤醒**：每个关键词可以独立设置是否需要唤醒机器人
- **灵活配置**：对每个关键词进行模块化储存，便于直接导入、导出数据

## 安装

将插件文件 `astrbot_plugin_keywords_pro`复制到 `AstrBot/data/plugins/`目录下，然后重启AstrBot

## 配置项

在插件配置文件中可以设置以下参数：

- `whitelist`：白名单，格式为 `@群号`或 `#QQ号`。白名单存在时，白名单内且在黑名单外的会话可用
- `blacklist`：黑名单，格式为 `@群号`或 `#QQ号`。白名单为空时，黑名单里的会话不可使用
- `max_calls_per_minute`：1分钟内最多调用次数（默认：30）
- `webui_password`：WebUI管理界面密码（默认：`keywords@pro`）
- `webui_base_url`：WebUI URL，用于协议端访问文件（默认：`http://127.0.0.1:5678`）

## 管理

### 方式一：WebUI（推荐）

1. 启动插件后，访问 `http://127.0.0.1:5678` 进入WebUI管理界面，使用默认密码 `keywords@pro` 登录
2. 在WebUI中可以：
   - 重命名、查看、添加、编辑、删除关键词，预览和上传文件
   - 支持上传的文件类型：图片、视频、音频、文档、压缩文件等
   - 配置唤醒要求、正则匹配、定时任务
   - ~~点击右上角进入本项目仓库，为本项目点击一个 Star~~

### 方式二：手动编辑

1. 插件会在 `AstrBot/data/plugin_data/astrbot_plugin_keywords_pro/` 目录下为每个关键词创建独立的目录，并在每个目录中创建 `keywords.json` 文件。你可以编辑这些文件来添加或修改关键词配置。
2. 配置项说明：

- `aliases`：关键词的别名数组，用户可以通过别名触发回复
- `responses`：回复数组，每个元素为一个回复配置(存在多个时会随机抽取)
- `text`：文字内容
- `image`：图片数组
- `video`：视频数组
- `file`：文件数组
- `need_wake`：是否需要唤醒（默认：true）
- `regex_match`：是否启用正则匹配模式（默认：false）
- `cron_enabled`：是否启用定时任务（默认：false）
- `cron_config`：定时任务配置，包含 `cron_expression`（Cron表达式）、`whitelist`（定时发送白名单）、`blacklist`（定时发送黑名单）
- `created_at`：关键词创建时间（自动生成）
- `updated_at`：关键词更新时间（自动生成）

3. 下面是一个配置实例:

```json
{
  "关键词": {
    "aliases": [],
    "responses": [
      {
        "text": "",
        "image": [],
        "video": [],
        "file": []
      }
    ],
    "need_wake": true,
    "regex_match": false,
    "cron_enabled": false,
    "cron_config": {
      "cron_expression": "",
      "whitelist": [],
      "blacklist": []
    }
  }
}
```

## 变量

在回复文本中，你可以使用以下变量：

| 变量              | 描述                 | 示例                |
| ----------------- | -------------------- | ------------------- |
| `{time}`        | 当前时间（24小时制） | 14:30:45            |
| `{date}`        | 当前日期             | 2024-01-01          |
| `{datetime}`    | 当前日期时间         | 2024-01-01 14:30:45 |
| `{random}`      | 1-100之间的随机数    | 42                  |
| `{day_of_week}` | 当前星期几（中文）   | 星期一              |

**示例**：

- 文本内容：`现在时间是{time}，今天是{date}，{day_of_week}`
- 实际发送：`现在时间是14:30:45，今天是2024-01-01，星期一`

## 使用

1. 在群聊或私聊中发送配置好的关键词或别名
2. 机器人会根据配置的模式回复相应的内容
3. 管理员可以发送 `/keywords`指令查看当前已设置的关键词及其别名

## 结构

### 插件文件结构

```
astrbot_plugin_keywords_pro/
├── core/                     # 核心功能模块
│   ├── templates/            # WebUI模板文件
│   │   ├── index.html        # 主页面
│   │   ├── login.html        # 登录页面
│   │   └── logo.png          # 插件logo
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── exception.py          # 异常处理
│   ├── sender.py             # 消息发送
│   ├── utils.py              # 工具函数
│   └── webui.py              # WebUI服务
├── .gitignore
├── LICENSE                   # 许可证
├── README.md                 # 文档
├── _conf_schema.json         # 配置
├── logo.png                  # 图标
├── main.py                   # 主入口
├── metadata.yaml             # 元数据
└── requirements.txt          # 依赖项
```

### 数据存储结构

```
AstrBot/data/plugin_data/astrbot_plugin_keywords_pro/
├── 关键词1/                  # 关键词目录
│   ├── keywords.json         # 该关键词的配置文件
│   ├── image1.jpg            # 该关键词的图片
│   └── video1.mp4            # 该关键词的视频
├── 关键词2/                  # 另一个关键词目录
│   ├── keywords.json         # 该关键词的配置文件
│   └── file1.pdf             # 该关键词的文件
└── default/                  # 默认目录（未指定关键词时上传的文件）
    └── default_file.jpg      # 默认目录下的文件
```

### ⚠️ 跨平台部署

如果你的 AstrBot 运行在 Windows 主机，而 Napcat（或其他协议端）运行在 WSL2 或容器中，由于文件系统隔离，无法通过本地文件路径直接发送文件。本插件通过 HTTP 服务提供对文件访问，你需要正确配置 `webui_base_url`：

1. 在插件配置中，将 `webui_base_url` 设置为 Windows 主机的局域网 IP（例如 `http://192.168.1.100:5678`），不能使用 `127.0.0.1`
2. 请确保 Windows 防火墙允许端口 5678 的入站连接
3. 你可以通过以下命令获取 Windows 主机的 IP 地址：

```bash
wsl
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
```

## ❗ 注意

- **平台支持**：作者仅测试了 aiocqhttp 平台
- **空配置处理**：当配置了关键词，但其回复内容为空时，本插件不会进行任何操作，也不会阻碍LLM的正常工作
- **定时任务**：定时任务白名单为空时不会启用，其黑白名单优先级低于全局黑白名单
- **正则匹配**：启用正则匹配时，关键词会在消息中进行包含匹配
- **声明**：本插件大部分代码都由 AI 生成，但作者保证对其功能运行进行了完整的测试和验证

## 问题反馈

如遇bug或有改进建议请提交 issue

## 许可证

AGPL-3.0 License
