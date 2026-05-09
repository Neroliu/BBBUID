from typing import List, Optional, TypedDict


# --- Index (Player Overview) ---


class BH3RoleInfo(TypedDict, total=False):
    AvatarUrl: str
    nickname: str
    region: str
    level: int


class BH3NewAbyssStats(TypedDict, total=False):
    level: int
    cup_number: int


class BH3Stats(TypedDict, total=False):
    active_day_number: int
    suit_number: int
    achievement_number: int
    stigmata_number: int
    armor_number: int
    sss_armor_number: int
    weapon_number: int
    five_star_weapon_number: int
    five_star_stigmata_number: int
    elf_number: int
    battle_field_ranking_percentage: str
    battle_field_area: int
    battle_field_score: int
    battle_field_rank: int
    new_abyss: BH3NewAbyssStats
    abyss_score: int
    abyss_floor: int
    god_war_max_punish_level: int
    god_war_extra_item_number: int
    god_war_max_challenge_score: int
    god_war_max_challenge_level: int
    god_war_max_level_avatar_number: int
    god_war_max_support_point: int
    explore_score: int
    explore_score_sum: int


class BH3Preference(TypedDict, total=False):
    abyss: int
    main_line: int
    battle_field: int
    open_world: int
    community: int
    comprehensive_score: int
    comprehensive_rating: str
    god_war: int
    is_god_war_unlock: bool


class BH3IndexData(TypedDict, total=False):
    role: BH3RoleInfo
    stats: BH3Stats
    preference: BH3Preference
    head_background: str


# --- Note (Real-time Notes) ---


class BH3GreedyEndless(TypedDict, total=False):
    schedule_end: str
    level_icon: str
    cur_reward: int
    max_reward: int
    is_open: bool


class BH3UltraEndless(TypedDict, total=False):
    schedule_end: str
    group_level: int
    challenge_score: int
    is_open: bool
    level_icon: str


class BH3BattleFieldNote(TypedDict, total=False):
    schedule_end: str
    cur_reward: int
    max_reward: int
    cur_sss_reward: int
    max_sss_reward: int
    is_open: bool


class BH3GodWarNote(TypedDict, total=False):
    schedule_end: str
    cur_reward: int
    max_reward: int
    is_open: bool


class BH3NoteData(TypedDict, total=False):
    current_stamina: int
    max_stamina: int
    stamina_recover_time: int
    current_train_score: int
    max_train_score: int
    greedy_endless: BH3GreedyEndless
    ultra_endless: BH3UltraEndless
    battle_field: BH3BattleFieldNote
    god_war: BH3GodWarNote


# --- Characters (Valkyrie List) ---


class BH3AvatarIcon(TypedDict, total=False):
    id: str
    name: str
    star: int
    icon_path: str
    background_path: str
    image_path: str
    level: int
    attribute_id: int
    wiki_url: str


class BH3WeaponInfo(TypedDict, total=False):
    id: int
    name: str
    max_rarity: int
    rarity: int
    icon: str


class BH3StigmatInfo(TypedDict, total=False):
    id: int
    name: str
    rarity: int
    icon: str
    slot: int


class BH3CharacterDetail(TypedDict, total=False):
    avatar: BH3AvatarIcon
    weapon: BH3WeaponInfo
    stigmatas: List[BH3StigmatInfo]
    elf: dict


class BH3CharacterItem(TypedDict, total=False):
    character: BH3CharacterDetail


class BH3CharactersData(TypedDict, total=False):
    characters: List[BH3CharacterItem]


# --- Abyss (New/Superstring) ---


class BH3AbyssBoss(TypedDict, total=False):
    id: str
    name: str
    avatar: str


class BH3AbyssLineupAvatar(TypedDict, total=False):
    id: str
    name: str
    star: int
    icon_path: str


class BH3AbyssReport(TypedDict, total=False):
    score: int
    updated_time_second: str
    boss: BH3AbyssBoss
    lineup: List[BH3AbyssLineupAvatar]


class BH3NewAbyssData(TypedDict, total=False):
    reports: List[BH3AbyssReport]


class BH3OldAbyssData(TypedDict, total=False):
    reports: List[BH3AbyssReport]


# --- Battle Field (Memorial Arena) ---


class BH3ElfInfo(TypedDict, total=False):
    id: str
    name: str
    avatar: str
    rarity: int
    star: int


class BH3BattleInfo(TypedDict, total=False):
    elf: BH3ElfInfo
    lineup: List[BH3AbyssLineupAvatar]


class BH3BattleFieldReport(TypedDict, total=False):
    score: int
    rank: int
    ranking_percentage: str
    area: int
    battle_infos: List[BH3BattleInfo]


class BH3BattleFieldData(TypedDict, total=False):
    reports: List[BH3BattleFieldReport]


# --- God War (Elysian Realm) ---


class BH3GodWarBuff(TypedDict, total=False):
    icon: str
    number: int
    id: int


class BH3GodWarRecord(TypedDict, total=False):
    settle_time_second: str
    score: int
    punish_level: int
    level: int
    buffs: List[BH3GodWarBuff]
    conditions: list
    main_avatar: BH3AbyssLineupAvatar
    support_avatars: List[BH3AbyssLineupAvatar]


class BH3GodWarData(TypedDict, total=False):
    records: List[BH3GodWarRecord]
