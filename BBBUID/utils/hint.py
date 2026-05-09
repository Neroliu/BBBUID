from gsuid_core.sv import get_plugin_available_prefix

prefix = get_plugin_available_prefix("BBBUID")
BIND_UID_HINT = f"你还没有绑定UID哦, 请使用 {prefix}绑定uid 完成绑定！"
CK_HINT = "你还没有绑定Cookie哦！请先绑定Cookie后再查询~"

BBB_ERROR_CODE = {
    -51: CK_HINT,
    10001: "Cookie已失效，请重新获取！",
    10101: "当前查询CK已超过每日30次上限！",
    10102: "当前查询id已设置隐私，无法查询！",
    -501002: "用户数据未公开，请绑定/使用自己的CK！",
}


def bbb_error_reply(retcode: int) -> str:
    if retcode in BBB_ERROR_CODE:
        return f"[崩坏3] {BBB_ERROR_CODE[retcode]}"
    return f"[崩坏3] 查询失败，错误码: {retcode}"
