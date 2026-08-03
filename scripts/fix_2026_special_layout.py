"""
2026년 특수 레이아웃 문항 보정.

text_extractor.py 는 선택지 기호(①②③④)가 보기 내용보다 '앞'에 온다고 가정한다.
그러나 일부 문항은 기호가 코드 박스/그림 왼쪽 세로 중앙에 놓여, 읽기 순서상
기호가 자기 보기 내용보다 뒤에 온다. 그런 문항은 자동 분할이 어긋나므로 여기서
개별 보정한다.

text_extractor.py 를 2026 에 다시 돌린 경우 이 스크립트를 이어서 실행하면 된다.

사용: python scripts/fix_2026_special_layout.py
"""
import json
import os

DATA_PATH = os.path.join('2026', '2026_data.json')

# 선택지가 그림(표·다이어그램)이라 텍스트 선택지를 구성할 수 없는 문항.
# subjects.html 은 문항 PNG 를 보여주므로 학습에는 지장이 없다.
IMAGE_ONLY_CHOICES = {28, 75}


def fix_q57(question: dict) -> bool:
    """Q57: 보기 ①의 SQL 이 question_text 끝에 붙고 선택지가 3개로 밀린 것을 되돌린다."""
    marker = 'SELECT E1.deptcode, E1.deptphone'
    text = question['question_text']
    idx = text.find(marker)
    if idx == -1 or len(question['question_choice']) != 3:
        return False
    question['question_text'] = text[:idx].rstrip()
    first_choice = ' '.join(text[idx:].split())
    question['question_choice'] = [first_choice] + question['question_choice']
    return True


def main():
    with open(DATA_PATH, encoding='utf-8') as f:
        data = json.load(f)

    questions = {q['question_num']: q for p in data['pages'] for q in p['questions']}
    changed = []

    if fix_q57(questions[57]):
        changed.append(57)

    for num in sorted(IMAGE_ONLY_CHOICES):
        n_choices = len(questions[num]['question_choice'] or [])
        print(f"  [정보] Q{num}: 선택지가 그림 — 텍스트 선택지 {n_choices}개 (PNG 참조 필요)")

    if changed:
        with open(DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ 보정 완료: {changed}")
    else:
        print("보정할 항목 없음 (이미 반영됨)")


if __name__ == '__main__':
    main()
