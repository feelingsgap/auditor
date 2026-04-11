"""
apply_expl_staging.py
---------------------
expl_staging/{ai}/{year}/{q_num}.txt 에 저장된 해설 원문을 읽어
{year}/{year}_data.json 의 해당 문항 필드(expl_claude / expl_gemini / expl_gpt)에 주입한다.

사용법:
    python scripts/apply_expl_staging.py --field expl_claude --staging-dir expl_staging/claude
    python scripts/apply_expl_staging.py --field expl_claude --staging-dir expl_staging/claude --years 2024 2025 --force

기본 동작:
- 스테이징 파일이 존재하는 문항만 처리.
- 대상 필드가 이미 비어 있지 않으면 스킵 (덮어쓰기는 --force).
- 기존 포맷 유지 (UTF-8, ensure_ascii=False, indent=2).
"""

import argparse
import json
import os
import sys


VALID_FIELDS = {"expl_claude", "expl_gemini", "expl_gpt"}


def apply_year(year: int, field: str, staging_dir: str, base_dir: str, force: bool) -> tuple[int, int, int]:
    year_staging = os.path.join(staging_dir, str(year))
    data_path = os.path.join(base_dir, str(year), f"{year}_data.json")

    if not os.path.exists(data_path):
        print(f"[{year}] 데이터 파일 없음: {data_path}", file=sys.stderr)
        return (0, 0, 0)
    if not os.path.isdir(year_staging):
        print(f"[{year}] 스테이징 디렉터리 없음: {year_staging}")
        return (0, 0, 0)

    with open(data_path, "r", encoding="utf-8") as f:
        year_data = json.load(f)

    injected = 0
    skipped = 0
    missing = 0

    for page in year_data.get("pages", []):
        for q in page.get("questions", []):
            q_num = q.get("question_num")
            staging_file = os.path.join(year_staging, f"{q_num}.txt")

            if not os.path.exists(staging_file):
                missing += 1
                continue

            existing = q.get(field, "")
            if existing and not force:
                skipped += 1
                continue

            with open(staging_file, "r", encoding="utf-8") as sf:
                content = sf.read().rstrip("\n")

            q[field] = content
            injected += 1

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(year_data, f, ensure_ascii=False, indent=2)

    print(f"[{year}] {field}: 주입 {injected}개, 스킵 {skipped}개, 스테이징 없음 {missing}개")
    return (injected, skipped, missing)


def main() -> None:
    parser = argparse.ArgumentParser(description="스테이징 텍스트 파일을 data.json 해설 필드에 주입")
    parser.add_argument("--field", required=True, choices=sorted(VALID_FIELDS),
                        help="주입 대상 필드명")
    parser.add_argument("--staging-dir", required=True,
                        help="스테이징 루트 (예: expl_staging/claude)")
    parser.add_argument("--years", nargs="+", type=int,
                        default=[2021, 2022, 2023, 2024, 2025])
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--force", action="store_true",
                        help="기존에 내용이 있어도 덮어쓰기")
    args = parser.parse_args()

    if not os.path.isdir(args.staging_dir):
        print(f"스테이징 루트 디렉터리가 없습니다: {args.staging_dir}", file=sys.stderr)
        sys.exit(1)

    total_injected = 0
    total_skipped = 0
    total_missing = 0

    for year in args.years:
        i, s, m = apply_year(year, args.field, args.staging_dir, args.base_dir, args.force)
        total_injected += i
        total_skipped += s
        total_missing += m

    print(f"\n[합계] 주입 {total_injected}개, 스킵 {total_skipped}개, 스테이징 없음 {total_missing}개")


if __name__ == "__main__":
    main()
