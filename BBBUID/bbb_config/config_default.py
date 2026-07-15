from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsStrConfig,
    GsIntConfig,
    GsBoolConfig,
    GsListStrConfig,
    GsListConfig,
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
        "裁剪压缩后的壁纸缓存的最大占用空间",
        "200",
    ),
    "BBBAllowAtQuery": GsBoolConfig(
        "@他人查询",
        "开启后可通过@他人查询对方崩坏3数据（需对方已绑定UID）",
        False,
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
    # ── 公告 (旧, 保留用于迁移) ──
    "BBBAnnIds": GsListStrConfig(
        "崩坏3已知公告ID (旧)",
        "旧版扁平ID列表, 首次运行时自动迁移到分类存储",
        [],
    ),
    # ── 公告 (新, 按分类存储) ──
    "BBBAnnIdsAnnounce": GsListConfig(
        "崩坏3已知公告ID-公告",
        "公告类(type=1)已知帖子ID列表",
        [],
    ),
    "BBBAnnIdsActivity": GsListConfig(
        "崩坏3已知公告ID-活动",
        "活动类(type=2)已知帖子ID列表",
        [],
    ),
    "BBBAnnIdsInfo": GsListConfig(
        "崩坏3已知公告ID-资讯",
        "资讯类(type=3)已知帖子ID列表",
        [],
    ),
    "BBBAnnOpen": GsBoolConfig(
        "崩坏3公告推送",
        "开启后将自动推送崩坏3最新公告到订阅群",
        True,
    ),
    "BBBAnnCheckMinutes": GsIntConfig(
        "崩坏3公告检查间隔",
        "自动检查公告的间隔（分钟，最大60）",
        10,
    ),
}
