import fitz
import json
import re
import os
from typing import Dict, List, Tuple

class PDFAnalyzer:
    def __init__(self):
        self.subjects = {
            1: "감리 및 사업관리",  # 1-25
            26: "소프트웨어 공학",  # 26-50
            51: "데이터베이스",     # 51-75
            76: "시스템 구조",   # 76-100
            101: "보안"     # 101-120
        }
        self.page_margins = {"left": 40, "right": 40, "top": 50, "bottom": 50}
        # 연도별 레이아웃 캐시
        self.layout_cache = {}
        
        # 연도별 표준 컬럼 폭 정의 (포인트 단위)
        self.standard_column_widths = {
            2021: {"left": 290, "right": 290},   # 우측 폭 대폭 증가: 320pt로 완전 잘림 방지
            2022: {"left": 290, "right": 290},   # 우측 폭 대폭 증가: 310pt로 완전 잘림 방지
            2023: {"left": 290, "right": 290},   # 우측 폭 대폭 증가: 310pt로 완전 잘림 방지
            2024: {"left": 235, "right": 235},   # 기존 유지 (문제 없음)
            2026: {"left": 235, "right": 250},   # 우측 텍스트가 553pt까지 존재
        }
        
        # 연도별 표준 컬럼 시작점 정의 (포인트 단위) - 실제 감지된 위치 기반
        self.standard_column_positions = {
            2021: {"left": 57, "right": 375, "gap": 25},    # 실제 감지: 좌측 56-57pt, 우측 375-376pt
            2022: {"left": 57, "right": 376, "gap": 25},    # 실제 감지: 좌측 56-57pt, 우측 376pt
            2023: {"left": 56, "right": 375, "gap": 25},    # 실제 감지: 좌측 56pt, 우측 375pt
            2024: {"left": 50, "right": 309, "gap": 20},    # 중앙 정렬 조정: 좌측 +3pt, 우측 +3pt
            2026: {"left": 50, "right": 309, "gap": 20},    # 2024와 동일
        }
    
    def get_subject_by_number(self, question_num: int) -> str:
        for start_num in sorted(self.subjects.keys(), reverse=True):
            if question_num >= start_num:
                return self.subjects[start_num]
        return "기타"
    
    def detect_adaptive_layout(self, doc: fitz.Document, year: int) -> Dict:
        """연도별 적응형 레이아웃 자동 감지"""
        if year in self.layout_cache:
            return self.layout_cache[year]
        
        print(f"{year}년 PDF 레이아웃 분석 중...")
        
        # 첫 몇 페이지에서 문항 위치 분석
        layout_stats = {"left_x": [], "right_x": [], "question_positions": []}
        
        for page_num in range(1, min(4, len(doc))):  # 2-4페이지 분석
            page = doc[page_num]
            text_blocks = page.get_text("dict")
            
            # 문항 번호 패턴으로 위치 찾기
            question_pattern = re.compile(r'^(\d+)\s*\.\s*')
            
            for block in text_blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            match = question_pattern.match(text)
                            if match:
                                q_num = int(match.group(1))
                                if 1 <= q_num <= 120:
                                    bbox = span["bbox"]
                                    layout_stats["question_positions"].append({
                                        "q_num": q_num,
                                        "x": bbox[0],
                                        "y": bbox[1],
                                        "page": page_num + 1
                                    })
        
        # 좌우 단락 경계 자동 감지
        x_positions = [pos["x"] for pos in layout_stats["question_positions"]]
        if len(x_positions) < 4:
            # 기본값 사용
            detected_layout = {
                "left_column": {"x1": 40, "x2": 300},
                "right_column": {"x1": 320, "x2": 580},
                "page_margins": {"left": 40, "right": 40, "top": 75, "bottom": 50}
            }
        else:
            # K-means 클러스터링으로 좌우 구분
            x_sorted = sorted(set(x_positions))
            mid_point = (min(x_positions) + max(x_positions)) / 2
            
            left_xs = [x for x in x_positions if x < mid_point]
            right_xs = [x for x in x_positions if x >= mid_point]
            
            left_boundary = max(left_xs) + 20 if left_xs else 300
            right_start = min(right_xs) - 10 if right_xs else 320
            
            detected_layout = {
                "left_column": {"x1": 40, "x2": left_boundary},
                "right_column": {"x1": right_start, "x2": max(x_positions) + 250},
                "page_margins": {"left": 40, "right": 40, "top": 75, "bottom": 50}
            }
        
        print(f"감지된 레이아웃: 좌측({detected_layout['left_column']['x1']}-{detected_layout['left_column']['x2']}), "
              f"우측({detected_layout['right_column']['x1']}-{detected_layout['right_column']['x2']})")
        
        self.layout_cache[year] = detected_layout
        return detected_layout
    
    def calculate_column_layout(self, page_rect, adaptive_layout: Dict):
        """적응형 레이아웃 기반 단락 계산"""
        page_width = page_rect.width
        page_height = page_rect.height
        
        margins = adaptive_layout["page_margins"]
        left_col_info = adaptive_layout["left_column"]
        right_col_info = adaptive_layout["right_column"]
        
        # 컨텐츠 영역
        content_top = margins["top"]
        content_bottom = page_height - margins["bottom"]
        
        left_column = {
            "x1": left_col_info["x1"],
            "x2": left_col_info["x2"],
            "y1": content_top,
            "y2": content_bottom
        }
        
        right_column = {
            "x1": right_col_info["x1"],
            "x2": right_col_info["x2"],
            "y1": content_top,
            "y2": content_bottom
        }
        
        return left_column, right_column
    
    def find_question_positions(self, page, question_nums: List[int], year: int = None):
        """강화된 문항 번호 위치 찾기 - 모든 문항을 확실히 찾도록 개선"""
        positions = {}

        # 컬럼 시작 x좌표 필터 (들여쓰기 선택지 오인 방지)
        col_x_filter = None
        if year and year in self.standard_column_positions:
            pos = self.standard_column_positions[year]
            col_x_filter = {
                "left_max": pos["left"] + 2,
                "right_max": pos["right"] + 2,
            }

        # PDF 텍스트를 구조화된 형태로 분석
        text_dict = page.get_text("dict")
        
        for num in question_nums:
            found = False
            detection_method = ""
            
            # 1단계: 확장된 정확한 패턴으로 찾기
            precise_patterns = [
                rf'\b{num}\s*\.\s*[가-힣A-Za-z]',  # 숫자 + 점 + 공백 + 한글/영문
                rf'^\s*{num}\s*\.\s*',             # 줄 시작 + 숫자 + 점
                rf'\n\s*{num}\s*\.\s*',            # 새줄 + 숫자 + 점
                rf'{num}\s*\.\s*\S',               # 숫자 + 점 + 공백 + 비공백문자
                rf'(?<!\d){num}\s*\.',             # 앞에 숫자 없음 + 숫자 + 점
                rf'\s{num}\s*\.\s*',               # 공백 + 숫자 + 점 + 공백
            ]
            
            # 블록 단위로 정확한 검색
            for block in text_dict.get("blocks", []):
                if found:
                    break
                    
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    if found:
                        break
                        
                    for span in line["spans"]:
                        text = span["text"]

                        # 컬럼 x좌표 필터: 들여쓰기 선택지 오인 방지
                        if col_x_filter:
                            sx0 = span["bbox"][0]
                            if sx0 < 200 and sx0 > col_x_filter["left_max"]:
                                continue
                            if sx0 >= 200 and sx0 > col_x_filter["right_max"]:
                                continue

                        # 정확한 패턴 매칭
                        for pattern in precise_patterns:
                            if re.search(pattern, text):
                                # 실제 문항인지 검증 (완화된 검증 적용)
                                if self._validate_question_text(text, num, strict=False):
                                    bbox = span["bbox"]
                                    positions[num] = fitz.Rect(bbox)
                                    found = True
                                    detection_method = "정확한 패턴"
                                    print(f"    문항 {num} 위치 발견 ({detection_method}): ({bbox[0]:.1f}, {bbox[1]:.1f})")
                                    break
                        
                        if found:
                            break
            
            # 2단계: 전체 페이지 텍스트에서 강력하게 찾기 (검증 포함)
            if not found:
                full_text = page.get_text()
                lines = full_text.split('\n')
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith(f"{num}."):
                        # 완화된 검증 적용
                        if self._validate_question_text(line, num, strict=False):
                            detection_method = "전체텍스트 검색"
                            print(f"    문항 {num} 텍스트 발견 ({detection_method}): {line[:50]}...")
                            
                            # 해당 텍스트의 위치를 search_for로 찾기
                            search_text = line[:20] if len(line) >= 20 else line  # 처음 20문자
                            rects = page.search_for(search_text)
                            if rects:
                                positions[num] = rects[0]
                                found = True
                                print(f"    문항 {num} 위치 발견 ({detection_method}): ({rects[0].x0:.1f}, {rects[0].y0:.1f})")
                                break
                        else:
                            print(f"    문항 {num} 텍스트 검증 실패: {line[:50]}...")
            
            # 3단계: 확장된 단순 패턴으로 시도
            if not found:
                simple_patterns = [f"{num}.", f" {num} .", f"{num}　", f"{num} .", f" {num}.", f"\t{num}.", f"{num}.\t"]
                for pattern in simple_patterns:
                    rects = page.search_for(pattern)
                    if rects:
                        # 각 매치를 검증해서 가장 적절한 것 선택
                        best_rect = None
                        for rect in rects:
                            expanded = fitz.Rect(rect.x0-10, rect.y0-5, 
                                               rect.x1+100, rect.y1+20)
                            text_sample = page.get_text(clip=expanded)
                            
                            # 문항 번호로 시작하는지 확인
                            if text_sample.strip().startswith(f"{num}."):
                                # 완화된 검증 (숫자 데이터만 제외)
                                first_line = text_sample.strip().split('\n')[0]
                                after_dot = first_line.replace(f"{num}.", "").strip()
                                
                                # 순수 숫자만 제외 (소수점 숫자도 허용)
                                if not re.match(r'^\d+$', after_dot):
                                    best_rect = rect
                                    detection_method = "단순패턴"
                                    break
                                else:
                                    print(f"    fallback 검증 실패 (순수 숫자): {first_line}")
                        
                        if best_rect:
                            positions[num] = best_rect
                            found = True
                            print(f"    문항 {num} 위치 발견 ({detection_method}): ({best_rect.x0:.1f}, {best_rect.y0:.1f})")
                            break
            
            # 4단계: 위치 추정 기반 검색 (새로운 단계)
            if not found:
                estimated_position = self._estimate_question_position(page, num, positions)
                if estimated_position:
                    positions[num] = estimated_position
                    found = True
                    detection_method = "위치추정"
                    print(f"    문항 {num} 위치 발견 ({detection_method}): ({estimated_position.x0:.1f}, {estimated_position.y0:.1f})")
            
            if not found:
                print(f"    ⚠️ 문항 {num}: 위치 찾기 실패 - 수동 보정 필요")
        
        return positions
    
    def _estimate_question_position(self, page, target_num: int, existing_positions: Dict) -> fitz.Rect:
        """인접 문항 기반 위치 추정"""
        if not existing_positions:
            return None
            
        # 인접한 문항들 찾기
        adjacent_questions = []
        for num, rect in existing_positions.items():
            distance = abs(target_num - num)
            if distance <= 5:  # 5개 번호 이내
                adjacent_questions.append((num, rect, distance))
        
        if not adjacent_questions:
            return None
            
        # 가장 가까운 문항 기준으로 추정
        adjacent_questions.sort(key=lambda x: x[2])  # distance로 정렬
        closest_num, closest_rect, _ = adjacent_questions[0]
        
        # 문항 번호 차이에 따른 Y 오프셋 계산
        num_diff = target_num - closest_num
        estimated_y_offset = num_diff * 150  # 문항당 평균 150pt 간격
        
        # 추정 위치 계산
        estimated_x = closest_rect.x0
        estimated_y = closest_rect.y0 + estimated_y_offset
        
        # 페이지 경계 내로 제한
        page_height = page.rect.height
        if estimated_y < 50:
            estimated_y = 50
        elif estimated_y > page_height - 100:
            estimated_y = page_height - 100
            
        return fitz.Rect(estimated_x, estimated_y, estimated_x + 50, estimated_y + 20)
    
    def _validate_question_text(self, text: str, expected_num: int, strict: bool = True) -> bool:
        """문항 텍스트가 실제 문항인지 강화된 검증"""
        if not text:
            return False
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return False
        
        first_line = lines[0]
        
        # 1차: 정확한 문항 번호 패턴으로 시작하는지 확인
        question_start_pattern = rf'^{expected_num}\.\s*'
        if not re.match(question_start_pattern, first_line):
            return False
        
        # 2차: 숫자 데이터 패턴 제외 (13.404954 같은 소수점 숫자)
        number_after_dot = re.sub(rf'^{expected_num}\.', '', first_line).strip()
        if re.match(r'^\d+(\.\d+)*\s*$', number_after_dot):
            print(f"  ❌ 숫자 데이터 패턴 제외: {expected_num}.{number_after_dot}")
            return False
        
        # 3차: 너무 짧은 텍스트 제외 (완화모드에서는 더 관대하게)
        min_length = 3 if not strict else 5
        if len(number_after_dot) < min_length:
            return False
        
        # 4차: 문항다운 내용 검증 (완화모드에서는 더 관대하게)
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[A-Za-z]', text))
        
        # 완화모드에서는 기준을 낮춤
        min_korean = 5 if not strict else 10
        min_english = 10 if not strict else 20
        
        # 한글 문항
        if korean_chars >= min_korean:
            # 확장된 문항 키워드 리스트
            question_keywords = [
                '다음', '아래', '위의', '설명', '옳은', '틀린', '가장', '적절', '부적절', 
                '관련', '해당', '경우', '문제', '질문', '답', '선택', '보기', '항목',
                '무엇', '어떤', '어느', '누구', '언제', '어디서', '왜', '어떻게',
                '대해', '대한', '관하여', '관한', '있는', '없는', '맞는', '틀린',
                '옳지', '그르', '바른', '잘못', '올바른'
            ]
            if any(keyword in text for keyword in question_keywords):
                print(f"  ✅ 한글 문항 키워드 확인: {expected_num}번")
                return True
            elif korean_chars >= (15 if strict else 8):  # 완화모드에서는 8자 이상
                return True
        
        # 영문 문항
        elif english_chars >= min_english:
            return True
        
        # 5차: 잘못된 패턴들 제외 (완화모드에서는 일부만 적용)
        if strict:
            false_patterns = [
                r'\d{4}',      # 연도 (2021, 2022 등)
                r'페이지',      # 페이지 번호
                r'점수',       # 점수
                r'시간',       # 시간
                r'분',         # 분  
                r'^[A-Z]\d+$', # C001, C002 같은 코드
                r'^\d+$',      # 순수 숫자만
            ]
        else:
            # 완화모드에서는 명백히 잘못된 것만 제외
            false_patterns = [
                r'^[A-Z]\d+$', # C001, C002 같은 코드
                r'^\d+$',      # 순수 숫자만
            ]
        
        for pattern in false_patterns:
            if re.search(pattern, number_after_dot):
                print(f"  ❌ 잘못된 패턴 감지: {pattern} in {number_after_dot}")
                return False
        
        # 완화모드에서는 기본적으로 허용
        if not strict:
            return True
            
        return False
    
    def reorder_questions_by_global_sequence(self, all_questions: List[Tuple[int, any, str]]) -> List[Tuple[int, any, str]]:
        """전체 순서를 고려하여 문항 재정렬"""
        if not all_questions:
            return []
        
        # 문항 번호순으로 정렬하여 전체 순서 파악
        sorted_by_number = sorted(all_questions, key=lambda x: x[0])
        
        # 좌우 단락별로 분리
        left_questions = [(num, rect, col) for num, rect, col in sorted_by_number if col == "left"]
        right_questions = [(num, rect, col) for num, rect, col in sorted_by_number if col == "right"]
        
        # 각 단락에서 Y 좌표순으로 정렬
        left_questions.sort(key=lambda x: x[1].y0)
        right_questions.sort(key=lambda x: x[1].y0)
        
        # 문항 번호와 Y 좌표 순서가 일치하는지 검사
        reordered = []
        
        # 좌우 단락을 번갈아가며 순서대로 배치
        left_idx = 0
        right_idx = 0
        
        for target_num in range(1, 121):
            # 좌측에서 찾기
            found_left = None
            for i in range(left_idx, len(left_questions)):
                if left_questions[i][0] == target_num:
                    found_left = left_questions[i]
                    left_idx = i + 1
                    break
            
            # 우측에서 찾기
            found_right = None
            for i in range(right_idx, len(right_questions)):
                if right_questions[i][0] == target_num:
                    found_right = right_questions[i]
                    right_idx = i + 1
                    break
            
            # 찾은 문항 추가
            if found_left:
                reordered.append(found_left)
            elif found_right:
                reordered.append(found_right)
        
        return reordered
    
    def identify_misplaced_questions(self, page_questions: List[Tuple[int, any, str]]) -> List[int]:
        """잘못 배치된 문항 식별 (제거하지 않고 마킹만)"""
        misplaced = []
        
        if len(page_questions) < 3:
            return misplaced
        
        # 문항 번호순으로 정렬
        sorted_by_num = sorted(page_questions, key=lambda x: x[0])
        
        # 연속된 문항들 사이에 큰 간격이 있는지 확인
        for i in range(len(sorted_by_num) - 1):
            current_num = sorted_by_num[i][0]
            next_num = sorted_by_num[i + 1][0]
            
            # 문항 번호 간격이 5 이상이면 잘못 배치된 것으로 판단
            if next_num - current_num > 5:
                misplaced.append(next_num)
                print(f"잘못 배치된 문항 식별: {next_num} (이전 문항: {current_num})")
        
        return misplaced
    
    def verify_question_content(self, page, question_num: int, bbox: List[float]) -> bool:
        """바운딩 박스 영역의 실제 문항 내용 검증"""
        try:
            # 바운딩 박스 영역의 텍스트 추출
            rect = fitz.Rect(bbox)
            # 약간 확장하여 검사
            expanded_rect = fitz.Rect(bbox[0]-5, bbox[1]-5, bbox[2]+5, bbox[3]+5)
            text = page.get_text(clip=expanded_rect)
            
            # 문항 번호가 포함되어 있는지 확인
            patterns = [
                f"{question_num}.",
                f"{question_num} .",
                f" {question_num}.",
                f"문{question_num}",
                f"제{question_num}"
            ]
            
            for pattern in patterns:
                if pattern in text:
                    return True
            
            # 숫자가 아예 없으면 False
            if not any(char.isdigit() for char in text[:50]):
                return False
                
            return True
        except:
            return False

    def improve_question_boundaries(self, positions: Dict, left_col: Dict, right_col: Dict, page_height: float, expected_questions: List[int], page, adaptive_layout: Dict, year: int = 2024):
        """개선된 문항 경계 설정 - 연속성 기반 종료좌표 계산"""
        improved_questions = []
        
        if not positions:
            return improved_questions
        
        # 좌측/우측 단락별로 문항 분류
        left_questions = []
        right_questions = []
        
        center_x = (left_col["x2"] + right_col["x1"]) / 2
        
        for num, rect in positions.items():
            if rect.x0 < center_x:
                left_questions.append((num, rect))
            else:
                right_questions.append((num, rect))
        
        # Y 좌표 순으로 정렬
        left_questions.sort(key=lambda x: x[1].y0)
        right_questions.sort(key=lambda x: x[1].y0)
        
        # 연속성 기반 종료좌표 계산 시스템 적용
        improved_questions.extend(self._calculate_sequential_boundaries(left_questions, "left", left_col, page_height, year, page))
        improved_questions.extend(self._calculate_sequential_boundaries(right_questions, "right", right_col, page_height, year, page))
        
        # 페이지별 단락 내 Y좌표 추가 보정 시스템 적용
        print("  페이지별 단락 내 Y좌표 추가 보정 실행...")
        corrected_questions = self._apply_page_level_y_correction(improved_questions, page, page_height, year)
        
        return corrected_questions
    
    def _calculate_sequential_boundaries(self, questions: List[Tuple[int, any]], column_type: str, column_bounds: Dict, page_height: float, year: int, page) -> List[Dict]:
        """연속성 기반 문항 경계 계산"""
        if not questions:
            return []
            
        results = []
        standard_width = self.get_standard_width(year, column_type)
        standard_start = self.get_standard_position(year, column_type)
        
        print(f"  {column_type} 컬럼 연속성 기반 경계 계산 ({len(questions)}개 문항)")
        
        for i, (num, rect) in enumerate(questions):
            # X 좌표는 표준값 사용
            x1 = standard_start
            x2 = x1 + standard_width
            
            # Y 시작점은 감지된 위치 사용 (약간의 여백 포함)
            y1 = max(rect.y0 - 5, column_bounds["y1"])
            
            # Y 종료점은 연속성 기반 계산
            y2 = self._calculate_end_position(questions, i, column_bounds, page_height)
            
            # 최종 검증 및 보정
            y2 = self._validate_and_adjust_end_position(page, num, x1, y1, x2, y2, page_height)
            
            bbox = [x1, y1, x2, y2]
            
            print(f"    문항 {num}: 시작 y={y1:.1f}, 종료 y={y2:.1f}, 높이={y2-y1:.1f}pt")
            
            # 실제 문항 내용 검증
            if self.verify_question_content(page, num, bbox):
                results.append({
                    "question_num": num,
                    "subject": self.get_subject_by_number(num),
                    "bbox": bbox,
                    "column": column_type,
                    "verified": True
                })
            else:
                print(f"    경고: {num}번 문항 내용 검증 실패, 기본 크기 적용")
                # 기본 크기로 대체
                fallback_bbox = [x1, y1, x2, min(y1 + 150, page_height - 50)]
                results.append({
                    "question_num": num,
                    "subject": self.get_subject_by_number(num),
                    "bbox": fallback_bbox,
                    "column": column_type,
                    "verified": False
                })
        
        return results
    
    def _calculate_end_position(self, questions: List[Tuple[int, any]], current_index: int, column_bounds: Dict, page_height: float) -> float:
        """연속성 기반 종료 Y 좌표 계산 - 더 정교한 다음 문항 위치 기반"""
        current_num, current_rect = questions[current_index]
        
        # 마지막 문항인 경우: 페이지 하단까지
        if current_index == len(questions) - 1:
            return min(page_height - 30, column_bounds["y2"])
        
        # 다음 문항이 있는 경우: 다음 문항 시작점에서 여백을 뺀 지점
        next_num, next_rect = questions[current_index + 1]
        
        # 다음 문항까지의 거리 계산
        gap_to_next = next_rect.y0 - current_rect.y0
        
        # 연속된 문항 번호인지 확인
        is_consecutive = (next_num == current_num + 1)
        
        if is_consecutive:
            # 연속된 문항인 경우 더 정교한 계산
            if gap_to_next > 80:  # 80pt 이상 간격 (충분한 공간)
                return next_rect.y0 - 15  # 15pt 여백으로 다음 문항 침범 방지
            elif gap_to_next > 40:  # 40-80pt 간격 (중간 공간)
                return next_rect.y0 - 8   # 8pt 여백
            else:
                # 매우 가까운 간격인 경우 중간지점보다 조금 앞쪽
                return current_rect.y0 + (gap_to_next * 0.65)
        else:
            # 비연속 문항인 경우 (페이지 넘김 등)
            if gap_to_next > 100:  # 100pt 이상 간격
                return next_rect.y0 - 20  # 20pt 여백
            else:
                return current_rect.y0 + (gap_to_next * 0.75)
    
    def _validate_and_adjust_end_position(self, page, question_num: int, x1: float, y1: float, x2: float, y2: float, page_height: float) -> float:
        """종료 위치 검증 및 보정"""
        # 최소 높이 보장 (100pt)
        min_height = 100
        if y2 - y1 < min_height:
            y2 = y1 + min_height
        
        # 페이지 경계 검사
        if y2 > page_height - 30:
            y2 = page_height - 30
        
        # 실제 텍스트 내용이 y2를 넘어가는지 확인
        extended_y2 = self._check_content_extends_beyond(page, question_num, x1, y1, x2, y2)
        if extended_y2 > y2:
            # 내용이 더 길면 확장 (단, 페이지 경계 내에서)
            y2 = min(extended_y2, page_height - 30)
        
        return y2
    
    def _check_content_extends_beyond(self, page, question_num: int, x1: float, y1: float, x2: float, y2: float) -> float:
        """문항 내용이 현재 경계를 넘어가는지 확인 - 다음 문항 침범 방지 강화"""
        try:
            # 현재 bbox에서 아래로 확장된 영역의 텍스트 추출 (더 제한적으로)
            extended_rect = fitz.Rect(x1 - 5, y1 - 5, x2 + 5, y2 + 150)  # 아래로 150pt만 확장 (줄임)
            text = page.get_text(clip=extended_rect)
            
            if not text:
                return y2
            
            lines = text.split('\n')
            question_started = False
            last_content_y = y2
            next_question_start_y = None
            
            # 먼저 다음 문항의 시작 위치를 찾기
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 다음 문항 번호 패턴 찾기
                next_question_match = re.match(r'^\s*(\d+)\s*\.', line)
                if next_question_match:
                    next_num = int(next_question_match.group(1))
                    if next_num > question_num:
                        # 다음 문항의 실제 위치 찾기
                        search_results = page.search_for(line[:15] if len(line) > 15 else line)
                        if search_results:
                            for rect in search_results:
                                if x1 <= rect.x0 <= x2 and rect.y0 > y1:
                                    next_question_start_y = rect.y0
                                    break
                        break
            
            # 다음 문항이 발견되면 그 위치까지만 허용
            if next_question_start_y:
                max_allowed_y = next_question_start_y - 10  # 다음 문항에서 10pt 여백
                if last_content_y > max_allowed_y:
                    print(f"      문항 {question_num}: 다음 문항 침범 방지로 y2를 {last_content_y:.1f} -> {max_allowed_y:.1f}로 조정")
                    return max_allowed_y
            
            # 현재 문항의 실제 내용 끝 찾기
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 현재 문항 시작 확인
                if re.match(rf'^\s*{question_num}\s*\.', line):
                    question_started = True
                    continue
                
                # 다음 문항 발견시 중단
                if question_started and re.match(r'^\s*(\d+)\s*\.', line):
                    next_num = int(re.match(r'^\s*(\d+)\s*\.', line).group(1))
                    if next_num > question_num:
                        break
                
                # 문항 내용 중이면 위치 추적
                if question_started and len(line) > 3:  # 의미있는 텍스트만
                    search_results = page.search_for(line[:20] if len(line) > 20 else line)
                    if search_results:
                        for rect in search_results:
                            if x1 <= rect.x0 <= x2 and rect.y0 > y1:
                                last_content_y = max(last_content_y, rect.y1)
            
            return last_content_y
            
        except Exception as e:
            print(f"      내용 확장 검사 오류: {e}")
            return y2
    
    def _apply_page_level_y_correction(self, questions: List[Dict], page, page_height: float, year: int = 2024) -> List[Dict]:
        """페이지별 단락 내 Y좌표 추가 보정 시스템 - 다음 문항 크롭 방지 강화"""
        if not questions:
            return questions
            
        print(f"    페이지별 Y좌표 보정 적용: {len(questions)}개 문항")
        corrected_questions = []
        
        # 컬럼별로 분리하여 처리
        left_questions = [q for q in questions if q["column"] == "left"]
        right_questions = [q for q in questions if q["column"] == "right"]
        
        # 각 컬럼별로 순차적 보정 적용
        corrected_questions.extend(self._correct_column_y_coordinates(left_questions, page, page_height, "left", year))
        corrected_questions.extend(self._correct_column_y_coordinates(right_questions, page, page_height, "right", year))
        
        return corrected_questions
    
    def _correct_column_y_coordinates(self, column_questions: List[Dict], page, page_height: float, column_type: str, year: int = 2024) -> List[Dict]:
        """단락 내 Y좌표 순차적 보정"""
        if not column_questions:
            return []
            
        # 문항 번호 순으로 정렬
        column_questions.sort(key=lambda q: q["question_num"])
        
        # 1단계: 모든 문항에 2021년 특수 보정 먼저 적용
        for question in column_questions:
            question_num = question["question_num"]
            x1, y1, x2, y2 = question["bbox"]
            y1, y2 = self._apply_2021_special_corrections(question_num, year, x1, y1, x2, y2)
            question["bbox"] = [x1, y1, x2, y2]
        
        # 2단계: 충돌 검사 및 보정
        corrected = []
        print(f"      {column_type} 컬럼 Y좌표 보정: {len(column_questions)}개 문항")
        
        for i, question in enumerate(column_questions):
            original_bbox = question["bbox"].copy()
            question_num = question["question_num"]
            
            # 현재 bbox (이미 2021년 특수 보정 적용됨)
            x1, y1, x2, y2 = original_bbox
            
            # 다음 문항과의 충돌 검사 및 보정
            if i < len(column_questions) - 1:
                next_question = column_questions[i + 1]
                next_y1 = next_question["bbox"][1]  # 다음 문항도 이미 특수 보정 적용됨
                
                # 현재 문항이 다음 문항 영역을 침범하는지 확인
                if y2 > next_y1:
                    # 침범하는 경우 조정
                    safe_margin = 10  # 안전 여백
                    corrected_y2 = next_y1 - safe_margin
                    
                    # 최소 높이 보장 (80pt)
                    min_height = 80
                    if corrected_y2 - y1 < min_height:
                        corrected_y2 = y1 + min_height
                        # 이 경우 다음 문항과 겹칠 수 있으므로 warning
                        print(f"        경고: 문항 {question_num} 최소 높이 보장으로 인한 잠재적 겹침")
                    
                    # 실제 내용 범위 재검증
                    validated_y2 = self._validate_content_boundary(page, question_num, x1, y1, x2, corrected_y2, next_y1)
                    
                    if validated_y2 != y2:
                        print(f"        문항 {question_num}: Y종료점 보정 {y2:.1f} -> {validated_y2:.1f} (다음문항침범방지)")
                        y2 = validated_y2
            
            # 페이지 경계 최종 검증
            if y2 > page_height - 20:
                y2 = page_height - 20
                print(f"        문항 {question_num}: 페이지 경계 조정 -> {y2:.1f}")
            
            # 보정된 bbox로 업데이트
            corrected_question = question.copy()
            corrected_question["bbox"] = [x1, y1, x2, y2]
            corrected.append(corrected_question)
        
        return corrected
    
    def _validate_content_boundary(self, page, question_num: int, x1: float, y1: float, x2: float, proposed_y2: float, next_question_y1: float) -> float:
        """내용 경계 검증 - 실제 문항 내용이 제안된 경계 내에 있는지 확인"""
        try:
            # 제안된 경계 영역의 텍스트 추출
            rect = fitz.Rect(x1, y1, x2, proposed_y2)
            text = page.get_text(clip=rect)
            
            if not text.strip():
                return proposed_y2
            
            # 현재 문항의 실제 내용이 모두 포함되어 있는지 확인
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # 문항이 시작되었는지 확인
            question_started = False
            for line in lines:
                if re.match(rf'^\s*{question_num}\s*\.', line):
                    question_started = True
                    break
            
            if not question_started:
                # 문항 시작이 없으면 위쪽으로 확장 필요
                expanded_rect = fitz.Rect(x1, y1 - 20, x2, proposed_y2)
                expanded_text = page.get_text(clip=expanded_rect)
                if f"{question_num}." in expanded_text:
                    return proposed_y2
            
            # 다음 문항이 현재 영역에 포함되어 있는지 확인
            for line in lines:
                next_question_match = re.match(r'^\s*(\d+)\s*\.', line)
                if next_question_match:
                    found_num = int(next_question_match.group(1))
                    if found_num > question_num:
                        # 다음 문항이 포함되어 있으면 더 줄여야 함
                        search_results = page.search_for(line[:15])
                        if search_results:
                            for rect in search_results:
                                if x1 <= rect.x0 <= x2 and y1 <= rect.y0 <= proposed_y2:
                                    adjusted_y2 = rect.y0 - 5
                                    print(f"          문항 {question_num}: 다음문항 발견으로 추가 조정 -> {adjusted_y2:.1f}")
                                    return max(adjusted_y2, y1 + 60)  # 최소 높이 보장
            
            return proposed_y2
            
        except Exception as e:
            print(f"          문항 {question_num} 내용 경계 검증 오류: {e}")
            return proposed_y2
    
    def _apply_2021_special_corrections(self, question_num: int, year: int, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
        """2021년 특정 문항들에 대한 예외 처리 보정"""
        if year != 2021:
            return y1, y2
            
        if question_num == 1:
            # 1번 문항: 끝부분이 짤림 - 2번 문항 시작 전까지 확장
            corrected_y2 = 337.28  # 2번 문항 시작(342.28) - 5pt 여백
            print(f"        문항 1: 2021년 특수 보정 - 종료점 {y2:.1f} -> {corrected_y2:.1f}")
            return y1, corrected_y2
            
        elif question_num == 3:
            # 3번 문항: 끝부분이 짤림 - 4번 문항 시작 전까지 확장
            corrected_y2 = 635.0  # 4번 문항 시작(640.0) - 5pt 여백
            print(f"        문항 3: 2021년 특수 보정 - 종료점 {y2:.1f} -> {corrected_y2:.1f}")
            return y1, corrected_y2
            
        elif question_num == 4:
            # 4번 문항: 시작좌표가 잘못됨 - 3번 문항 종료 후로 조정
            corrected_y1 = 640.0  # 3번 문항 종료(635.0) + 5pt 여백
            corrected_y2 = 981.0   # 페이지 끝까지 확장
            print(f"        문항 4: 2021년 특수 보정 - 시작점 {y1:.1f} -> {corrected_y1:.1f}, 종료점 {y2:.1f} -> {corrected_y2:.1f}")
            return corrected_y1, corrected_y2
        
        return y1, y2
    
    def interpolate_missing_questions(self, metadata: Dict) -> Dict:
        """순차적 문항 배치 규칙을 활용한 누락 문항 보정"""
        print("순차적 문항 배치 기반 누락 문항 보정 시작...")
        
        # 현재 발견된 모든 문항들 수집
        found_questions = {}
        for page in metadata["pages"]:
            for q in page["questions"]:
                found_questions[q["question_num"]] = {
                    "page_num": page["page_num"],
                    "bbox": q["bbox"],
                    "column": q["column"],
                    "subject": q["subject"]
                }
        
        # 누락된 문항 식별
        all_questions = set(range(1, 121))
        found_numbers = set(found_questions.keys())
        missing_numbers = sorted(all_questions - found_numbers)
        
        if not missing_numbers:
            print("누락된 문항이 없습니다.")
            return metadata
            
        print(f"누락된 문항: {missing_numbers} (총 {len(missing_numbers)}개)")
        
        # 각 누락 문항에 대해 위치 추정
        interpolated_count = 0
        for missing_num in missing_numbers:
            interpolated = self._interpolate_single_question(missing_num, found_questions, metadata)
            if interpolated:
                interpolated_count += 1
        
        print(f"보정 완료: {interpolated_count}개 문항 추가")
        return metadata
    
    def _interpolate_single_question(self, missing_num: int, found_questions: Dict, metadata: Dict) -> bool:
        """단일 누락 문항의 위치 추정 및 추가"""
        
        # 인접한 문항들 찾기
        prev_num = missing_num - 1
        next_num = missing_num + 1
        
        prev_q = found_questions.get(prev_num)
        next_q = found_questions.get(next_num)
        
        # Case 1: 앞뒤 문항이 모두 있는 경우 (선형 보간)
        if prev_q and next_q and prev_q["page_num"] == next_q["page_num"]:
            bbox = self._linear_interpolate_bbox(prev_q["bbox"], next_q["bbox"])
            page_num = prev_q["page_num"]
            column = prev_q["column"]  # 일반적으로 같은 컬럼에 있을 가능성이 높음
            
        # Case 2: 이전 문항만 있는 경우 (다음 위치 추정)
        elif prev_q:
            bbox = self._estimate_next_bbox(prev_q["bbox"], prev_q["column"])
            page_num = prev_q["page_num"]
            column = prev_q["column"]
            
        # Case 3: 다음 문항만 있는 경우 (이전 위치 추정)
        elif next_q:
            bbox = self._estimate_prev_bbox(next_q["bbox"], next_q["column"])
            page_num = next_q["page_num"]
            column = next_q["column"]
            
        # Case 4: 인접 문항이 없는 경우 (페이지별 예상 위치)
        else:
            estimated = self._estimate_by_sequence_rule(missing_num, found_questions, metadata)
            if not estimated:
                return False
            bbox, page_num, column = estimated
        
        # 과목 결정
        subject = self.get_subject_by_number(missing_num)
        
        # 새 문항 생성
        new_question = {
            "question_num": missing_num,
            "subject": subject,
            "bbox": bbox,
            "column": column
        }
        
        # 해당 페이지에 추가
        page_found = False
        for page in metadata["pages"]:
            if page["page_num"] == page_num:
                page["questions"].append(new_question)
                page["questions"].sort(key=lambda x: x["question_num"])
                page_found = True
                break
        
        # 페이지가 없으면 새로 생성
        if not page_found:
            new_page = {
                "page_num": page_num,
                "questions": [new_question]
            }
            metadata["pages"].append(new_page)
            metadata["pages"].sort(key=lambda x: x["page_num"])
        
        print(f"  문항 {missing_num} 보정: 페이지 {page_num}, {column} 컬럼")
        return True
    
    def _linear_interpolate_bbox(self, bbox1: List[float], bbox2: List[float]) -> List[float]:
        """두 바운딩 박스 사이의 선형 보간"""
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2
        
        # 중간 위치 계산
        mid_x1 = (x1 + x3) / 2
        mid_y1 = (y1 + y3) / 2
        mid_x2 = (x2 + x4) / 2
        mid_y2 = (y2 + y4) / 2
        
        return [mid_x1, mid_y1, mid_x2, mid_y2]
    
    def _estimate_next_bbox(self, prev_bbox: List[float], column: str) -> List[float]:
        """이전 문항 기준으로 다음 문항 위치 추정"""
        x1, y1, x2, y2 = prev_bbox
        
        # 문항 간격 추정 (평균적으로 150-200 포인트)
        avg_question_height = 180
        
        # 다음 위치 계산
        next_y1 = y2 + 30  # 문항 간 여백
        next_y2 = next_y1 + avg_question_height
        
        return [x1, next_y1, x2, next_y2]
    
    def _estimate_prev_bbox(self, next_bbox: List[float], column: str) -> List[float]:
        """다음 문항 기준으로 이전 문항 위치 추정"""
        x1, y1, x2, y2 = next_bbox
        
        # 문항 간격 추정
        avg_question_height = 180
        
        # 이전 위치 계산
        prev_y2 = y1 - 30  # 문항 간 여백
        prev_y1 = prev_y2 - avg_question_height
        
        return [x1, prev_y1, x2, prev_y2]
    
    def _estimate_by_sequence_rule(self, missing_num: int, found_questions: Dict, metadata: Dict):
        """순차적 배치 규칙으로 위치 추정"""
        
        # 해당 문항이 위치할 예상 페이지 계산
        expected_page = self._determine_correct_page(missing_num, metadata)
        
        # 같은 페이지의 다른 문항들 찾기
        same_page_questions = []
        for num, info in found_questions.items():
            if info["page_num"] == expected_page:
                same_page_questions.append((num, info))
        
        if not same_page_questions:
            return None
            
        # 페이지 내에서 순서에 따른 위치 추정
        same_page_questions.sort(key=lambda x: x[0])  # 문항 번호순 정렬
        
        # 좌측/우측 컬럼 결정 (홀수는 대체로 좌측부터 시작)
        column = "left" if missing_num % 2 == 1 else "right"
        
        # 해당 컬럼의 첫 번째 문항 기준으로 위치 추정
        for num, info in same_page_questions:
            if info["column"] == column:
                base_bbox = info["bbox"]
                # 문항 번호 차이에 따른 Y 오프셋 계산
                offset_factor = (missing_num - num) * 180
                
                bbox = [
                    base_bbox[0],
                    base_bbox[1] + offset_factor,
                    base_bbox[2], 
                    base_bbox[3] + offset_factor
                ]
                return bbox, expected_page, column
                
        return None
    
    def post_process_question_order(self, metadata: Dict) -> Dict:
        # 기존 후처리 실행
        metadata = self.post_process_question_order_original(metadata)
        
        # 페이지별 연속성 기반 정확한 보정
        metadata = self.accurate_page_mapping(metadata)
        
        return metadata
    
    def accurate_page_mapping(self, metadata: Dict) -> Dict:
        """실제 PDF 구조 기반 정확한 페이지 매핑"""
        print("실제 PDF 구조 기반 정확한 매핑 분석 중...")
        
        # 1. 현재 페이지별 실제 발견된 문항 범위 분석
        page_analysis = {}
        for page in metadata["pages"]:
            page_num = page["page_num"]
            questions = [q["question_num"] for q in page["questions"]]
            if questions:
                questions.sort()
                page_analysis[page_num] = {
                    "found_questions": set(questions),
                    "range": (min(questions), max(questions)),
                    "count": len(questions),
                    "questions_data": page["questions"]
                }
                print(f"페이지 {page_num}: 발견된 문항 {min(questions)}-{max(questions)} (총 {len(questions)}개)")
        
        # 2. 전체 연속성 분석
        all_found = set()
        for page_info in page_analysis.values():
            all_found.update(page_info["found_questions"])
        
        missing_questions = set(range(1, 121)) - all_found
        print(f"전체 누락 문항: {sorted(missing_questions)} (총 {len(missing_questions)}개)")
        
        # 3. 페이지 간 연속성 확인 및 누락 문항 정확한 위치 결정
        for missing_num in sorted(missing_questions):
            correct_page = self._find_correct_page_for_missing(missing_num, page_analysis)
            if correct_page:
                print(f"문항 {missing_num}: 페이지 {correct_page}에 배치 필요")
                self._add_missing_question_to_page(missing_num, correct_page, metadata, page_analysis)
        
        # 4. 최종 정리 및 재구성
        return self._finalize_page_structure(metadata)
    
    def _find_correct_page_for_missing(self, missing_num: int, page_analysis: Dict) -> int:
        """누락 문항의 정확한 페이지 결정"""
        # 연속된 페이지들 사이에서 누락 문항의 위치 찾기
        sorted_pages = sorted(page_analysis.keys())
        
        for i, page_num in enumerate(sorted_pages):
            page_range = page_analysis[page_num]["range"]
            min_q, max_q = page_range
            
            # Case 1: 문항이 현재 페이지 범위 내에 있어야 함
            if min_q <= missing_num <= max_q:
                return page_num
            
            # Case 2: 현재 페이지와 다음 페이지 사이의 빈 구간에 있음
            if i < len(sorted_pages) - 1:
                next_page = sorted_pages[i + 1]
                next_min = page_analysis[next_page]["range"][0]
                
                # 현재 페이지 다음, 다음 페이지 이전에 위치
                if max_q < missing_num < next_min:
                    # 더 가까운 페이지 선택
                    if missing_num - max_q <= next_min - missing_num:
                        return page_num  # 현재 페이지에 추가
                    else:
                        return next_page  # 다음 페이지에 추가
            
            # Case 3: 마지막 페이지 이후
            elif missing_num > max_q and i == len(sorted_pages) - 1:
                return page_num
        
        # Case 4: 첫 페이지 이전
        if sorted_pages and missing_num < page_analysis[sorted_pages[0]]["range"][0]:
            return sorted_pages[0]
        
        return None
    
    def _add_missing_question_to_page(self, missing_num: int, page_num: int, metadata: Dict, page_analysis: Dict):
        """누락 문항을 정확한 페이지에 추가 - 실제 PDF 구조 기반 정확한 좌표 계산"""
        # 해당 페이지의 기존 문항들 참고해서 위치와 컬럼 결정
        page_questions = page_analysis[page_num]["questions_data"]
        
        # 문항 번호 순서에 따라 컬럼 결정 (기존 패턴 분석)
        left_questions = [q for q in page_questions if q["column"] == "left"]
        right_questions = [q for q in page_questions if q["column"] == "right"]
        
        # 홀수/짝수 또는 기존 패턴에 따라 컬럼 결정
        if left_questions and right_questions:
            left_nums = [q["question_num"] for q in left_questions]
            right_nums = [q["question_num"] for q in right_questions]
            
            # 가장 가까운 문항 찾기
            closest_left_diff = min([abs(missing_num - num) for num in left_nums]) if left_nums else float('inf')
            closest_right_diff = min([abs(missing_num - num) for num in right_nums]) if right_nums else float('inf')
            
            target_column = "left" if closest_left_diff <= closest_right_diff else "right"
        else:
            target_column = "left" if len(left_questions) <= len(right_questions) else "right"
        
        # 위치 추정 (인접 문항 기반)
        adjacent_questions = [q for q in page_questions if q["column"] == target_column]
        
        if adjacent_questions:
            adjacent_questions.sort(key=lambda x: x["question_num"])
            
            # 적절한 위치 찾기
            insert_index = 0
            for i, q in enumerate(adjacent_questions):
                if q["question_num"] > missing_num:
                    break
                insert_index = i + 1
            
            # 실제 PDF 구조 기반 정확한 위치 계산
            year = metadata.get("year", 2024)
            standard_x = self.get_standard_position(year, target_column)
            standard_width = self.get_standard_width(year, target_column)
            
            # 위치 계산
            if insert_index == 0 and adjacent_questions:
                # 맨 앞에 삽입 - 첫 번째 문항 위로
                base_bbox = adjacent_questions[0]["bbox"]
                estimated_y = base_bbox[1] - 180  # 적절한 간격
                estimated_bbox = [standard_x, estimated_y, standard_x + standard_width, estimated_y + 150]
            elif insert_index >= len(adjacent_questions) and adjacent_questions:
                # 맨 뒤에 삽입 - 마지막 문항 아래로
                base_bbox = adjacent_questions[-1]["bbox"]
                estimated_y = base_bbox[3] + 30  # 적절한 간격
                estimated_bbox = [standard_x, estimated_y, standard_x + standard_width, estimated_y + 150]
            elif insert_index > 0 and insert_index < len(adjacent_questions):
                # 중간에 삽입 (선형 보간)
                prev_bbox = adjacent_questions[insert_index - 1]["bbox"]
                next_bbox = adjacent_questions[insert_index]["bbox"]
                estimated_y = (prev_bbox[3] + next_bbox[1]) / 2  # 두 문항 사이 중간
                estimated_bbox = [standard_x, estimated_y, standard_x + standard_width, estimated_y + 150]
            else:
                # 기본 위치 - 표준 좌표 사용
                estimated_y = 100
                estimated_bbox = [standard_x, estimated_y, standard_x + standard_width, estimated_y + 150]
        else:
            # 기본 위치 - 표준 좌표 사용
            year = metadata.get("year", 2024)
            standard_x = self.get_standard_position(year, target_column)
            standard_width = self.get_standard_width(year, target_column)
            estimated_y = 100
            estimated_bbox = [standard_x, estimated_y, standard_x + standard_width, estimated_y + 150]
        
        # 페이지 경계 검증 및 보정
        estimated_bbox = self._validate_and_fix_bbox(estimated_bbox, year)
        
        # 새 문항 생성 - 정확한 페이지 정보와 함께
        new_question = {
            "question_num": missing_num,
            "subject": self.get_subject_by_number(missing_num),
            "bbox": estimated_bbox,
            "column": target_column,
            "corrected": True,  # 후보정된 문항임을 표시
            "corrected_to_page": page_num  # 보정된 대상 페이지
        }
        
        # 해당 페이지에 추가
        for page in metadata["pages"]:
            if page["page_num"] == page_num:
                page["questions"].append(new_question)
                break
    
    def _validate_and_fix_bbox(self, bbox: List[float], year: int) -> List[float]:
        """페이지 경계 검증 및 좌표 보정"""
        x1, y1, x2, y2 = bbox
        
        # 연도별 페이지 크기 정의
        page_bounds = {
            2021: {"min_y": 50, "max_y": 800, "min_height": 100, "max_height": 500},
            2022: {"min_y": 50, "max_y": 800, "min_height": 100, "max_height": 500}, 
            2023: {"min_y": 50, "max_y": 800, "min_height": 100, "max_height": 500},
            2024: {"min_y": 50, "max_y": 800, "min_height": 100, "max_height": 400},
            2026: {"min_y": 50, "max_y": 800, "min_height": 100, "max_height": 400},
        }
        
        bounds = page_bounds.get(year, page_bounds[2024])
        min_y, max_y = bounds["min_y"], bounds["max_y"]
        min_height, max_height = bounds["min_height"], bounds["max_height"]
        
        # 현재 높이 계산
        current_height = y2 - y1
        
        # 높이가 너무 작거나 큰 경우 조정
        if current_height < min_height:
            target_height = min_height
        elif current_height > max_height:
            target_height = max_height
        else:
            target_height = current_height
        
        # y좌표 보정
        if y1 < min_y:
            # 너무 위쪽인 경우
            print(f"    좌표 보정: y1={y1:.1f} → {min_y} (최소값 적용)")
            y1 = min_y
            y2 = y1 + target_height
        elif y2 > max_y:
            # 너무 아래쪽인 경우  
            print(f"    좌표 보정: y2={y2:.1f} → {max_y} (최대값 적용)")
            y2 = max_y
            y1 = y2 - target_height
            # y1이 여전히 음수인 경우 추가 조정
            if y1 < min_y:
                y1 = min_y
                y2 = y1 + target_height
        elif y1 > max_y - target_height:
            # 시작점이 너무 아래에 있어서 충분한 높이를 확보할 수 없는 경우
            print(f"    좌표 보정: y1={y1:.1f} → {max_y - target_height} (공간 확보)")
            y1 = max_y - target_height
            y2 = y1 + target_height
        
        # 최종 검증
        if y1 < 0:
            print(f"    최종 보정: y1={y1:.1f} → 0 (음수 제거)")
            y1 = 0
            y2 = target_height
        
        return [x1, y1, x2, y2]
    
    def _finalize_page_structure(self, metadata: Dict) -> Dict:
        """최종 페이지 구조 정리"""
        # 각 페이지 내 문항들을 번호순으로 정렬
        for page in metadata["pages"]:
            page["questions"].sort(key=lambda x: x["question_num"])
        
        # 전체 통계
        all_questions = set()
        for page in metadata["pages"]:
            for q in page["questions"]:
                all_questions.add(q["question_num"])
        
        missing = set(range(1, 121)) - all_questions
        
        print(f"최종 결과: {len(all_questions)}개/120개 문항")
        if missing:
            print(f"최종 누락: {sorted(missing)}")
        else:
            print("✅ 모든 문항 완성!")
        
        # 최종 페이지별 분포 출력
        print("\n최종 페이지별 분포:")
        for page in metadata["pages"]:
            questions = sorted([q["question_num"] for q in page["questions"]])
            if questions:
                if len(questions) == 1:
                    print(f"페이지 {page['page_num']:2d}: 문항 {questions[0]} (1개)")
                else:
                    print(f"페이지 {page['page_num']:2d}: 문항 {questions[0]}-{questions[-1]} (총 {len(questions)}개)")
        
        return metadata
    
    def balance_pages(self, metadata: Dict) -> Dict:
        """페이지별 문항 분포 균형 조정"""
        print("페이지별 문항 분포 균형 조정 중...")
        
        # 현재 페이지별 분포 확인
        page_distribution = {}
        for page in metadata["pages"]:
            page_num = page["page_num"]
            questions = page["questions"]
            page_distribution[page_num] = {
                "questions": questions,
                "count": len(questions),
                "range": f"{min(q['question_num'] for q in questions)}-{max(q['question_num'] for q in questions)}" if questions else "empty"
            }
        
        # 과도하게 많은 문항이 있는 페이지 찾기 (8개 이상)
        overloaded_pages = []
        for page_num, info in page_distribution.items():
            if info["count"] > 7:  # 7개 이상을 과부하로 간주 (더 엄격한 기준)
                overloaded_pages.append(page_num)
                print(f"과부하 페이지 {page_num}: {info['count']}개 문항 ({info['range']})")
        
        if not overloaded_pages:
            print("페이지별 분포가 균형적입니다.")
            return metadata
        
        # 과부하된 페이지의 문항들을 적절히 재분산
        for overloaded_page in overloaded_pages:
            page_info = page_distribution[overloaded_page]
            questions = page_info["questions"]
            
            if len(questions) <= 7:
                continue  # 이미 조정됨
            
            # 문항 번호순 정렬
            questions.sort(key=lambda x: x["question_num"])
            
            # 후반부 문항들을 다음 페이지로 이동
            excess_count = len(questions) - 6  # 6개까지만 유지 (더 엄격)
            questions_to_move = questions[-excess_count:]
            remaining_questions = questions[:-excess_count]
            
            print(f"페이지 {overloaded_page}: {len(questions_to_move)}개 문항을 다음 페이지로 이동")
            
            # 현재 페이지에는 앞쪽 문항들만 유지
            for page in metadata["pages"]:
                if page["page_num"] == overloaded_page:
                    page["questions"] = remaining_questions
                    break
            
            # 이동할 문항들을 다음 페이지에 추가
            next_page_num = overloaded_page + 1
            next_page_found = False
            
            for page in metadata["pages"]:
                if page["page_num"] == next_page_num:
                    # 기존 문항들과 합쳐서 정렬
                    combined_questions = page["questions"] + questions_to_move
                    combined_questions.sort(key=lambda x: x["question_num"])
                    page["questions"] = combined_questions
                    next_page_found = True
                    break
            
            # 다음 페이지가 없으면 새로 생성
            if not next_page_found:
                new_page = {
                    "page_num": next_page_num,
                    "questions": questions_to_move
                }
                metadata["pages"].append(new_page)
                metadata["pages"].sort(key=lambda x: x["page_num"])
        
        # 재분산 후 통계
        print("재분산 후 페이지별 분포:")
        for page in metadata["pages"]:
            questions = page["questions"]
            if questions:
                q_range = f"{min(q['question_num'] for q in questions)}-{max(q['question_num'] for q in questions)}"
                print(f"페이지 {page['page_num']}: {len(questions)}개 문항 ({q_range})")
        
        return metadata
    
    def post_process_question_order_original(self, metadata: Dict) -> Dict:
        """기존 문항 순서 후처리"""
        print("기존 문항 순서 후처리 시작...")
        
        # 모든 문항을 수집
        all_questions = []
        for page_data in metadata["pages"]:
            for q in page_data["questions"]:
                all_questions.append({
                    "question_num": q["question_num"],
                    "subject": q["subject"],
                    "bbox": q["bbox"],
                    "column": q["column"],
                    "original_page": page_data["page_num"],
                    "y_center": (q["bbox"][1] + q["bbox"][3]) / 2
                })
        
        # 문항 번호 유효성 검사 및 정리
        valid_questions = []
        invalid_questions = []
        
        for q in all_questions:
            if 1 <= q["question_num"] <= 120:
                valid_questions.append(q)
            else:
                invalid_questions.append(q)
                
        if invalid_questions:
            print(f"유효하지 않은 문항 번호 제거: {[q['question_num'] for q in invalid_questions]}")
        
        # 중복 제거 (같은 번호의 문항이 여러 개 있을 경우 첫 번째만 유지)
        seen = set()
        unique_questions = []
        duplicates = []
        
        for q in sorted(valid_questions, key=lambda x: (x["question_num"], x["original_page"], x["y_center"])):
            if q["question_num"] in seen:
                duplicates.append(q["question_num"])
            else:
                seen.add(q["question_num"])
                unique_questions.append(q)
        
        if duplicates:
            print(f"중복 문항 제거: {duplicates}")
        
        # 누락된 문항 확인
        found_numbers = {q["question_num"] for q in unique_questions}
        missing = set(range(1, 121)) - found_numbers
        
        if missing:
            print(f"누락된 문항: {sorted(missing)} (총 {len(missing)}개)")
        else:
            print("모든 문항이 발견되었습니다!")
        
        # 페이지별 재배치 - 문항 번호 순서대로
        questions_by_page = {}
        
        # 1. 각 문항을 적절한 페이지에 배치
        for q in unique_questions:
            page_num = self._determine_correct_page(q["question_num"], metadata)
            
            if page_num not in questions_by_page:
                questions_by_page[page_num] = []
            
            # 페이지 정보 제거한 깨끗한 문항 데이터
            clean_q = {
                "question_num": q["question_num"],
                "subject": q["subject"],
                "bbox": q["bbox"],
                "column": q["column"]
            }
            questions_by_page[page_num].append(clean_q)
        
        # 2. 각 페이지 내에서 문항 번호순 정렬
        for page_num in questions_by_page:
            questions_by_page[page_num].sort(key=lambda x: x["question_num"])
        
        # 3. 메타데이터 재구성
        new_pages = []
        for page_num in sorted(questions_by_page.keys()):
            if questions_by_page[page_num]:  # 빈 페이지 제외
                page_data = {
                    "page_num": page_num,
                    "questions": questions_by_page[page_num]
                }
                new_pages.append(page_data)
        
        metadata["pages"] = new_pages
        
        # 최종 통계
        final_found = {q["question_num"] for page in metadata["pages"] for q in page["questions"]}
        final_missing = set(range(1, 121)) - final_found
        
        print(f"후처리 완료: 총 {len(final_found)}개 문항 배치")
        if final_missing:
            print(f"최종 누락: {sorted(final_missing)} (총 {len(final_missing)}개)")
        
        return metadata
    
    def _determine_correct_page(self, question_num: int, metadata: Dict) -> int:
        """실제 발견된 문항 분포를 기반으로 페이지 결정"""
        # 실제로 발견된 문항들의 페이지 분포 분석
        page_ranges = {}
        for page in metadata["pages"]:
            page_num = page["page_num"]
            questions = [q["question_num"] for q in page["questions"]]
            if questions:
                page_ranges[page_num] = {
                    "min": min(questions),
                    "max": max(questions),
                    "count": len(questions)
                }
        
        # 목표 문항이 어느 페이지에 속할지 추정
        for page_num in sorted(page_ranges.keys()):
            page_range = page_ranges[page_num]
            # 문항 번호가 해당 페이지 범위 내에 있으면
            if page_range["min"] <= question_num <= page_range["max"]:
                return page_num
            # 문항 번호가 해당 페이지 범위 직후에 있고, 페이지에 여유가 있으면
            elif (question_num > page_range["max"] and 
                  question_num <= page_range["max"] + 3 and 
                  page_range["count"] < 7):  # 페이지당 최대 7개로 제한
                return page_num
        
        # 인접한 페이지 기반으로 추정
        closest_page = 2  # 기본값
        min_distance = float('inf')
        
        for page_num, page_range in page_ranges.items():
            # 가장 가까운 문항이 있는 페이지 찾기
            distance = min(abs(question_num - page_range["min"]), 
                          abs(question_num - page_range["max"]))
            if distance < min_distance:
                min_distance = distance
                closest_page = page_num
        
        # 페이지별 용량 확인해서 조정
        if closest_page in page_ranges and page_ranges[closest_page]["count"] >= 7:
            # 현재 페이지가 꽉 찼으면 다음 페이지로
            next_page = closest_page + 1
            if next_page not in page_ranges or page_ranges[next_page]["count"] < 7:
                return next_page
        
        return closest_page
    
    def analyze_pdf(self, pdf_path: str, year: int) -> Dict:
        """개선된 PDF 분석 - 실제 문항 위치 기반 정확한 매핑"""
        doc = fitz.open(pdf_path)
        
        # 1단계: 실제 문항 위치 정확 매핑
        actual_questions = self._find_actual_questions(doc, year)
        
        # 2단계: 연도별 적응형 레이아웃 감지
        adaptive_layout = self.detect_adaptive_layout(doc, year)
        
        metadata = {
            "year": year,
            "total_questions": 120,
            "pages": []
        }
        
        # 3단계: 실제 문항 정보 기반으로 정확한 페이지 분석
        page_questions_map = {}  # 페이지별 문항 그룹화
        
        for q_num, q_info in actual_questions.items():
            page_num = q_info['page']
            if page_num not in page_questions_map:
                page_questions_map[page_num] = []
            page_questions_map[page_num].append(q_num)
        
        # 각 페이지별로 정확한 크롭 영역 계산
        for page_num in sorted(page_questions_map.keys()):
            page = doc[page_num - 1]  # 0-based index
            questions_on_page = sorted(page_questions_map[page_num])
            
            print(f"페이지 {page_num} 분석 중...")
            print(f"  실제 발견된 문항: {questions_on_page}")
            
            # 적응형 단락 레이아웃 계산
            left_col, right_col = self.calculate_column_layout(page.rect, adaptive_layout)
            
            # 각 문항의 정확한 위치 찾기
            positions = self.find_question_positions(page, questions_on_page, year)
            
            if not positions:
                print(f"  페이지 {page_num}: 문항 위치 찾기 실패")
                continue
            
            # 연속성 기반 개선된 경계 계산 적용
            verified_questions = self.improve_question_boundaries(
                positions, left_col, right_col, page.rect.height, questions_on_page, page, adaptive_layout, year
            )
            
            # 검증 결과 로깅
            for q_data in verified_questions:
                q_num = q_data["question_num"]
                if q_data["verified"]:
                    print(f"    문항 {q_num}: 연속성 기반 검증 완료")
                else:
                    print(f"    문항 {q_num}: 연속성 기반 검증 실패 (폴백 적용)")
            
            # 위치를 찾지 못한 문항들 처리
            for q_num in questions_on_page:
                if q_num not in positions:
                    print(f"    문항 {q_num}: 위치 찾기 실패")
            
            if verified_questions:
                page_data = {
                    "page_num": page_num,
                    "questions": verified_questions
                }
                metadata["pages"].append(page_data)
                print(f"  페이지 {page_num}: {len(verified_questions)}개 문항 검증 완료")
        
        doc.close()
        
        # 4단계: 누락 문항 처리 및 강화된 검증
        found_questions = {q["question_num"] for page in metadata["pages"] for q in page["questions"]}
        missing_questions = set(range(1, 121)) - found_questions
        
        print(f"\n=== 문항 검출 결과 ===")
        print(f"발견된 문항: {len(found_questions)}/120개")
        
        if missing_questions:
            print(f"🔍 누락된 문항: {sorted(missing_questions)} (총 {len(missing_questions)}개)")
            print("강화된 누락 문항 복구 시작...")
            
            # PDF를 다시 열어서 복구 진행
            doc = fitz.open(pdf_path)
            metadata = self._enhanced_missing_questions_recovery(doc, metadata, missing_questions, year, adaptive_layout)
            doc.close()
            
            # 복구 후 재검증
            found_after_recovery = {q["question_num"] for page in metadata["pages"] for q in page["questions"]}
            still_missing = set(range(1, 121)) - found_after_recovery
            
            if still_missing:
                print(f"⚠️ 복구 후에도 누락: {sorted(still_missing)} (총 {len(still_missing)}개)")
                # 최종 폴백: 표준 위치 기반 추가
                metadata = self._add_fallback_questions(metadata, still_missing, year)
            else:
                print("✅ 모든 누락 문항 성공적으로 복구!")
        else:
            print("✅ 모든 120개 문항 성공적으로 발견!")
        
        # 5단계: 최종 구조 정리 및 검증
        metadata = self._finalize_page_structure(metadata)
        
        # 최종 검증
        final_questions = {q["question_num"] for page in metadata["pages"] for q in page["questions"]}
        if len(final_questions) != 120:
            print(f"⚠️ 경고: 최종 문항 수가 120개가 아닙니다: {len(final_questions)}개")
            print(f"누락: {sorted(set(range(1, 121)) - final_questions)}")
        else:
            print("✅ 최종 검증 완료: 120개 문항 모두 준비됨")
        
        return metadata
    
    def _enhanced_missing_questions_recovery(self, doc, metadata: Dict, missing_questions: set, year: int, adaptive_layout: Dict) -> Dict:
        """강화된 누락 문항 복구 - 전체 PDF 재검색"""
        print("🔍 전체 PDF 재검색으로 누락 문항 복구 중...")
        
        recovered_count = 0
        for missing_num in sorted(missing_questions):
            print(f"  문항 {missing_num} 복구 시도...")
            
            # 전체 페이지에서 해당 문항 재검색
            for page_idx in range(doc.page_count):
                page = doc[page_idx]
                page_num = page_idx + 1
                
                # 매우 관대한 검색 패턴
                liberal_patterns = [
                    f"{missing_num}.",
                    f" {missing_num}.",
                    f"{missing_num} .",
                    f"\t{missing_num}.",
                    f"{missing_num}.\t",
                    f"({missing_num})",
                    f"　{missing_num}.",
                    f"{missing_num}.　",
                ]
                
                found_position = None
                for pattern in liberal_patterns:
                    rects = page.search_for(pattern)
                    if rects:
                        # 각 매치를 검사하여 가장 적합한 것 선택
                        for rect in rects:
                            # 확장된 영역에서 텍스트 검사
                            expanded = fitz.Rect(rect.x0-20, rect.y0-10, rect.x1+200, rect.y1+50)
                            sample_text = page.get_text(clip=expanded)
                            
                            # 매우 관대한 검증
                            if self._liberal_question_validation(sample_text, missing_num):
                                found_position = rect
                                print(f"    ✅ 문항 {missing_num} 발견 (페이지 {page_num})")
                                break
                        
                        if found_position:
                            break
                
                if found_position:
                    # 해당 페이지에 문항 추가
                    self._add_question_to_page(metadata, missing_num, page_num, found_position, year)
                    recovered_count += 1
                    break
            
            if not found_position:
                print(f"    ❌ 문항 {missing_num} 복구 실패")
        
        print(f"복구 완료: {recovered_count}개 문항 복구됨")
        return metadata
    
    def _liberal_question_validation(self, text: str, expected_num: int) -> bool:
        """매우 관대한 문항 검증 - 누락 복구용"""
        if not text or len(text.strip()) < 3:
            return False
            
        # 해당 번호가 포함되어 있고 점이 있으면 일단 OK
        if f"{expected_num}." in text:
            # 명백히 잘못된 것만 제외
            if re.search(r'페이지|점수|시간|분수', text):
                return False
            return True
        
        return False
    
    def _add_fallback_questions(self, metadata: Dict, missing_questions: set, year: int) -> Dict:
        """최종 폴백: 표준 위치 기반 누락 문항 추가"""
        print(f"🔧 최종 폴백: {len(missing_questions)}개 문항을 표준 위치로 추가")
        
        for missing_num in sorted(missing_questions):
            # 과목별 예상 페이지 계산
            expected_page = self._estimate_page_by_question_number(missing_num)
            
            # 표준 위치 계산
            standard_position = self._get_standard_question_position(missing_num, year)
            
            # 메타데이터에 추가
            self._add_question_to_page(metadata, missing_num, expected_page, None, year, fallback_position=standard_position)
            print(f"  📍 문항 {missing_num} → 페이지 {expected_page} (표준 위치)")
        
        return metadata
    
    def _estimate_page_by_question_number(self, question_num: int) -> int:
        """문항 번호 기반 페이지 추정"""
        # 일반적으로 페이지당 6-8개 문항
        estimated_page = (question_num - 1) // 7 + 2  # 2페이지부터 시작
        return max(2, min(estimated_page, 20))  # 2-20페이지 범위
    
    def _get_standard_question_position(self, question_num: int, year: int) -> fitz.Rect:
        """표준 문항 위치 계산"""
        # 홀수는 좌측, 짝수는 우측 (대략적)
        is_left = (question_num % 2 == 1)
        
        if is_left:
            x = self.get_standard_position(year, "left")
        else:
            x = self.get_standard_position(year, "right")
        
        # 페이지 내 순서에 따른 Y 위치
        page_position = ((question_num - 1) % 7)  # 페이지 내 위치 (0-6)
        y = 100 + page_position * 150  # 시작 위치 + 간격
        
        return fitz.Rect(x, y, x + 50, y + 20)
    
    def _add_question_to_page(self, metadata: Dict, question_num: int, page_num: int, position_rect, year: int, fallback_position=None):
        """페이지에 문항 추가"""
        # 해당 페이지 찾기 또는 생성
        target_page = None
        for page in metadata["pages"]:
            if page["page_num"] == page_num:
                target_page = page
                break
        
        if not target_page:
            target_page = {"page_num": page_num, "questions": []}
            metadata["pages"].append(target_page)
        
        # bbox 계산
        if position_rect:
            # 발견된 위치 기반
            standard_width = self.get_standard_width(year, "left")  # 기본값
            bbox = [position_rect.x0, position_rect.y0, position_rect.x0 + standard_width, position_rect.y0 + 200]
        elif fallback_position:
            # 폴백 위치 기반
            standard_width = self.get_standard_width(year, "left" if fallback_position.x0 < 200 else "right")
            bbox = [fallback_position.x0, fallback_position.y0, fallback_position.x0 + standard_width, fallback_position.y0 + 200]
        else:
            # 기본 위치
            x = self.get_standard_position(year, "left")
            y = 100
            width = self.get_standard_width(year, "left")
            bbox = [x, y, x + width, y + 200]
        
        # 새 문항 생성
        new_question = {
            "question_num": question_num,
            "subject": self.get_subject_by_number(question_num),
            "bbox": bbox,
            "column": "left" if bbox[0] < 200 else "right",
            "recovered": True  # 복구된 문항임을 표시
        }
        
        target_page["questions"].append(new_question)
    
    def _calculate_question_bbox(self, position_rect: fitz.Rect, left_col: Dict, right_col: Dict, page_height: float, year: int) -> List[float]:
        """기본 문항 bbox 계산 - 기본 높이만 적용 (정확한 계산은 _get_accurate_question_bbox에서)"""
        x, y = position_rect.x0, position_rect.y0
        
        # 컬럼 판단 및 표준 좌표 적용
        if x < (left_col["x2"] + right_col["x1"]) / 2:  # 좌측 컬럼
            standard_x = self.get_standard_position(year, "left")
            standard_width = self.get_standard_width(year, "left")
        else:  # 우측 컬럼
            standard_x = self.get_standard_position(year, "right")
            standard_width = self.get_standard_width(year, "right")
        
        # 기본 높이 200pt (정확한 계산은 _get_accurate_question_bbox에서 수행)
        bbox = [standard_x, y, standard_x + standard_width, y + 200]
        
        # 페이지 경계 검증 및 보정
        return self._validate_and_fix_bbox(bbox, year)
    
    def _handle_missing_questions(self, metadata: Dict, missing_questions: set, year: int) -> Dict:
        """누락 문항 처리 - 인접 문항 기반 위치 추정"""
        print("누락 문항 후보정 처리 중...")
        
        # 페이지별 문항 분포 분석
        page_ranges = {}
        for page in metadata["pages"]:
            page_num = page["page_num"]
            questions = [q["question_num"] for q in page["questions"]]
            if questions:
                page_ranges[page_num] = {
                    "min": min(questions),  
                    "max": max(questions),
                    "questions": sorted(questions)
                }
        
        # 각 누락 문항에 대해 적절한 페이지 찾기
        for missing_num in sorted(missing_questions):
            target_page = None
            
            # 인접한 문항이 있는 페이지 찾기
            for page_num, page_range in page_ranges.items():
                if page_range["min"] <= missing_num <= page_range["max"]:
                    target_page = page_num
                    break
                    
            if target_page:
                # 해당 페이지에 누락 문항 추가
                self._add_estimated_question(metadata, missing_num, target_page, year)
                print(f"  문항 {missing_num}: 페이지 {target_page}에 추가")
        
        return metadata
    
    def _add_estimated_question(self, metadata: Dict, question_num: int, page_num: int, year: int):
        """추정 위치에 문항 추가"""
        # 해당 페이지 찾기
        target_page = None
        for page in metadata["pages"]:
            if page["page_num"] == page_num:
                target_page = page
                break
        
        if not target_page:
            return
        
        # 인접 문항 기반 위치 추정
        existing_questions = sorted(target_page["questions"], key=lambda x: x["question_num"])
        
        # 문항 번호 기준으로 삽입 위치 찾기
        prev_q = None
        next_q = None
        
        for q in existing_questions:
            if q["question_num"] < question_num:
                prev_q = q
            elif q["question_num"] > question_num:
                next_q = q
                break
        
        # 위치 추정
        if prev_q and next_q:
            # 두 문항 사이에 위치
            estimated_bbox = self._linear_interpolate_bbox(prev_q["bbox"], next_q["bbox"])
            column = prev_q["column"]
        elif prev_q:
            # 이전 문항 아래에 위치
            estimated_bbox = self._estimate_next_bbox(prev_q["bbox"], prev_q["column"])
            column = prev_q["column"]
        elif next_q:
            # 다음 문항 위에 위치
            estimated_bbox = self._estimate_prev_bbox(next_q["bbox"], next_q["column"])
            column = next_q["column"]
        else:
            # 기본 위치
            estimated_bbox = [57, 100, 337, 250]  # 기본 좌측 컬럼
            column = "left"
        
        # 페이지 경계 검증 후 추가
        estimated_bbox = self._validate_and_fix_bbox(estimated_bbox, year)
        
        new_question = {
            "question_num": question_num,
            "subject": self.get_subject_by_number(question_num),
            "bbox": estimated_bbox,
            "column": column,
            "corrected": True
        }
        
        target_page["questions"].append(new_question)
    
    def save_metadata(self, metadata: Dict, output_path: str):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def analyze_and_save(self, pdf_path: str, year: int, output_dir: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        metadata = self.analyze_pdf(pdf_path, year)
        
        output_file = os.path.join(output_dir, f"{year}_data.json")
        self.save_metadata(metadata, output_file)
        
        # 발견된 문항들 통계
        found_numbers = {q['question_num'] for p in metadata['pages'] for q in p['questions']}
        total_found = len(found_numbers)
        missing = set(range(1, 121)) - found_numbers
        
        print(f"분석 완료: {year}년 총 {total_found}개 문항")
        if missing:
            print(f"누락된 문항: {sorted(missing)}")
        
        return metadata

    def get_standard_width(self, year: int, column: str) -> float:
        """연도별 표준 컬럼 폭 반환"""
        return self.standard_column_widths.get(year, {"left": 250, "right": 250}).get(column, 250)
    
    def get_standard_position(self, year: int, column: str) -> float:
        """연도별 표준 컬럼 시작점 반환"""
        return self.standard_column_positions.get(year, {"left": 40, "right": 300, "gap": 20}).get(column, 40 if column == "left" else 300)
    
    def _find_actual_questions(self, doc: fitz.Document, year: int = None) -> Dict[int, Dict]:
        """PDF 전체에서 실제 문항 위치 정확 매핑"""
        print("실제 문항 위치 정확 매핑 중...")
        actual_questions = {}

        # 연도별 컬럼 시작 x좌표가 등록된 경우 들여쓰기 선택지를 필터한다.
        # 실제 문항 번호는 컬럼 시작점과 거의 일치하고, 선택지는 그보다 오른쪽에 있다.
        col_x_filter = None
        if year and year in self.standard_column_positions:
            pos = self.standard_column_positions[year]
            col_x_filter = {
                "left_max": pos["left"] + 2,   # 좌측 컬럼 허용 최대 x (2pt 여유)
                "right_max": pos["right"] + 2,  # 우측 컬럼 허용 최대 x
            }

        # 페이지 2부터 분석 (1페이지는 유의사항)
        for page_num in range(1, doc.page_count):
            page = doc[page_num]
            actual_page_num = page_num + 1

            if col_x_filter:
                # dict 방식: x좌표 포함 분석으로 들여쓰기 선택지 제외
                text_dict = page.get_text("dict")
                for blk in text_dict.get("blocks", []):
                    if "lines" not in blk:
                        continue
                    for ln in blk["lines"]:
                        for sp in ln["spans"]:
                            txt = sp["text"].strip()
                            match = re.match(r'^(\d+)\.', txt)
                            if not match:
                                continue
                            q_num = int(match.group(1))
                            if not (1 <= q_num <= 120):
                                continue
                            x0 = sp["bbox"][0]
                            # 좌측/우측 컬럼 구분 후 x좌표 허용 범위 체크
                            if x0 < 200:
                                if x0 > col_x_filter["left_max"]:
                                    continue  # 들여쓰기 선택지로 간주
                            else:
                                if x0 > col_x_filter["right_max"]:
                                    continue
                            line_text = "".join(s["text"] for s in ln["spans"]).strip()
                            if q_num not in actual_questions:
                                actual_questions[q_num] = {
                                    'page': actual_page_num,
                                    'line_start': 0,
                                    'title': line_text,
                                    'verified': True
                                }
                            else:
                                print(f"중복 문항 {q_num} 발견 (페이지 {actual_page_num}) - 첫 번째 발견 유지 (페이지 {actual_questions[q_num]['page']})")
            else:
                # 기존 방식: 전체 텍스트에서 패턴 매칭
                full_text = page.get_text('text')
                lines = full_text.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    match = re.match(r'^(\d+)\.', line)
                    if match:
                        q_num = int(match.group(1))
                        if 1 <= q_num <= 120:
                            if q_num not in actual_questions:
                                actual_questions[q_num] = {
                                    'page': actual_page_num,
                                    'line_start': i,
                                    'title': line,
                                    'verified': True
                                }
                            else:
                                print(f"중복 문항 {q_num} 발견 (페이지 {actual_page_num}) - 첫 번째 발견 유지 (페이지 {actual_questions[q_num]['page']})")

        print(f"실제 문항 매핑 완료: {len(actual_questions)}개 문항 발견")
        return actual_questions
    
    def _verify_question_in_bbox(self, page: fitz.Page, question_num: int, bbox: List[float]) -> bool:
        """크롭 영역에 올바른 문항이 있는지 검증"""
        try:
            # 크롭 영역에서 텍스트 추출
            crop_rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            text_in_area = page.get_text('text', clip=crop_rect).strip()
            
            if not text_in_area:
                return False
                
            # 해당 문항 번호가 영역 내에 있는지 확인
            question_patterns = [
                rf'^\s*{question_num}\s*\.',  # 줄 시작 + 문항번호 + 점
                rf'\n\s*{question_num}\s*\.',  # 새줄 + 문항번호 + 점
                rf'\b{question_num}\s*\.\s*[가-힣A-Za-z]',  # 문항번호 + 점 + 공백 + 문자
            ]
            
            for pattern in question_patterns:
                if re.search(pattern, text_in_area):
                    return True
                    
            return False
            
        except Exception as e:
            print(f"    검증 오류: {e}")
            return False
    
    def _get_accurate_question_bbox(self, page: fitz.Page, question_num: int, rough_bbox: List[float]) -> List[float]:
        """정확한 문항 경계 박스 계산 - 적응형 높이 적용"""
        try:
            # 문항 번호 패턴으로 정확한 시작점 찾기
            text_dict = page.get_text("dict")
            question_start = None
            
            for block in text_dict.get("blocks", []):
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"]
                        if re.match(rf'^\s*{question_num}\s*\.', text):
                            question_start = span["bbox"]
                            break
                    if question_start:
                        break
                if question_start:
                    break
            
            if question_start:
                # 정확한 시작점에서 적응형 크기로 경계 박스 생성
                x1, y1 = question_start[0], question_start[1]
                
                # 컬럼 폭 기반으로 끝점 계산
                if x1 < 200:  # 좌측 컬럼
                    x2 = x1 + 280
                else:  # 우측 컬럼
                    x2 = x1 + 280
                
                # 적응형 높이 계산
                adaptive_height = self._calculate_adaptive_question_height(page, question_num, x1, y1, x2)
                y2 = y1 + adaptive_height
                
                # 페이지 경계 내로 제한
                page_height = page.rect.height
                if y2 > page_height - 50:
                    y2 = page_height - 50
                
                print(f"    문항 {question_num} 적응형 크롭: 높이 {adaptive_height:.1f}pt")
                
                return [x1, y1, x2, y2]
            else:
                # 정확한 위치를 찾지 못한 경우 기존 박스 사용
                return rough_bbox
                
        except Exception as e:
            print(f"    정확한 bbox 계산 오류: {e}")
            return rough_bbox
    
    def _calculate_adaptive_question_height(self, page: fitz.Page, question_num: int, x1: float, y1: float, x2: float) -> float:
        """문항 내용 분석을 통한 적응형 높이 계산"""
        try:
            # 다음 문항까지의 거리 또는 페이지 끝까지의 거리 계산
            next_question_y = self._find_next_question_position(page, question_num, x1, y1)
            
            if next_question_y:
                # 다음 문항이 있는 경우: 그 문항까지의 90% 지점까지
                content_height = (next_question_y - y1) * 0.9
                print(f"      다음 문항과의 간격 기반: {content_height:.1f}pt")
            else:
                # 다음 문항이 없는 경우: 텍스트 내용 기반 계산
                content_height = self._calculate_content_based_height(page, question_num, x1, y1, x2)
                print(f"      텍스트 내용 기반: {content_height:.1f}pt")
            
            # 최소/최대 높이 제한
            min_height = 120  # 최소 높이
            max_height = 500  # 최대 높이
            
            adaptive_height = max(min_height, min(content_height, max_height))
            
            return adaptive_height
            
        except Exception as e:
            print(f"      적응형 높이 계산 오류: {e}")
            return 200  # 기본 높이
    
    def _find_next_question_position(self, page: fitz.Page, current_question: int, current_x: float, current_y: float) -> float:
        """다음 문항의 Y 위치 찾기"""
        try:
            # 같은 컬럼에서 다음 문항 찾기
            is_left_column = current_x < 200
            next_question_nums = []
            
            # 다음 몇 개 문항 번호 생성
            for i in range(1, 10):
                next_num = current_question + i
                if next_num <= 120:
                    next_question_nums.append(next_num)
            
            for next_num in next_question_nums:
                # 다음 문항의 패턴 검색
                patterns = [f"{next_num}.", f" {next_num}.", f"{next_num} ."]
                
                for pattern in patterns:
                    rects = page.search_for(pattern)
                    if rects:
                        for rect in rects:
                            # 같은 컬럼인지 확인
                            found_is_left = rect.x0 < 200
                            if found_is_left == is_left_column:
                                # 현재 문항보다 아래에 있는지 확인
                                if rect.y0 > current_y + 50:  # 최소 50pt 간격
                                    return rect.y0
            
            return None
            
        except Exception as e:
            print(f"      다음 문항 위치 찾기 오류: {e}")
            return None
    
    def _calculate_content_based_height(self, page: fitz.Page, question_num: int, x1: float, y1: float, x2: float) -> float:
        """텍스트 내용 기반 높이 계산"""
        try:
            # 문항 영역에서 텍스트 추출하여 분석
            # 넉넉한 영역으로 시작
            search_rect = fitz.Rect(x1 - 10, y1 - 10, x2 + 10, y1 + 400)
            text_content = page.get_text(clip=search_rect)
            
            if not text_content:
                return 200  # 기본 높이
            
            # 문항 텍스트 분석
            lines = text_content.split('\n')
            question_lines = []
            found_question_start = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 문항 시작 확인
                if re.match(rf'^\s*{question_num}\s*\.', line):
                    found_question_start = True
                    question_lines.append(line)
                    continue
                
                # 문항 시작 후 텍스트 수집
                if found_question_start:
                    # 다음 문항 번호가 나오면 중단
                    if re.match(r'^\s*\d+\s*\.', line):
                        next_num = int(re.match(r'^\s*(\d+)\s*\.', line).group(1))
                        if next_num > question_num:
                            break
                    
                    question_lines.append(line)
            
            if not question_lines:
                return 200
            
            # 텍스트 줄 수를 기반으로 높이 추정
            line_count = len(question_lines)
            
            # 각 줄의 평균 높이 추정 (약 15-20pt per line)
            avg_line_height = 18
            
            # 여백 포함 계산
            content_height = line_count * avg_line_height + 40  # 상하 여백
            
            # 텍스트 길이도 고려 (긴 텍스트는 더 많은 공간 필요)
            total_text_length = sum(len(line) for line in question_lines)
            
            if total_text_length > 500:  # 긴 문항
                content_height *= 1.3
            elif total_text_length > 300:  # 중간 문항
                content_height *= 1.1
            
            return content_height
            
        except Exception as e:
            print(f"      내용 기반 높이 계산 오류: {e}")
            return 200

if __name__ == "__main__":
    analyzer = PDFAnalyzer()
    
    # 테스트용
    year = 2024
    pdf_path = f"source/{year}_auditor.pdf"
    output_dir = str(year)
    
    try:
        metadata = analyzer.analyze_and_save(pdf_path, year, output_dir)
        print(f"메타데이터 저장: {output_dir}/{year}_data.json")
    except Exception as e:
        print(f"오류 발생: {e}")