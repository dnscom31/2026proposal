# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

OFFICIAL_2026: Dict[str, Any] = {
    "schema_version": 1,
    "organization": "뉴고려병원",
    "title": "2026 건강검진 안내문",
    "subtitle": "건강검진 프로그램",
    "target": "임직원 및 가족",
    "period": "",
    "application_period": "",
    "phone": "1833-9988",
    "qr_url": "",
    "event_title": "EVENT",
    "event_lines": [
        "종합검진 진행 시 A그룹 1가지 추가 혜택",
    ],
    "common_items": (
        "간기능 | 간염 | 순환기계 | 당뇨 | 췌장기능 | 철결핍성 | 빈혈 | 혈액질환 | 전해질 | "
        "신장기능 | 골격계질환 | 감염성 | 갑상선기능 | 부갑상선기능 | 종양표지자 | 소변 등 "
        "800여종 혈액(소변) 검사 | 심전도 | 신장 | 체중 | 혈압 | 시력 | 청력 | 체성분 | "
        "건강유형분석 | 폐기능 | 안저 | 안압 | 혈액점도검사 | 유전자20종 | 흉부X-ray | "
        "복부초음파 | 위수면내시경 | (여)자궁경부세포진 | (여)유방촬영 - #30세이상 권장#"
    ),
    "groups": {
        "A": [
            "[01] 갑상선초음파",
            "[02] 경동맥초음파",
            "[03] (여)경질초음파",
            "[04] 뇌CT",
            "[05] 폐CT",
            "[06] 요추CT",
            "[07] 경추CT",
            "[08] 심장MDCT",
            "[09] 복부비만CT",
            "[10] 골다공증QCT+비타민D",
            "[11] 혈관협착도ABI",
            "[12] (여)액상 자궁경부세포진",
            "[13] (여)HPV바이러스",
            "[14] (여)(혈액)마스토체크:유방암",
            "[15] (혈액)NK뷰키트",
            "[16] (여)(혈액)여성호르몬",
            "[17] (남)(혈액)남성호르몬",
            "[18] 유전자 뉴베이직",
            "[19] 유전자 면역형",
            "[20] 유전자 라이프형",
        ],
        "B": [
            "[가] 대장수면내시경",
            "[나] 심장초음파",
            "[다] (여)유방초음파",
            "[라] [분변]대장암_얼리텍",
            "[마] 방광암_소변유전자(PENK)",
            "[바] 부정맥검사S-PATCH",
            "[사] [혈액]알레르기검사",
            "[아] [혈액]알츠온:치매위험도검사",
            "[야] [혈액]간섬유화검사",
            "[자] 폐렴예방접종:15가",
        ],
        "C": [
            "[A] 뇌MRI+MRA",
            "[B] 경추MRI",
            "[C] 요추MRI",
            "[D] 췌장MRI",
            "[E] [혈액]스마트암검사(남6/여7종)",
            "[F] [혈액]선천적 유전자검사(남34/여35종)",
            "[G] [혈액]에피클락(생체나이, 노화측정)",
        ],
    },
    "packages": [
        {
            "name": "건강형",
            "detail": "공통항목 + A그룹 2가지",
            "male_price": "35만",
            "female_price": "42만",
        },
        {
            "name": "소망형",
            "detail": "공통항목 + A그룹 4가지",
            "male_price": "47만",
            "female_price": "54만",
        },
        {
            "name": "믿음형",
            "detail": "공통항목 + A그룹 4가지 + 대장수면내시경",
            "male_price": "59만",
            "female_price": "66만",
        },
        {
            "name": "행복형",
            "detail": "공통항목 + A그룹 4가지 + C그룹 1가지",
            "male_price": "71만",
            "female_price": "78만",
        },
        {
            "name": "사랑형",
            "detail": "공통항목 + A그룹 5가지 + C그룹 1가지 + 알츠온 + 대장수면내시경 + 심장초음파 + 선천적유전자",
            "male_price": "142만",
            "female_price": "147만",
        },
    ],
    "notes": [
        "공단검진 대상자는 종합검진 진행 시 공단청구 금액을 차감해드립니다.",
        "연속검진 중복 할인 적용 불가합니다.",
    ],
    "theme": "여름",
}


def official_2026_copy() -> Dict[str, Any]:
    return deepcopy(OFFICIAL_2026)


def normalize_project_data(data: Dict[str, Any] | None) -> Dict[str, Any]:
    base = official_2026_copy()
    if not isinstance(data, dict):
        return base

    for key in [
        "organization", "title", "subtitle", "target", "period", "application_period",
        "phone", "qr_url", "event_title", "common_items", "theme"
    ]:
        if key in data and data[key] is not None:
            base[key] = str(data[key])

    if isinstance(data.get("event_lines"), list):
        base["event_lines"] = [str(x) for x in data["event_lines"] if str(x).strip()]

    if isinstance(data.get("notes"), list):
        base["notes"] = [str(x) for x in data["notes"] if str(x).strip()]

    if isinstance(data.get("groups"), dict):
        for group_name in ("A", "B", "C"):
            group = data["groups"].get(group_name)
            if isinstance(group, list):
                base["groups"][group_name] = [str(x) for x in group if str(x).strip()]

    if isinstance(data.get("packages"), list):
        packages: List[Dict[str, str]] = []
        for row in data["packages"]:
            if not isinstance(row, dict):
                continue
            packages.append({
                "name": str(row.get("name", "")).strip(),
                "detail": str(row.get("detail", "")).strip(),
                "male_price": str(row.get("male_price", "")).strip(),
                "female_price": str(row.get("female_price", "")).strip(),
            })
        if packages:
            base["packages"] = packages

    if "schema_version" in data:
        try:
            base["schema_version"] = int(data["schema_version"])
        except Exception:
            pass

    return base
