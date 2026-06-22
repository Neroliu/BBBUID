from gsuid_core.utils.api.mys.api import GS_BASE, RECORD_BASE

# BH3 Record API Base
BH3_API = f"{RECORD_BASE}/game_record/app/honkai3rd/api"

# Data Query Endpoints (relative paths, used with base_url)
BH3_INDEX_API = "/index"
BH3_NOTE_API = "/note"
BH3_CHARACTERS_API = "/characters"
BH3_NEW_ABYSS_API = "/newAbyssReport"
BH3_OLD_ABYSS_API = "/latestOldAbyssReport"
BH3_BATTLE_FIELD_API = "/battleFieldReport"
BH3_GODWAR_API = "/godWar"

# Account API for server lookup
BH3_BIND_API = f"{GS_BASE}/binding/api/getUserGameRolesByCookie"

# BH3 Gacha Record API (self-help query service)
BH3_GACHA_MENUS_API = "https://public-operation-common.mihoyo.com/common/bh3_self_help_query/UserMenuQuery/GetMenus"
BH3_GACHA_LOG_API   = "https://public-operation-common.mihoyo.com/common/bh3_self_help_query/UserGachaQuery/GetUserGacha"

# BH3 Hand Account API (手账)
BH3_HAND_BOOK_COUNT_API = "https://api-takumi.mihoyo.com/event/handbook/current_month_count"
BH3_HAND_BOOK_LAST_MONTH_COUNT_API = "https://api-takumi.mihoyo.com/event/handbook/last_month_count"
BH3_WEEKLY_FINANCE_API  = "https://api.mihoyo.com/bh3-weekly_finance/api/index"
BH3_WEEKLY_FINANCE_LAST_MONTH_API = "https://api.mihoyo.com/bh3-weekly_finance/api/getLastMonthInfo"
