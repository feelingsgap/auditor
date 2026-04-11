"""
expl_progress.py
----------------
expl_staging/{ai}/{year}/{q_num}.txt 의 존재 여부를 기준으로
해설 생성 진행 상황을 집계해 출력한다.

사용법:
    python scripts/expl_progress.py
    python scripts/expl_progress.py --field expl_claude --staging-dir expl_staging/claude
    python scripts/expl_progress.py --list-remaining --years 2025 2024
"""

import argparse
import json
import os


YEARS = [2025, 2024, 2023, 2022, 2021]  # 내림차순 (기본 처리 순서)


def load_questions(base_dir: str, years: list[int]) -> list[dict]:
    questions = []
    for year in years:
        data_path = os.path.join(base_dir, str(year), f"{year}_data.json")
        if not os.path.exists(data_path):
            continue
        with open(data_path, "r", encoding="utf-8") as f:
            year_data = json.load(f)
        for page in year_data.get("pages", []):
            for q in page.get("questions", []):
                questions.append({
                    "year": year,
                    "question_num": q.get("question_num"),
                })
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="expl 해설 생성 진행 상황 조회")
    parser.add_argument("--staging-dir", default="expl_staging/claude",
                        help="스테이징 루트 (기본: expl_staging/claude)")
    parser.add_argument("--years", nargs="+", type=int, default=YEARS)
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--list-remaining", action="store_true",
                        help="남은 문항 목록 출력 (연도, 번호)")
    args = parser.parse_args()

    questions = load_questions(args.base_dir, args.years)
    total = len(questions)
    done = 0
    remaining = []

    for q in questions:
        staging_file = os.path.join(args.staging_dir, str(q["year"]), f"{q['question_num']}.txt")
        if os.path.exists(staging_file):
            done += 1
        else:
            remaining.append(q)

    pct = done / total * 100 if total else 0
    print(f"진행 상황: {done}/{total} ({pct:.1f}%)")
    print(f"완료: {done}  남음: {len(remaining)}")
    print()

    # 연도별 집계
    year_done: dict[int, int] = {}
    year_total: dict[int, int] = {}
    for q in questions:
        year_total[q["year"]] = year_total.get(q["year"], 0) + 1
        staging_file = os.path.join(args.staging_dir, str(q["year"]), f"{q['question_num']}.txt")
        if os.path.exists(staging_file):
            year_done[q["year"]] = year_done.get(q["year"], 0) + 1

    for year in sorted(year_total.keys(), reverse=True):
        d = year_done.get(year, 0)
        t = year_total[year]
        bar_filled = int(d / t * 20) if t else 0
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(f"  {year}: [{bar}] {d:3d}/{t}")

    if args.list_remaining and remaining:
        print(f"\n--- 남은 문항 ({len(remaining)}개) ---")
        for q in remaining:
            print(f"  {q['year']} Q{q['question_num']:3d}")


if __name__ == "__main__":
    main()
