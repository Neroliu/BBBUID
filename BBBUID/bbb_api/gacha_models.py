"""崩坏3抽卡记录数据模型（基于实测 API 响应）。"""
from __future__ import annotations

from typing import TypedDict


class GachaMenuItem(TypedDict):
    label: str
    type: int


class GachaRecordItem(TypedDict):
    label: str
    value: str


class GachaRecord(TypedDict):
    item: list[GachaRecordItem]


class GachaLogData(TypedDict):
    userLastUpdateTime: str
    lastUpdateTime: str
    currentPage: int
    pageSize: int
    list: list[GachaRecord]
