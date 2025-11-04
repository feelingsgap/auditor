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

    def extract_text_from_bbox(self, page_num: int, bbox: List[float]) -> str:
        """bbox 영역에서 텍스트 추출"""
        try:
            page = self.doc[page_num - 1]  # 0-based index
            rect = fitz.Rect(bbox)
            text = page.get_text('text', clip=rect)
            return text
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

            for question in page['questions']:
                q_num = question['question_num']
                bbox = question['bbox']

                # bbox 영역에서 텍스트 추출
                raw_text = self.extract_text_from_bbox(page_num, bbox)

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
