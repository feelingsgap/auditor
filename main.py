import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

#!/usr/bin/env python3
import argparse
import os
import time
import json
from pathlib import Path
from datetime import datetime

# 스크립트 디렉토리를 Python 패스에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from pdf_analyzer import PDFAnalyzer
from question_cropper import QuestionCropper
from html_generator import HTMLGenerator

class AuditorPDFProcessor:
    def __init__(self):
        self.analyzer = PDFAnalyzer()
        self.cropper = QuestionCropper()
        self.generator = HTMLGenerator()
        self.source_dir = "source"
        self.available_years = [2021, 2022, 2023, 2024]
        self.processing_log = []  # 처리 로그
    
    def log_processing_step(self, year: int, step: str, status: str, details: str = ""):
        """처리 단계 로깅"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "year": year,
            "step": step,
            "status": status,
            "details": details
        }
        self.processing_log.append(log_entry)
    
    def save_processing_log(self, year: int):
        """처리 로그 저장"""
        log_file = f"{year}/{year}_processing_log.json"
        os.makedirs(str(year), exist_ok=True)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.processing_log, f, ensure_ascii=False, indent=2)
        
        print(f"처리 로그 저장: {log_file}")
    
    def validate_question_completeness(self, year: int) -> bool:
        """문항 완성도 검증"""
        print(f"\n=== {year}년 문항 완성도 최종 검증 ===")
        
        # 메타데이터 파일 확인
        metadata_path = f"{year}/{year}_data.json"
        if not os.path.exists(metadata_path):
            print(f"❌ 메타데이터 파일 없음: {metadata_path}")
            return False
        
        # 메타데이터에서 문항 수 확인
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        found_questions = {q["question_num"] for page in metadata["pages"] for q in page["questions"]}
        missing_metadata = set(range(1, 121)) - found_questions
        
        print(f"메타데이터 문항: {len(found_questions)}/120개")
        if missing_metadata:
            print(f"❌ 메타데이터 누락: {sorted(missing_metadata)}")
            self.log_processing_step(year, "validation", "failed", f"메타데이터 누락: {len(missing_metadata)}개")
            return False
        
        # 실제 이미지 파일 확인
        question_dir = f"{year}/question"
        if not os.path.exists(question_dir):
            print(f"❌ 이미지 디렉토리 없음: {question_dir}")
            return False
        
        created_images = set()
        for i in range(1, 121):
            image_path = f"{question_dir}/{year}_{i}.png"
            if os.path.exists(image_path):
                created_images.add(i)
        
        missing_images = set(range(1, 121)) - created_images
        
        print(f"생성된 이미지: {len(created_images)}/120개")
        if missing_images:
            print(f"❌ 이미지 누락: {sorted(missing_images)}")
            self.log_processing_step(year, "validation", "failed", f"이미지 누락: {len(missing_images)}개")
            return False
        
        print("✅ 완성도 검증 통과: 120개 문항 모두 준비됨")
        self.log_processing_step(year, "validation", "success", "120개 문항 완료")
        return True
    
    def check_pdf_exists(self, year: int) -> bool:
        pdf_path = os.path.join(self.source_dir, f"{year}_auditor.pdf")
        return os.path.exists(pdf_path)
    
    def process_step1_analyze(self, year: int) -> bool:
        """Step 1: PDF 분석 및 메타데이터 추출"""
        print(f"\n=== Step 1: {year}년 PDF 분석 시작 ===")
        
        if not self.check_pdf_exists(year):
            error_msg = f"{year}_auditor.pdf 파일을 찾을 수 없습니다."
            print(f"오류: {error_msg}")
            self.log_processing_step(year, "pdf_analysis", "failed", error_msg)
            return False
        
        try:
            pdf_path = os.path.join(self.source_dir, f"{year}_auditor.pdf")
            output_dir = str(year)
            
            start_time = time.time()
            metadata = self.analyzer.analyze_and_save(pdf_path, year, output_dir)
            end_time = time.time()
            
            question_count = len([q for p in metadata['pages'] for q in p['questions']])
            
            print(f"✓ {year}년 PDF 분석 완료 ({end_time - start_time:.2f}초)")
            print(f"  - 총 {question_count}개 문항 발견")
            print(f"  - 메타데이터 저장: {output_dir}/{year}_data.json")
            
            if question_count == 120:
                self.log_processing_step(year, "pdf_analysis", "success", f"120개 문항 완벽 분석")
            else:
                self.log_processing_step(year, "pdf_analysis", "partial", f"{question_count}개 문항 분석, {120-question_count}개 누락")
            
            return True
            
        except Exception as e:
            error_msg = f"PDF 분석 실패: {str(e)}"
            print(f"✗ {year}년 {error_msg}")
            self.log_processing_step(year, "pdf_analysis", "failed", error_msg)
            return False
    
    def process_step2_crop(self, year: int) -> bool:
        """Step 2: 문항 크롭"""
        print(f"\n=== Step 2: {year}년 문항 크롭 시작 ===")
        
        try:
            start_time = time.time()
            total_questions = self.cropper.crop_questions_by_year(year, self.source_dir)
            end_time = time.time()
            
            print(f"✓ {year}년 문항 크롭 완료 ({end_time - start_time:.2f}초)")
            print(f"  - 총 {total_questions}개 문항 이미지 생성")
            print(f"  - 저장 위치: {year}/question/")
            
            if total_questions == 120:
                self.log_processing_step(year, "question_crop", "success", f"120개 문항 완벽 크롭")
            elif total_questions == 0:
                self.log_processing_step(year, "question_crop", "failed", "크롭된 문항 없음")
                return False
            else:
                self.log_processing_step(year, "question_crop", "partial", f"{total_questions}개 문항 크롭, {120-total_questions}개 실패")
            
            return True
            
        except Exception as e:
            error_msg = f"문항 크롭 실패: {str(e)}"
            print(f"✗ {year}년 {error_msg}")
            self.log_processing_step(year, "question_crop", "failed", error_msg)
            return False
    
    def process_step3_html(self, years: list = None) -> bool:
        """Step 3: HTML 생성"""
        if years is None:
            years = self.available_years
        
        print(f"\n=== Step 3: HTML 생성 시작 ===")
        print(f"대상 연도: {', '.join(map(str, years))}")
        
        try:
            start_time = time.time()
            html_file = self.generator.generate_html(years)
            end_time = time.time()
            
            print(f"✓ HTML 생성 완료 ({end_time - start_time:.2f}초)")
            print(f"  - 파일: {html_file}")
            print(f"  - 포함 연도: {len(years)}개")
            return True
            
        except Exception as e:
            print(f"✗ HTML 생성 실패: {e}")
            return False
    
    def process_single_year(self, year: int, steps: list = None) -> bool:
        """단일 연도 전체 처리"""
        if steps is None:
            steps = [1, 2]
        
        print(f"\n{'='*50}")
        print(f"  {year}년 정보시스템감리사 기출문제 처리 시작")
        print(f"{'='*50}")
        
        success = True
        
        if 1 in steps:
            success &= self.process_step1_analyze(year)
        
        if 2 in steps and success:
            success &= self.process_step2_crop(year)
        
        return success
    
    def process_all_years(self, steps: list = None) -> bool:
        """전체 연도 처리"""
        if steps is None:
            steps = [1, 2, 3]
        
        print(f"\n{'='*60}")
        print(f"  정보시스템감리사 기출문제 전체 처리 시작")
        print(f"  대상 연도: {', '.join(map(str, self.available_years))}")
        print(f"{'='*60}")
        
        processed_years = []
        
        # Step 1, 2: 연도별 처리
        if 1 in steps or 2 in steps:
            for year in self.available_years:
                if self.check_pdf_exists(year):
                    if self.process_single_year(year, [s for s in steps if s in [1, 2]]):
                        processed_years.append(year)
                else:
                    print(f"경고: {year}_auditor.pdf 파일이 없어 건너뜁니다.")
        
        # Step 3: HTML 생성
        if 3 in steps and processed_years:
            self.process_step3_html(processed_years)
        
        return len(processed_years) > 0

def main():
    parser = argparse.ArgumentParser(
        description="정보시스템감리사 기출문제 PDF → HTML 변환 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py --all                    # 전체 연도 모든 단계 처리
  python main.py --year 2024              # 2024년만 처리
  python main.py --year 2024 --step 1     # 2024년 PDF 분석만
  python main.py --year 2024 --step 2     # 2024년 문항 크롭만
  python main.py --step 3                 # HTML 생성만
        """
    )
    
    parser.add_argument('--all', action='store_true', 
                       help='모든 연도의 모든 단계 처리')
    parser.add_argument('--year', type=int, choices=[2021, 2022, 2023, 2024],
                       help='처리할 연도 지정')
    parser.add_argument('--step', type=int, choices=[1, 2, 3],
                       help='처리할 단계 (1: 분석, 2: 크롭, 3: HTML생성)')
    
    args = parser.parse_args()
    
    processor = AuditorPDFProcessor()
    
    try:
        if args.all:
            # 전체 처리
            success = processor.process_all_years()
            
        elif args.year:
            if args.step:
                # 특정 연도, 특정 단계
                if args.step == 1:
                    success = processor.process_step1_analyze(args.year)
                    if success:
                        # Step 1 완료 후 완성도 검증
                        processor.validate_question_completeness(args.year)
                elif args.step == 2:
                    success = processor.process_step2_crop(args.year)
                    if success:
                        # Step 2 완료 후 완성도 검증
                        processor.validate_question_completeness(args.year)
                elif args.step == 3:
                    success = processor.process_step3_html([args.year])
            else:
                # 특정 연도 전체 처리
                success = processor.process_single_year(args.year)
                if success:
                    # 크롭 완료 후 검증
                    validation_success = processor.validate_question_completeness(args.year)
                    if validation_success:
                        processor.process_step3_html([args.year])
                    else:
                        print(f"⚠️ {args.year}년 문항 완성도 검증 실패 - HTML 생성 건너뜀")
                        success = False
            
            # 로그 저장
            if args.year:
                processor.save_processing_log(args.year)
                    
        elif args.step == 3:
            # HTML 생성만
            success = processor.process_step3_html()
            
        else:
            # 인수가 없으면 도움말 출력
            parser.print_help()
            return
        
        if success:
            print(f"\n{'='*50}")
            print("🎉 모든 처리가 성공적으로 완료되었습니다!")
            print("✅ 120개 문항이 모두 준비되었습니다.")
            print("📄 index.html 파일을 브라우저에서 열어보세요.")
            print(f"{'='*50}")
        else:
            print(f"\n{'='*50}")
            print("❌ 일부 처리 과정에서 오류가 발생했습니다.")
            print("📋 처리 로그를 확인하여 문제를 파악하세요.")
            print(f"{'='*50}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n처리가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n예상치 못한 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()