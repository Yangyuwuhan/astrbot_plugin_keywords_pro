# 关键词 pro

关键词回复插件增强版，支持固定模式和随机模式，可设置别名、白名单和黑名单。

## 功能特点

- **自动识别固定/随机回复**：当配置多个回复时，机器人会随机选择一条发送；当只配置一个回复时，机器人会固定发送该内容
- **支持多种回复形式**：文字、图片、文字+图片、视频
- **别名功能**：每个关键词可以设置多个别名，达到相同效果
- **白名单和黑名单**：可以设置允许或禁止使用插件的群聊或私聊
- **频率限制**：可设置1分钟内最多被调用的次数，防止过度调用

## 安装方法

1. 将插件目录`astrbot_plugin_keywords_pro`复制到`AstrBot/data/plugins/`目录下
2. 重启AstrBot

## 配置项

   - `need_wake`：是否需要唤醒机器人
   - `whitelist`：白名单，格式为`@群号`或`#QQ号`。白名单存在时，只有白名单内且在黑名单外的会话可使用。
   - `blacklist`：黑名单，格式为`@群号`或`#QQ号`。白名单为空时，只有黑名单里的会话不可使用。
   - `max_calls_per_minute`：1分钟内最多调用次数

## 关键词配置

1. 插件会在`AstrBot/data/keywords_data/`目录下创建`keywords.json`文件
2. 编辑该文件添加或修改关键词配置
3. 配置格式如下：

```json
{
  "文字回复": {
    "aliases": ["文本", "text"],
    "responses": [
      {
        "type": "text",
        "content": "这是一条文字回复"
      }
    ]
  },
  "图片回复": {
    "aliases": ["图片", "image"],
    "responses": [
      {
        "type": "image",
        "content": "image.jpg" // 图片文件放在keywords_data目录下
      }
    ]
  },
  "视频回复": {
    "aliases": ["视频", "video"],
    "responses": [
      {
        "type": "video",
        "content": "video.mp4" // 视频文件放在keywords_data目录下
      }
    ]
  },
  "文字图片回复": {
    "aliases": ["图文", "text_image"],
    "responses": [
      {
        "type": "text_image",
        "text": "这是文字部分",
        "image": "image.jpg" // 图片文件放在keywords_data目录下
      }
    ]
  },
  "随机回复": {
    "aliases": ["随机"],
    "responses": [
      {
        "type": "text",
        "content": "随机回复1"
      },
      {
        "type": "text",
        "content": "随机回复2"
      },
      {
        "type": "text",
        "content": "随机回复3"
      }
    ]
  }
}
```

**回复类型说明**：
- `text`：文字回复，使用`content`字段指定文字内容
- `image`：图片回复，使用`content`字段指定图片路径（相对路径或绝对路径）
- `video`：视频回复，使用`content`字段指定视频路径（相对路径或绝对路径）
- `text_image`：文字+图片回复，使用`text`字段指定文字内容，`image`字段指定图片路径

4. 图片和视频文件请放在`AstrBot/data/keywords_data/`目录下

## 使用方法

1. 在群聊或私聊中发送配置好的关键词或别名
2. 机器人会根据配置的模式回复相应的内容
3. 管理员可以发送`/keywords`指令查看当前已设置的关键词及其别名

