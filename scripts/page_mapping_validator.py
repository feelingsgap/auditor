#!/usr/bin/env python3
"""
페이지-문항 매핑 정확성 검증 및 수정 시스템
"""

import json
import fitz  # PyMuPDF
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
import numpy as np
from collections import defaultdict
import re
import os

@dataclass
class QuestionInfo:
    question_num: int
    subject: str
    page_num: int
    bbox: List[float]
    column: str
    y_center: float = 0.0
    
    def __post_init__(self):
        self.y_center = (self.bbox[1] + self.bbox[3]) / 2

@dataclass
class PageLayout:
    page_num: int
    questions: List[QuestionInfo]
    expected_sequence: List[int]
    missing_questions: List[int]
    duplicate_questions: List[int]
    out_of_order: List[int]

class PageMappingValidator:
    def __init__(self, pdf_path: str, json_path: str):
        self.pdf_path = pdf_path
        self.json_path = json_path
        self.pdf_doc = fitz.open(pdf_path)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        
        self.year = self.metadata.get('year', 0)
        self.total_questions = self.metadata.get('total_questions', 120)
        
    def analyze_page_layouts(self) -> Dict[int, PageLayout]:
        """각 페이지의 문항 배치 분석"""
        page_layouts = {}
        
        # 모든 문항 정보 수집
        all_questions = []
        for page_data in self.metadata["pages"]:
            page_num = page_data["page_num"]
            for q_data in page_data["questions"]:
                question = QuestionInfo(
                    question_num=q_data["question_num"],
                    subject=q_data["subject"],
                    page_num=page_num,
                    bbox=q_data["bbox"],
                    column=q_data["column"]
                )
                all_questions.append(question)
        
        # 페이지별 분석
        for page_data in self.metadata["pages"]:
            page_num = page_data["page_num"]
            page_questions = [q for q in all_questions if q.page_num == page_num]
            
            # 문항 번호 추출 및 정렬
            question_nums = [q.question_num for q in page_questions]
            question_nums_sorted = sorted(question_nums)
            
            # 예상 순서 계산 (첫 번째와 마지막 번호 기준)
            if question_nums_sorted:
                min_q = min(question_nums_sorted)
                max_q = max(question_nums_sorted)
                expected_sequence = list(range(min_q, max_q + 1))
            else:
                expected_sequence = []
            
            # 누락 및 중복 문항 찾기
            missing_questions = [q for q in expected_sequence if q not in question_nums]
            duplicate_questions = [q for q in question_nums if question_nums.count(q) > 1]
            
            # 순서 오류 찾기 (Y좌표 기준)
            out_of_order = self._find_out_of_order_questions(page_questions)
            
            page_layouts[page_num] = PageLayout(
                page_num=page_num,
                questions=page_questions,
                expected_sequence=expected_sequence,
                missing_questions=missing_questions,
                duplicate_questions=duplicate_questions,
                out_of_order=out_of_order
            )
        
        return page_layouts
    
    def _find_out_of_order_questions(self, questions: List[QuestionInfo]) -> List[int]:
        """Y좌표 기준으로 순서가 맞지 않는 문항 찾기"""
        out_of_order = []
        
        # 컬럼별로 분리
        left_questions = [q for q in questions if q.column == "left"]
        right_questions = [q for q in questions if q.column == "right"]
        
        for column_questions in [left_questions, right_questions]:
            if len(column_questions) < 2:
                continue
                
            # Y좌표 기준 정렬
            sorted_by_y = sorted(column_questions, key=lambda q: q.y_center)
            sorted_by_num = sorted(column_questions, key=lambda q: q.question_num)
            
            # 순서 비교
            for i, (q_by_y, q_by_num) in enumerate(zip(sorted_by_y, sorted_by_num)):
                if q_by_y.question_num != q_by_num.question_num:
                    out_of_order.append(q_by_y.question_num)
        
        return list(set(out_of_order))
    
    def detect_pdf_layout_pattern(self) -> Dict:
        """PDF에서 실제 문항 패턴 분석"""
        layout_info = {
            "page_count": len(self.pdf_doc),
            "question_patterns": {},
            "layout_consistency": {}
        }
        
        question_number_pattern = re.compile(r'(\d+)\s*\.\s*')
        
        for page_num in range(2, min(6, len(self.pdf_doc))):  # 처음 몇 페이지만 분석
            page = self.pdf_doc[page_num]
            text_blocks = page.get_text("dict")
            
            # 문항 번호 패턴 찾기
            found_questions = []
            for block in text_blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            matches = question_number_pattern.findall(text)
                            for match in matches:
                                try:
                                    q_num = int(match)
                                    bbox = span["bbox"]
                                    found_questions.append({
                                        "question_num": q_num,
                                        "bbox": bbox,
                                        "y_pos": bbox[1],
                                        "text_sample": text[:50]
                                    })
                                except ValueError:
                                    continue
            
            # Y좌표 기준 정렬
            found_questions.sort(key=lambda x: x["y_pos"])
            
            layout_info["question_patterns"][page_num + 1] = {
                "found_questions": found_questions,
                "question_count": len(found_questions),
                "y_positions": [q["y_pos"] for q in found_questions],
                "question_numbers": [q["question_num"] for q in found_questions]
            }
        
        return layout_info
    
    def cross_validate_with_pdf(self, page_layouts: Dict[int, PageLayout]) -> Dict:
        """PDF 내용과 JSON 메타데이터 교차 검증"""
        validation_results = {}
        pdf_layout = self.detect_pdf_layout_pattern()
        
        for page_num, layout in page_layouts.items():
            if page_num in pdf_layout["question_patterns"]:
                pdf_questions = pdf_layout["question_patterns"][page_num]["question_numbers"]
                json_questions = [q.question_num for q in layout.questions]
                
                validation_results[page_num] = {
                    "pdf_questions": sorted(pdf_questions),
                    "json_questions": sorted(json_questions),
                    "missing_in_json": [q for q in pdf_questions if q not in json_questions],
                    "extra_in_json": [q for q in json_questions if q not in pdf_questions],
                    "match_rate": len(set(pdf_questions) & set(json_questions)) / max(len(set(pdf_questions)), 1)
                }
        
        return validation_results
    
    def generate_corrected_mapping(self, page_layouts: Dict[int, PageLayout], 
                                 validation_results: Dict) -> Dict:
        """수정된 페이지-문항 매핑 생성"""
        corrected_metadata = {
            "year": self.year,
            "total_questions": self.total_questions,
            "pages": []
        }
        
        # 모든 문항을 수집하여 전체적으로 재배치
        all_questions = []
        for layout in page_layouts.values():
            all_questions.extend(layout.questions)
        
        # 문항 번호 기준 정렬
        all_questions.sort(key=lambda q: q.question_num)
        
        # PDF 검증 결과를 기반으로 올바른 페이지 찾기
        question_to_correct_page = {}
        for page_num, validation in validation_results.items():
            for q_num in validation["pdf_questions"]:
                question_to_correct_page[q_num] = page_num
        
        # 페이지별로 문항 재배치
        pages_dict = defaultdict(list)
        
        for question in all_questions:
            # 올바른 페이지 결정
            correct_page = question_to_correct_page.get(
                question.question_num, 
                question.page_num  # 검증 정보가 없으면 기존 페이지 유지
            )
            
            pages_dict[correct_page].append({
                "question_num": question.question_num,
                "subject": question.subject,
                "bbox": question.bbox,
                "column": question.column
            })
        
        # 최종 페이지 데이터 생성
        for page_num in sorted(pages_dict.keys()):
            questions = pages_dict[page_num]
            # 각 페이지 내에서 Y좌표 기준 정렬
            questions.sort(key=lambda q: q["bbox"][1])
            
            corrected_metadata["pages"].append({
                "page_num": page_num,
                "questions": questions
            })
        
        return corrected_metadata
    
    def generate_validation_report(self, page_layouts: Dict[int, PageLayout], 
                                 validation_results: Dict) -> str:
        """검증 보고서 생성"""
        report = []
        report.append(f"=== {self.year}년 페이지-문항 매핑 검증 보고서 ===\n")
        
        # 전체 통계
        total_questions_found = sum(len(layout.questions) for layout in page_layouts.values())
        total_missing = sum(len(layout.missing_questions) for layout in page_layouts.values())
        total_duplicates = sum(len(layout.duplicate_questions) for layout in page_layouts.values())
        total_out_of_order = sum(len(layout.out_of_order) for layout in page_layouts.values())
        
        report.append(f"전체 문항 수: {total_questions_found}")
        report.append(f"누락된 문항: {total_missing}개")
        report.append(f"중복된 문항: {total_duplicates}개")
        report.append(f"순서 오류 문항: {total_out_of_order}개\n")
        
        # 페이지별 상세 분석
        for page_num, layout in sorted(page_layouts.items()):
            report.append(f"[페이지 {page_num}]")
            report.append(f"  문항 수: {len(layout.questions)}")
            report.append(f"  문항 번호: {sorted([q.question_num for q in layout.questions])}")
            
            if layout.missing_questions:
                report.append(f"  누락: {layout.missing_questions}")
            
            if layout.duplicate_questions:
                report.append(f"  중복: {layout.duplicate_questions}")
                
            if layout.out_of_order:
                report.append(f"  순서오류: {layout.out_of_order}")
            
            # PDF 검증 결과
            if page_num in validation_results:
                validation = validation_results[page_num]
                report.append(f"  PDF 대조 일치율: {validation['match_rate']:.2%}")
                if validation['missing_in_json']:
                    report.append(f"  JSON에서 누락: {validation['missing_in_json']}")
                if validation['extra_in_json']:
                    report.append(f"  JSON에 추가: {validation['extra_in_json']}")
            
            report.append("")
        
        return "\n".join(report)
    
    def run_full_validation(self) -> Tuple[Dict, str]:
        """전체 검증 프로세스 실행"""
        print(f"{self.year}년 페이지-문항 매핑 검증 시작...")
        
        # 1. 페이지 레이아웃 분석
        page_layouts = self.analyze_page_layouts()
        print(f"페이지 레이아웃 분석 완료: {len(page_layouts)}개 페이지")
        
        # 2. PDF와 교차 검증
        validation_results = self.cross_validate_with_pdf(page_layouts)
        print(f"PDF 교차 검증 완료: {len(validation_results)}개 페이지 검증")
        
        # 3. 수정된 매핑 생성
        corrected_mapping = self.generate_corrected_mapping(page_layouts, validation_results)
        print("수정된 매핑 생성 완료")
        
        # 4. 검증 보고서 생성
        report = self.generate_validation_report(page_layouts, validation_results)
        print("검증 보고서 생성 완료")
        
        return corrected_mapping, report
    
    def save_corrected_mapping(self, corrected_mapping: Dict, output_path: str):
        """수정된 매핑을 파일로 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(corrected_mapping, f, ensure_ascii=False, indent=2)
        print(f"수정된 매핑 저장: {output_path}")

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("사용법: python page_mapping_validator.py <연도>")
        print("예시: python page_mapping_validator.py 2024")
        sys.exit(1)
    
    year = int(sys.argv[1])
    
    # 파일 경로 수정
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(base_dir, "source", f"{year}_auditor.pdf")
    json_path = os.path.join(base_dir, str(year), f"{year}_data.json")
    
    # 파일 존재 확인
    if not os.path.exists(pdf_path):
        print(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)
    
    if not os.path.exists(json_path):
        print(f"JSON 파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    
    print(f"{year}년 페이지-문항 매핑 검증 시작...")
    print(f"PDF: {pdf_path}")
    print(f"JSON: {json_path}")
    
    try:
        validator = PageMappingValidator(pdf_path, json_path)
        page_layouts, report = validator.run_full_validation()
        
        print("\n" + "="*60)
        print("검증 보고서")
        print("="*60)
        print(report)
        
        # 수정된 매핑 저장
        corrected_output = os.path.join(base_dir, str(year), f"{year}_data_corrected.json")
        validator.save_corrected_mapping(page_layouts, corrected_output)
        print(f"\n수정된 매핑이 저장되었습니다: {corrected_output}")
        
    except Exception as e:
        print(f"검증 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()