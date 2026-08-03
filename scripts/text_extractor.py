import fitz
import json
import re
import os
import argparse
from typing import Tuple, List

class TextExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    # 컬럼 경계 판정 여유(pt). 문항 bbox 의 x1 은 본문 정렬 기준이라 줄 끝 글자가
    # 그 바깥까지 뻗는다(2026 기준 최대 307.5). 그래서 우측 한계는 bbox.x1 이 아니라
    # '다음 컬럼 시작 x0 - COLUMN_MARGIN' 으로 잡는다.
    COLUMN_MARGIN = 2.0

    def extract_text_from_bbox(
        self,
        page_num: int,
        bbox: List[float],
        next_column_x0: float = None,
        is_first_column: bool = True,
    ) -> str:
        """bbox 영역에서 텍스트 추출.

        get_text(clip=...) 는 글자가 사각형에 '완전히' 포함될 때만 잡아내므로
        경계에 걸친 줄 끝/줄 앞 한 글자(닫는 괄호·마침표·여는 괄호)가 사라진다.
        따라서 clip 대신 글자 중심점이 영역 안에 있는지로 직접 판정한다.

        next_column_x0: 같은 페이지에서 오른쪽에 인접한 컬럼의 시작 x 좌표.
                        None 이면 페이지 우측 끝까지를 이 문항의 영역으로 본다.
        is_first_column: 가장 왼쪽 컬럼이면 좌측도 페이지 끝까지 열어둔다.
                        (본문보다 왼쪽에서 시작하는 줄이 잘리는 것을 막는다)
        """
        try:
            page = self.doc[page_num - 1]  # 0-based index
            x0, y0, x1, y1 = bbox
            x_lo = page.rect.x0 if is_first_column else x0 - self.COLUMN_MARGIN
            x_hi = (
                next_column_x0 - self.COLUMN_MARGIN
                if next_column_x0 is not None
                else page.rect.x1
            )

            blocks = []  # (top_y, left_x, [line_text, ...])
            for block in page.get_text('rawdict')['blocks']:
                if block.get('type') != 0:  # 이미지 블록 제외
                    continue
                block_lines, top_y, left_x = [], None, None
                for line in block.get('lines', []):
                    chars, first_x, line_y = [], None, None
                    for span in line['spans']:
                        for ch in span['chars']:
                            cx0, cy0, cx1, cy1 = ch['bbox']
                            cx, cy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
                            if x_lo <= cx <= x_hi and y0 <= cy <= y1:
                                chars.append(ch['c'])
                                if first_x is None:
                                    first_x, line_y = cx0, cy
                    if chars:
                        block_lines.append(''.join(chars).rstrip())
                        if top_y is None:
                            top_y, left_x = line_y, first_x
                if block_lines:
                    blocks.append((top_y, left_x, block_lines))

            # 블록 순회 순서는 시각적 순서와 다를 수 있다(표·보기 박스가 선택지
            # 뒤로 밀려 ④ 에 흡수되는 원인). 블록 단위로만 (y, x) 정렬해 읽기
            # 순서를 복원하고, 블록 내부 줄 순서는 그대로 둔다. 줄 단위로 정렬하면
            # 나란히 놓인 코드 블록의 행이 서로 뒤섞인다.
            blocks.sort(key=lambda b: (round(b[0]), b[1]))
            return '\n'.join(line for _, _, lines in blocks for line in lines)
        except Exception as e:
            print(f"Error extracting text from page {page_num}: {e}")
            return ""

    def parse_question_and_choices(self, text: str) -> Tuple[str, List[str]]:
        """
        텍스트를 파싱하여 문제와 선택지로 분리
        문제 형식:
        1. 문제 내용...
        ① 선택지1
        ② 선택지2
        ③ 선택지3
        ④ 선택지4

        Note: 2025년 PDF는 선택지 기호 뒤 공백이 없음 (①정보시스템... 형태)
        """
        # 선택지 기호(①②③④)로 분리 (공백 선택적)
        choice_pattern = r'[①②③④]'

        # 첫 번째 선택지 위치 찾기
        choice_matches = list(re.finditer(choice_pattern, text))

        if not choice_matches:
            # 선택지가 없으면 전체를 문제로 간주
            return text.strip(), []

        # 첫 번째 선택지 위치
        first_choice_pos = choice_matches[0].start()
        question_part = text[:first_choice_pos].strip()
        choices_part = text[first_choice_pos:]

        # 문제 번호 제거 (예: "1. " 또는 "1 ")
        question_text = re.sub(r'^\d+\.\s*', '', question_part, count=1).strip()

        # 선택지 추출
        choices = []
        choice_lines = re.split(choice_pattern, choices_part)

        for line in choice_lines:
            if line.strip():
                # 개행 문자 제거하고 정리
                choice_text = ' '.join(line.split()).strip()
                if choice_text:
                    choices.append(choice_text)

        return question_text, choices

    def extract_questions(self, data_json_path: str) -> dict:
        """JSON 데이터에서 각 문제의 텍스트와 선택지 추출"""
        with open(data_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_questions = len([q for page in data['pages'] for q in page['questions']])
        processed = 0
        errors = 0

        for page in data['pages']:
            page_num = page['page_num']

            # 이 페이지에 존재하는 컬럼들의 시작 x 좌표 (2컬럼/4컬럼 레이아웃 공통)
            column_x0s = sorted({q['bbox'][0] for q in page['questions']})

            for question in page['questions']:
                q_num = question['question_num']
                bbox = question['bbox']

                # 오른쪽에 인접한 컬럼의 시작 좌표 = 이 문항 영역의 우측 한계
                next_column_x0 = next(
                    (x for x in column_x0s if x > bbox[0] + 1), None
                )

                # bbox 영역에서 텍스트 추출
                raw_text = self.extract_text_from_bbox(
                    page_num, bbox, next_column_x0,
                    is_first_column=(bbox[0] == column_x0s[0]),
                )

                if not raw_text.strip():
                    print(f"⚠️  문제 {q_num}: 텍스트 추출 실패 (페이지 {page_num})")
                    errors += 1
                    continue

                # 문제와 선택지 파싱
                question_text, choices = self.parse_question_and_choices(raw_text)

                # 선택지 개수 검증
                if len(choices) != 4:
                    print(f"⚠️  문제 {q_num}: 선택지 개수 불일치 ({len(choices)}/4)")
                    errors += 1

                # JSON에 추가
                question['question_text'] = question_text
                question['question_choice'] = choices

                processed += 1
                if processed % 20 == 0:
                    print(f"✓ {processed}/{total_questions} 문제 처리 완료...")

        print(f"\n✓ 총 {processed}개 문제 처리 완료")
        if errors > 0:
            print(f"⚠️  {errors}개 문제에서 주의 필요")

        self.doc.close()
        return data

    def save_json(self, data: dict, output_path: str):
        """JSON 파일 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ 파일 저장 완료: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='PDF에서 문제 텍스트와 선택지 추출')
    parser.add_argument('--year', type=int, required=True, help='대상 연도 (예: 2021)')
    args = parser.parse_args()

    year = args.year
    pdf_path = f"{year}/{year}_auditor.pdf"
    data_json_path = f"{year}/{year}_data.json"

    # 파일 존재 여부 확인
    if not os.path.exists(pdf_path):
        print(f"❌ PDF 파일을 찾을 수 없음: {pdf_path}")
        return

    if not os.path.exists(data_json_path):
        print(f"❌ JSON 파일을 찾을 수 없음: {data_json_path}")
        return

    print(f"시작: {year}년 문제 텍스트 및 선택지 추출")
    print(f"PDF: {pdf_path}")
    print(f"JSON: {data_json_path}")
    print("-" * 50)

    # 텍스트 추출
    extractor = TextExtractor(pdf_path)
    data = extractor.extract_questions(data_json_path)

    # 결과 저장
    extractor.save_json(data, data_json_path)

    print("-" * 50)
    print("✓ 작업 완료!")

if __name__ == "__main__":
    main()
