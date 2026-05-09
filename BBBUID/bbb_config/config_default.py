from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsStrConfig,
    GsBoolConfig,
    GsListStrConfig,
)

CONFIG_DEFAULT: Dict[str, GSC] = {
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
}
