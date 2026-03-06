class KeywordsProError(Exception):
    """插件基础异常"""

    pass


class KeywordNotFoundError(KeywordsProError):
    """关键词不存在"""

    pass


class ConfigError(KeywordsProError):
    """配置错误"""

    pass


class FileAccessError(KeywordsProError):
    """文件访问错误"""

    pass
