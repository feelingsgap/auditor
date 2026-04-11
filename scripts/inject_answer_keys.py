"""
inject_answer_keys.py
---------------------
{year}/{year}_answer_key.json 에서 문항별 정답을 읽어
{year}/{year}_data.json 의 각 문항에 다음 4개 필드를 주입한다.

  answer    : int (1~4)  — answer_key.json에서 직접 가져옴
  expl_claude : ""       — 추후 AI 배치로 채움
  expl_gemini : ""       — 추후 AI 배치로 채움
  expl_gpt    : ""       — 추후 AI 배치로 채움

이미 필드가 있으면 그대로 둔다 (--force 옵션으로 덮어쓰기 가능).
기존 필드(subject, bbox, question_text, question_choice 등)는 건드리지 않는다.
출력: UTF-8, ensure_ascii=False, 들여쓰기 2칸.
"""

import argparse
import json
import os
import sys


def inject_year(year: int, base_dir: str = '.', force: bool = False) -> None:
    key_path = os.path.join(base_dir, str(year), f'{year}_answer_key.json')
    data_path = os.path.join(base_dir, str(year), f'{year}_data.json')

    if not os.path.exists(key_path):
        print(f"[{year}] 정답 키 파일 없음: {key_path}", file=sys.stderr)
        return
    if not os.path.exists(data_path):
        print(f"[{year}] 데이터 파일 없음: {data_path}", file=sys.stderr)
        return

    with open(key_path, 'r', encoding='utf-8') as f:
        key_data = json.load(f)
    with open(data_path, 'r', encoding='utf-8') as f:
        year_data = json.load(f)

    answers = {int(k): v for k, v in key_data.get('answers', {}).items()}
    unresolved = set(key_data.get('unresolved', []))

    injected = 0
    skipped = 0
    missing_key = 0

    for page in year_data.get('pages', []):
        for q in page.get('questions', []):
            q_num = q.get('question_num')

            has_answer = 'answer' in q
            has_expls = 'expl_claude' in q and 'expl_gemini' in q and 'expl_gpt' in q

            if has_answer and has_expls and not force:
                skipped += 1
                continue

            # answer 주입
            if not has_answer or force:
                if q_num in answers:
                    q['answer'] = answers[q_num]
                elif q_num in unresolved:
                    q['answer'] = None  # 미해결 → null
                else:
                    q['answer'] = None
                    missing_key += 1

            # 해설 뼈대 주입 (빈 문자열)
            if not has_expls or force:
                q.setdefault('expl_claude', '')
                q.setdefault('expl_gemini', '')
                q.setdefault('expl_gpt', '')
                # force 시 덮어쓰기 (빈 문자열로만 — 이미 내용 있으면 유지)
                if force:
                    if not q.get('expl_claude'):
                        q['expl_claude'] = ''
                    if not q.get('expl_gemini'):
                        q['expl_gemini'] = ''
                    if not q.get('expl_gpt'):
                        q['expl_gpt'] = ''

            injected += 1

    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(year_data, f, ensure_ascii=False, indent=2)

    print(f"[{year}] 주입 완료: {injected}개 업데이트, {skipped}개 스킵, {missing_key}개 키 없음")
    if unresolved:
        print(f"  미해결 문항 (answer=null): {sorted(unresolved)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='answer_key.json → data.json 정답 및 해설 뼈대 주입')
    parser.add_argument('--years', nargs='+', type=int, default=[2021, 2022, 2023, 2024, 2025])
    parser.add_argument('--base-dir', default='.')
    parser.add_argument('--force', action='store_true', help='이미 있는 필드도 덮어쓰기')
    args = parser.parse_args()

    for year in args.years:
        inject_year(year, base_dir=args.base_dir, force=args.force)
