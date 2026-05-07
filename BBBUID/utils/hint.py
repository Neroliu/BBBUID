from gsuid_core.sv import get_plugin_available_prefix

prefix = get_plugin_available_prefix("BBBUID")
BIND_UID_HINT = f"你还没有绑定UID哦, 请使用 {prefix}绑定uid 完成绑定！"
