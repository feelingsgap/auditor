"""
이의신청 문항 표시 주입 스크립트
NIA 공지사항 게시판(bbsSn=4)의 이의신청 현황을 기반으로
각 연도별 data.json에 disputed 필드를 추가합니다.
A형 문항 번호 기준.
"""

import json
import os

# 연도별 이의신청 문항 (A형 기준)
DISPUTED_QUESTIONS = {
    2021: [26, 28, 32, 38, 40, 42, 47, 49, 54, 60, 71, 82, 87, 88, 93, 94, 100, 113],
    2022: [2, 6, 47, 50, 56, 60, 65, 77, 95, 102],
    2023: [9, 37, 45, 57, 74, 83, 114, 118],
    2024: [7, 30, 34, 35, 39, 40, 65, 83, 88, 98],
    2025: [3, 4, 19, 22, 26, 36, 47, 52, 54, 60, 64, 82, 102, 117],
}


def inject_disputed(base_dir: str = "."):
    for year, disputed_nums in DISPUTED_QUESTIONS.items():
        data_path = os.path.join(base_dir, str(year), f"{year}_data.json")
        if not os.path.exists(data_path):
            print(f"  경고: {data_path} 없음, 건너뜀")
            continue

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        disputed_set = set(disputed_nums)
        count = 0
        for page in data.get("pages", []):
            for q in page.get("questions", []):
                q_num = q.get("question_num")
                q["disputed"] = q_num in disputed_set
                if q["disputed"]:
                    count += 1

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  {year}년: {count}개 이의신청 문항 표시 완료")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=== 이의신청 문항 주입 ===")
    inject_disputed(base_dir)
    print("완료!")
