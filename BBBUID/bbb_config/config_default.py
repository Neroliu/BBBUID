from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsStrConfig,
    GsIntConfig,
    GsBoolConfig,
    GsListStrConfig,
)

CONFIG_DEFAULT: Dict[str, GSC] = {
    "BBBPrefix": GsStrConfig(
        "插件命令前缀（确认无冲突再修改）",
        "用于设置BBBUID前缀的配置",
        "bbb",
    ),
    "SignTime": GsListStrConfig(
        "每晚签到时间设置",
        "每晚米游社签到时间设置（时，分）",
        ["2", "00"],
    ),
    "SchedSignin": GsBoolConfig(
        "定时签到",
        "开启后每晚将按设定时间自动签到",
        True,
    ),
    "PrivateSignReport": GsBoolConfig(
        "私聊签到推送",
        "开启后签到结果将私聊推送给对应用户",
        True,
    ),
    "UseHtmlRender": GsBoolConfig(
        "HTML 渲染（实验性）",
        "开启后使用 playwright + HTML 渲染图片，关闭则使用 PIL 渲染。需手动 `playwright install chromium`",
        False,
    ),
    "WallpaperCacheCount": GsStrConfig(
        "壁纸原图缓存张数上限",
        "便笺壁纸原图缓存的最大张数",
        "10",
    ),
    "WallpaperCacheSizeMB": GsStrConfig(
        "壁纸原图缓存大小上限(MB)",
        "便笺壁纸原图缓存的最大占用空间",
        "100",
    ),
    "CompressedWallpaperCacheCount": GsStrConfig(
        "压缩壁纸缓存张数上限",
        "裁剪压缩后的壁纸缓存最大张数",
        "50",
    ),
    "CompressedWallpaperCacheSizeMB": GsStrConfig(
        "压缩壁纸缓存大小上限(MB)",
        "裁剪压缩后的壁纸缓存最大占用空间",
        "200",
    ),
    "ElysianStrategyEnabled": GsBoolConfig(
        "乐土攻略查询",
        "开启后允许查询往世乐土攻略图",
        True,
    ),
    "ElysianStrategyCacheHours": GsIntConfig(
        "乐土攻略索引缓存时间",
        "远程索引缓存时间，单位小时",
        6,
    ),
    "ElysianStrategyProxyPrefix": GsStrConfig(
        "乐土攻略代理前缀",
        "GitHub Raw 访问代理前缀，留空表示直连",
        "",
    ),
    "ElysianStrategyShowSource": GsBoolConfig(
        "乐土攻略来源提示",
        "发送攻略图时是否附带数据来源与更新时间",
        True,
    ),
}
