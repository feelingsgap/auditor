"""처리 대상 연도 탐지.

연도 목록을 코드에 하드코딩하면 새 회차를 추가할 때마다 여러 스크립트를 함께
고쳐야 한다. 대신 `{year}/{year}_data.json` 이 존재하는 연도를 대상으로 본다.
"""
import os
import re

FIRST_YEAR = 2021


def available_years(base_dir: str = ".") -> list:
    """data.json 이 준비된 연도를 오름차순으로 반환한다."""
    years = []
    for name in os.listdir(base_dir):
        if not re.fullmatch(r"\d{4}", name):
            continue
        if os.path.exists(os.path.join(base_dir, name, f"{name}_data.json")):
            year = int(name)
            if year >= FIRST_YEAR:
                years.append(year)
    return sorted(years)
