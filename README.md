# 关键词 PRO

关键词回复 PRO，支持多种模式，并提供WebUI管理

## 功能特点

- **自动识别固定/随机回复**：当配置多个回复时，机器人会随机选择一条发送；当只配置一个回复时，机器人会固定发送该内容
- **支持多种回复形式**：系统自动根据配置自动判断回复类型，可同时配置 文字+图片+视频+文件
- **别名**：每个关键词可以设置多个别名，达到相同效果
- **白名单和黑名单**：可以设置允许或禁止使用插件的群聊或私聊
- **频率限制**：可设置1分钟内最多被调用的次数，防止过度调用
- **WebUI管理界面**：提供图形化界面管理关键词配置，支持在线预览和编辑
- **文件管理**：自动管理图片、视频和文件，支持多文件上传和预览
- **定时任务**：支持Cron表达式设置定时发送消息
- **正则匹配**：支持正则表达式匹配模式，实现更灵活的关键词触发
- **文件清理**：可清理未被引用的文件，节省存储空间
- **独立唤醒设置**：每个关键词可以独立设置是否需要唤醒机器人

## 安装

将插件目录 `astrbot_plugin_keywords_pro`复制到 `AstrBot/data/plugins/`目录下，重启AstrBot

## 文件结构

插件的文件结构如下：

```
astrbot_plugin_keywords_pro/
├── core/                     # 核心功能模块
│   ├── templates/            # WebUI模板文件
│   │   ├── index.html        # 主页面
│   │   └── login.html        # 登录页面
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── exception.py          # 异常处理
│   ├── sender.py             # 消息发送
│   ├── utils.py              # 工具函数
│   └── webui.py              # WebUI服务
├── .gitignore
├── LICENSE                   # 许可证文件
├── README.md                 # 说明文档
├── _conf_schema.json         # 配置模式定义
├── logo.png                  # 插件图标
├── main.py                   # 插件主入口
├── metadata.yaml             # 插件元数据
└── requirements.txt          # 依赖项
```

* **core/**：包含插件的核心功能实现，包括WebUI、配置管理、消息发送等
* **core/templates/**：WebUI的HTML模板文件
* **main.py**：插件的主入口文件，处理消息和指令
* **metadata.yaml**：插件的元数据信息
* **requirements.txt**：插件依赖的Python包

## 配置项

在插件配置文件中可以设置以下参数：

- `whitelist`：白名单，格式为 `@群号`或 `#QQ号`。白名单存在时，只有白名单内且在黑名单外的会话可使用
- `blacklist`：黑名单，格式为 `@群号`或 `#QQ号`。白名单为空时，只有黑名单里的会话不可使用
- `max_calls_per_minute`：1分钟内最多调用次数（默认：30）
- `webui_password`：WebUI管理界面密码（默认：keywords@pro）
- `webui_base_url`：WebUI基础URL，用于文件访问（默认：http://127.0.0.1:5678）

## 配置

### WebUI（推荐）

1. 启动插件后，访问 `http://127.0.0.1:5678` 进入WebUI管理界面
2. 使用默认密码 `keywords@pro` 登录（可在配置中修改）
3. 在WebUI中可以：

   - 查看、添加、编辑、删除关键词
   - 重命名关键词
   - 上传和管理文件：支持上传的文件类型：图片（.png, .jpg, .jpeg, .gif, .webp, .bmp）、视频（.mp4, .avi, .mov, .mkv）、文档（.doc, .docx, .pdf, .txt, .md, .rtf）、压缩文件（.zip, .rar, .7z, .tar, .gz）等等
   - 清理未使用的文件
   - 配置定时任务（Cron表达式）、正则匹配、唤醒要求

### 手动配置

1. 插件会在 `AstrBot/data/keywords_data/`目录下创建 `keywords.json`文件，编辑该文件添加或修改关键词配置。
2. 配置说明：

- `aliases`：关键词的别名数组，用户可以通过别名触发回复
- `responses`：回复数组，每个元素为一个回复配置(存在多个时会随机抽取)
- `text`：文字回复，使用 `text`字段指定文字内容
- `image`：图片回复，使用 `image`字段指定图片名称，也可以是图片数组，支持发送多张图片
- `video`：视频回复，使用 `video`字段指定视频名称，也可以是视频数组，支持发送多个视频（每个视频会单独发送）
- `file`：文件回复，使用 `file`字段指定文件名称，也可以是文件数组，支持发送多个文件（每个文件会单独发送）
- `need_wake`：该关键词是否需要唤醒机器人（默认：true）
- `regex_match`：是否启用正则匹配模式（默认：false）
- `cron_enabled`：是否启用定时任务（默认：false）
- `cron_config`：定时任务配置，包含cron_expression（Cron表达式）、whitelist（定时发送白名单）、blacklist（定时发送黑名单）
- `created_at`：关键词创建时间（自动生成）
- `updated_at`：关键词更新时间（自动生成）

3. 配置格式：

```json
{
  "test1": {
    "aliases": [
      "测试1.1",
      "测试1.2"
    ],
    "responses": [
      {
        "text": "文字1",
        "image": "image1.jpg",
        "video": "video1.mp4",
        "file": "document.pdf"
      },
      {
        "text": "文字2",
        "image": "image2.jpg",
        "video": "",
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
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  "test2": {
    "aliases": [
      "测试2"
    ],
    "responses": [
      {
        "text": "这是一个多文件示例1",
        "image": [
          "image1.png",
          "image2.png"
        ],
        "video": [
          "video1.mp4",
          "video2.mp4"
        ],
        "file": [
          "doc1.pdf",
          "doc2.docx"
        ]
      },
      {
        "text": "这是一个多文件示例2",
        "image": [
          "image3.png",
          "image4.png"
        ],
        "video": [
          "video3.mp4",
          "video4.mp4"
        ],
        "file": []
      }
    ],
    "need_wake": false,
    "regex_match": true,
    "cron_enabled": true,
    "cron_config": {
      "cron_expression": "0 0 * * *",
      "whitelist": ["@123456789", "#987654321"],
      "blacklist": []
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

 *说明：*

*a.在 test1 关键词中用户会收到“文字1+image1”+“video1”*
*b.在 test2 关键词中，用户会等概率地收到“这是一个多文件示例1+image1+image2”+“video1”+"video2" 和 “这是一个多文件示例2+image3+image4”+“video3”+"video4"*
*c.图片和视频文件请放在 `AstrBot/data/keywords_data/`目录下*

4. 下面是一个最小化的配置实例:

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

## 注意事项

- **消息发送规则**：

  - 文字和图片会合并在同一条消息中发送
  - 视频和文件会每个单独发送一条消息
  - 支持同时发送多个图片、视频和文件
- **平台支持**：作者仅测试了 aiocqhttp 平台
- **空配置处理**：

  - 当配置了关键词，但其回复内容为空时，本插件不会进行任何操作
  - 不会阻碍LLM的正常工作
- **定时任务**：

  - 定时任务需要设置cron_expression（Cron表达式）和whitelist（发送目标）
  - 定时任务黑白名单优先级低于全局黑白名单
- **正则匹配**：

  - 启用正则匹配后，关键词会在消息中进行包含匹配；非正则模式下，关键词需要精确匹配

### 使用

1. 在群聊或私聊中发送配置好的关键词或别名
2. 机器人会根据配置的模式回复相应的内容
3. 管理员可以发送 `/keywords`指令查看当前已设置的关键词及其别名

### ⚠️ 跨平台部署注意事项

    如果您的 AstrBot 运行在 Windows 主机，而 Napcat（或其他协议端）运行在 WSL2 或容器中，由于文件系统隔离，无法通过本地文件路径直接发送视频。本插件通过 HTTP 服务提供视频文件访问，您需要正确配置 webui_base_url：
    1. 在插件配置中，将 webui_base_url 设置为 Windows 主机的局域网 IP（例如 http://192.168.1.100:5678），不能使用 127.0.0.1。
    2. 请确保 Windows 防火墙允许端口 5678 的入站连接。
    3. 如果您在 WSL2 中运行协议端，可以通过以下命令获取 Windows 主机的 IP 地址：``bash        wsl        cat /etc/resolv.conf | grep nameserver | awk '{print $2}'        ``
       执行上述命令后，会返回 Windows 主机的 IP 地址，您可以将其用于 webui_base_url 的配置。

### 问题反馈

1. 提交 issue
2. 添加 QQ群: 1083269367 进行反馈，注意入群后及时完成人机验证

## 许可证

AGPL-3.0 License
