"""
answer_key_extractor.py
-----------------------
2021~2025년 정보시스템감리사 답안지 PDF에서 문항별 정답 번호(1~4)를 추출한다.

연도별 전략:
  - 2021/2022/2023 : 문제+답안이 합쳐진 문제지 PDF.
                     올바른 보기만 2 Tr (볼드 렌더링 모드) 사용.
                     content stream 파싱으로 볼드 좌표 목록 추출.
  - 2024           : 별도 답안표(문제/답안 2열 테이블). 직접 텍스트 추출.
  - 2025           : 문제지 PDF (landscape 4컬럼).
                     T10=일반, T12=볼드(정답).

출력 : {year}/{year}_answer_key.json
"""

import fitz
import json
import os
import re
import sys
from collections import defaultdict

# 보기 기호 → 번호 매핑
CHOICES = {'①': 1, '②': 2, '③': 3, '④': 4}

# 연도별 컬럼 split 경계 (x 좌표): (col_min, col_max) 리스트
COLUMN_SPLITS = {
    2021: [(0, 310), (310, 9999)],
    2022: [(0, 310), (310, 9999)],
    2023: [(0, 310), (310, 9999)],
    2024: None,  # 테이블 형식 — 별도 처리
    2025: [(0, 190), (190, 430), (430, 615), (615, 841)],
    2026: [(0, 310), (310, 9999)],
}

# 문항번호 패턴: "N." 뒤에 공백·한국어 따옴표·문자 또는 줄끝
# `)`, 숫자 등이 이어지면 본문 속 소수점/버전 번호로 간주해 제외
Q_PATTERN = re.compile(r'^(\d{1,3})\.(?:[ \t\u2018\u2019\u201c\u201d「]|$)')


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

def get_bold_positions(page: fitz.Page) -> dict:
    """
    2021/2022/2023 전용: PDF content stream에서 '2 Tr' 블록의 좌표를 추출.
    반환: {y_coord: [x_coord, ...]}  — y-행별 볼드 x 좌표 목록
    """
    content = b''
    for xref in page.get_contents():
        content += page.parent.xref_stream(xref)
    text_content = content.decode('latin-1', errors='replace')

    # q ... Q 블록 단위로 잘라서 2 Tr 포함된 것만 처리
    segments = re.findall(r'q\n(.*?)\nQ', text_content, re.DOTALL)

    bold_xy = []
    for seg in segments:
        if 'BT' not in seg or '2 Tr' not in seg:
            continue
        cm_m = re.search(
            r'([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+cm', seg)
        tm_m = re.search(
            r'([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+Tm', seg)
        if cm_m and tm_m:
            cm = [float(v) for v in cm_m.groups()]
            tm = [float(v) for v in tm_m.groups()]
            py_x = abs(cm[0]) * tm[4] + cm[4]
            py_y = abs(cm[3]) * tm[5]
            bold_xy.append((round(py_x, 1), round(py_y, 1)))

    # y-행 그룹화 (±5 허용), 같은 행의 x 좌표 모두 저장
    rows: dict = {}
    for x, y in bold_xy:
        matched_key = next((ky for ky in rows if abs(y - ky) <= 5), None)
        if matched_key is None:
            rows[y] = [x]
        else:
            rows[matched_key].append(x)
    return rows


def is_span_bold_by_position(sx: float, sy: float, bold_rows: dict) -> bool:
    """span (sx, sy)가 볼드 좌표와 근접한지 확인."""
    for by, bx_list in bold_rows.items():
        if abs(sy - by) <= 8:
            if any(abs(sx - bx) <= 50 for bx in bx_list):
                return True
    return False


def save_question_answer(answers: dict, q_num: int, choice_results: dict) -> None:
    """choice_results에서 볼드 보기를 찾아 answers에 저장."""
    bold_choices = [c for c, (_, _, is_bold) in choice_results.items() if is_bold]
    if len(bold_choices) >= 1:
        if len(bold_choices) > 1:
            print(f"  [경고] Q{q_num}: 볼드 보기 {len(bold_choices)}개 감지 → 첫 번째 사용")
        answers[q_num] = bold_choices[0]
    else:
        # 볼드가 없으면 미해결로 남김
        pass


def process_column_spans(col_spans, bold_rows, answers, bold_font=None,
                         orphan_out=None):
    """
    단일 컬럼의 span 목록을 y-순으로 스캔해 문항별 정답을 추출.

    bold_font : 문자열이면 해당 폰트명 == bold (2025 T12).
                None 이면 좌표 기반 볼드 판정 사용 (2021-2023).
    orphan_out: dict|None. 문항이 시작되기 전에 나오는 orphan 선택지를
                여기에 저장 (Q57 스타일 오버플로 처리용).
                {choice_num: (x, y, is_bold)} 형태로 채워짐.

    [볼드 우선 규칙]
    같은 choice_num에 대해:
    - 첫 번째 등록 이후 더 bold 한 것이 나오면 덮어쓴다.
    """
    current_q = None
    choice_results = {}
    pre_question_choices = {}  # 문항 번호 전에 나온 선택지 버퍼

    def _get_is_bold(x, y, font):
        if bold_font is not None:
            # 폰트 기반 (2025 T12 primary)
            is_b = (font == bold_font)
            # 폴백: content stream 볼드 (H2mjsM 등 코드폰트)
            if not is_b and bold_rows is not None:
                is_b = is_span_bold_by_position(x, y, bold_rows)
            return is_b
        else:
            # 좌표 기반 (2021-2023)
            return is_span_bold_by_position(x, y, bold_rows) if bold_rows else False

    def _register_choice(results, choice_num, x, y, is_bold):
        """볼드 우선 규칙에 따라 choice_results에 등록."""
        if choice_num not in results:
            results[choice_num] = (x, y, is_bold)
        elif is_bold and not results[choice_num][2]:
            # 새 것이 bold, 기존 것이 non-bold → 덮어쓰기
            results[choice_num] = (x, y, is_bold)

    for t, x, y, font in sorted(col_spans, key=lambda s: s[2]):
        # 문항번호 감지
        m = Q_PATTERN.match(t)
        if m:
            q_num = int(m.group(1))
            # 유효 조건: 범위 내 AND 현재 문항보다 큰 번호(단조증가)
            # — 질문 본문 내 "1. (생략)", "2. 항목..." 등이 오인식되는 것을 방지
            if 1 <= q_num <= 120 and q_num > (current_q or 0):
                # 이전 문항 저장
                if current_q is not None and choice_results:
                    save_question_answer(answers, current_q, choice_results)
                current_q = q_num
                choice_results = {}
                continue
            # 그 외(범위 밖 또는 역행 번호) 무시

        # 보기 기호 감지
        for glyph, choice_num in CHOICES.items():
            if t.startswith(glyph):
                is_bold = _get_is_bold(x, y, font)
                if current_q is not None:
                    _register_choice(choice_results, choice_num, x, y, is_bold)
                else:
                    # 아직 문항 없음 → orphan 버퍼에 저장
                    _register_choice(pre_question_choices, choice_num, x, y, is_bold)
                break

    # 마지막 문항 저장
    if current_q is not None and choice_results:
        save_question_answer(answers, current_q, choice_results)

    # orphan 선택지 반환 (호출자에서 처리)
    if orphan_out is not None:
        orphan_out.update(pre_question_choices)


def get_page_spans(page: fitz.Page):
    """페이지의 모든 텍스트 span을 (text, x, y, font) 리스트로 반환."""
    spans = []
    for block in page.get_text('dict')['blocks']:
        if block['type'] != 0:
            continue
        for line in block['lines']:
            for span in line['spans']:
                t = span['text'].strip()
                if t:
                    spans.append((t, span['origin'][0], span['origin'][1], span['font']))
    return spans


# ---------------------------------------------------------------------------
# 연도별 추출 로직
# ---------------------------------------------------------------------------

def _load_page_question_map(year: int, base_dir: str) -> dict:
    """data.json에서 {pdf_page_idx: {left: [q_nums], right: [q_nums]}} 로드."""
    data_path = os.path.join(base_dir, str(year), f'{year}_data.json')
    if not os.path.exists(data_path):
        return {}
    with open(data_path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    page_map = {}
    for page in d['pages']:
        pdf_idx = page['page_num'] - 1
        left_qs = sorted([q['question_num'] for q in page['questions'] if q['column'] == 'left'])
        right_qs = sorted([q['question_num'] for q in page['questions'] if q['column'] == 'right'])
        page_map[pdf_idx] = {'left': left_qs, 'right': right_qs}
    return page_map


def extract_2021_2023(year: int, base_dir: str = '.', pdf_filename: str = None) -> dict:
    """2021, 2022, 2023년: content stream 볼드 감지.
    pdf_filename: 기본값은 '{year}_answer.pdf'. 2026처럼 별도 정답 PDF가 없을 때 사용."""
    if pdf_filename is None:
        pdf_filename = f'{year}_answer.pdf'
    pdf_path = os.path.join(base_dir, str(year), pdf_filename)
    doc = fitz.open(pdf_path)
    col_splits = COLUMN_SPLITS[year]
    answers = {}
    page_q_map = _load_page_question_map(year, base_dir)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        bold_rows = get_bold_positions(page)
        all_spans = get_page_spans(page)

        right_orphan: dict = {}

        for col_idx, (col_min, col_max) in enumerate(col_splits):
            col_spans = [(t, x, y, f) for t, x, y, f in all_spans
                         if col_min <= x < col_max]
            if col_idx == 0:
                process_column_spans(col_spans, bold_rows, answers, bold_font=None)
            else:
                process_column_spans(col_spans, bold_rows, answers, bold_font=None,
                                     orphan_out=right_orphan)

        # orphan 선택지 → 왼쪽 컬럼 마지막 미답 문항에 배정 (Q57 스타일)
        if right_orphan:
            bold_orphan = {c: v for c, v in right_orphan.items() if v[2]}
            if bold_orphan:
                page_info = page_q_map.get(page_idx, {})
                left_qs = page_info.get('left', [])
                # 왼쪽 컬럼에서 아직 정답이 없는 문항 (가장 큰 번호 우선)
                unanswered_left = [q for q in reversed(left_qs) if q not in answers]
                if unanswered_left:
                    target_q = unanswered_left[0]
                    save_question_answer(answers, target_q, {c: v for c, v in right_orphan.items()})
                    print(f"  [orphan] Q{target_q}: 오른쪽 orphan 선택지로 정답 보완")
                else:
                    print(f"  [정보] 페이지 {page_idx}: orphan 볼드 {list(bold_orphan.keys())} 매칭 실패 — 수동 확인")

    doc.close()
    return answers


def extract_2024(base_dir: str = '.') -> dict:
    """2024년: 답안표 직접 파싱."""
    pdf_path = os.path.join(base_dir, '2024', '2024_answer.pdf')
    doc = fitz.open(pdf_path)
    answers = {}

    glyph_map = {'①': 1, '②': 2, '③': 3, '④': 4}

    for page in doc:
        text = page.get_text()
        # 문항번호와 답안 기호가 줄바꿈으로 분리된 패턴: "숫자\n기호"
        for m in re.finditer(r'(\d+)\n([①②③④](?:,[①②③④])?)', text):
            q_num = int(m.group(1))
            choices_str = m.group(2)
            if 1 <= q_num <= 120:
                first_glyph = choices_str[0]
                if first_glyph in glyph_map:
                    if q_num not in answers:
                        answers[q_num] = glyph_map[first_glyph]
                        if ',' in choices_str:
                            print(f"  [참고] Q{q_num}: 복수 정답 '{choices_str}' → {glyph_map[first_glyph]} 사용")

    doc.close()
    return answers


def extract_2025(base_dir: str = '.') -> dict:
    """2025년: T12 폰트가 정답 (landscape 4컬럼).
    폴백: H2mjsM 등 코드 폰트 선택지는 2 Tr content stream 감지 사용.
    """
    pdf_path = os.path.join(base_dir, '2025', '2025_answer.pdf')
    doc = fitz.open(pdf_path)
    col_splits = COLUMN_SPLITS[2025]
    answers = {}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # 2 Tr content stream 볼드 (코드 폰트 폴백용)
        bold_rows = get_bold_positions(page)
        all_spans = get_page_spans(page)

        for col_min, col_max in col_splits:
            col_spans = [(t, x, y, f) for t, x, y, f in all_spans
                         if col_min <= x < col_max]
            process_column_spans(col_spans, bold_rows=bold_rows, answers=answers, bold_font='T12')

    doc.close()
    return answers


# ---------------------------------------------------------------------------
# 주 실행
# ---------------------------------------------------------------------------

EXTRACTORS = {
    2021: lambda base: extract_2021_2023(2021, base),
    2022: lambda base: extract_2021_2023(2022, base),
    2023: lambda base: extract_2021_2023(2023, base),
    2024: lambda base: extract_2024(base),
    2025: lambda base: extract_2025(base),
    2026: lambda base: extract_2021_2023(2026, base, '2026_auditor.pdf'),
}


def run_extraction(years=None, base_dir='.', verbose=False):
    if years is None:
        years = list(EXTRACTORS.keys())

    results = {}
    for year in years:
        print(f"\n=== {year}년 정답 추출 중 ===")
        extractor = EXTRACTORS.get(year)
        if extractor is None:
            print(f"  [오류] {year}년 추출기가 없습니다.")
            continue

        answers = extractor(base_dir)

        # 누락 확인
        expected = set(range(1, 121))
        missing = sorted(expected - set(answers.keys()))
        extra = sorted(set(answers.keys()) - expected)

        print(f"  추출: {len(answers)}문항  누락: {missing if missing else '없음'}  초과: {extra if extra else '없음'}")

        if verbose:
            for q in sorted(answers):
                print(f"    Q{q:3d}: {answers[q]}")

        # 결과 저장
        output = {
            'year': year,
            'total': len(answers),
            'answers': {str(q): answers[q] for q in sorted(answers)},
            'unresolved': missing,
        }
        out_path = os.path.join(base_dir, str(year), f'{year}_answer_key.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  저장: {out_path}")
        results[year] = output

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='감리사 답안지 PDF 정답 추출')
    parser.add_argument('--years', nargs='+', type=int, default=[2021, 2022, 2023, 2024, 2025, 2026],
                        help='처리할 연도 목록 (기본: 2021~2025)')
    parser.add_argument('--base-dir', default='.', help='프로젝트 루트 디렉토리')
    parser.add_argument('--verbose', action='store_true', help='문항별 정답 출력')
    args = parser.parse_args()

    run_extraction(years=args.years, base_dir=args.base_dir, verbose=args.verbose)
