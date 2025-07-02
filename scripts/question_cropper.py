import fitz
import json
import os
from typing import Dict, List

class QuestionCropper:
    def __init__(self):
        self.dpi = 300
        self.padding = 10
    
    def crop_question_directly(self, pdf_path: str, page_num: int, bbox: List[float], output_path: str):
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]  # 0-based index
        
        # 바운딩 박스에 패딩 추가
        x1, y1, x2, y2 = bbox
        rect = fitz.Rect(x1 - self.padding, y1 - self.padding, 
                        x2 + self.padding, y2 + self.padding)
        
        # 페이지 경계 내로 제한
        rect = rect & page.rect
        
        # 유효한 크기인지 확인
        if rect.width <= 0 or rect.height <= 0:
            print(f"경고: 유효하지 않은 크롭 영역, 기본 영역 사용")
            rect = fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
        
        # 고해상도 매트릭스 (300 DPI)
        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
        
        # 픽스맵 생성 및 저장
        try:
            pix = page.get_pixmap(matrix=mat, clip=rect)
            pix.save(output_path)
            pix = None  # 메모리 해제
        except Exception as e:
            # 오류 발생시 저해상도로 재시도
            print(f"고해상도 크롭 실패, 저해상도로 재시도: {e}")
            mat = fitz.Matrix(2.0, 2.0)  # 저해상도
            pix = page.get_pixmap(matrix=mat, clip=rect)
            pix.save(output_path)
            pix = None
        
        doc.close()
    
    def crop_questions_from_metadata(self, pdf_path: str, metadata: Dict, output_dir: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        year = metadata["year"]
        question_dir = os.path.join(output_dir, "question")
        os.makedirs(question_dir, exist_ok=True)
        
        # 사전 검증: 120개 문항이 모두 있는지 확인
        all_questions = []
        for page_data in metadata["pages"]:
            for question_data in page_data["questions"]:
                all_questions.append(question_data["question_num"])
        
        expected_questions = set(range(1, 121))
        found_questions = set(all_questions)
        missing_from_metadata = expected_questions - found_questions
        
        print(f"\n=== 크롭 전 메타데이터 검증 ===")
        print(f"메타데이터 내 문항: {len(found_questions)}/120개")
        
        if missing_from_metadata:
            print(f"⚠️ 메타데이터에서 누락된 문항: {sorted(missing_from_metadata)}")
            print("❌ 크롭을 진행할 수 없습니다. PDF 분석을 다시 실행하세요.")
            return 0
        else:
            print("✅ 메타데이터 검증 완료: 120개 문항 모두 준비됨")
        
        total_questions = 0
        failed_questions = []
        successful_crops = []
        
        for page_data in metadata["pages"]:
            page_num = page_data["page_num"]
            
            for question_data in page_data["questions"]:
                question_num = question_data["question_num"]
                bbox = question_data["bbox"]
                
                output_filename = f"{year}_{question_num}.png"
                output_path = os.path.join(question_dir, output_filename)
                
                try:
                    self.crop_question_directly(pdf_path, page_num, bbox, output_path)
                    total_questions += 1
                    successful_crops.append(question_num)
                    
                    # 복구된 문항인지 표시
                    if question_data.get("recovered", False):
                        print(f"  📦 문항 {question_num} 크롭 완료 (복구된 문항)")
                    
                    if total_questions % 20 == 0:
                        print(f"📊 진행률: {total_questions}/120 문항 처리 완료")
                        
                except Exception as e:
                    print(f"❌ 문항 {question_num} 크롭 실패: {e}")
                    print(f"   페이지: {page_num}, bbox: {bbox}")
                    failed_questions.append(question_num)
                    continue
        
        # 최종 검증
        print(f"\n=== 크롭 결과 검증 ===")
        created_files = set()
        for i in range(1, 121):
            image_path = os.path.join(question_dir, f"{year}_{i}.png")
            if os.path.exists(image_path):
                created_files.add(i)
        
        missing_files = expected_questions - created_files
        
        if failed_questions:
            print(f"❌ 크롭 실패한 문항: {sorted(failed_questions)}")
            
        if missing_files:
            print(f"⚠️ 이미지 파일이 생성되지 않은 문항: {sorted(missing_files)}")
        
        print(f"✅ 크롭 완료: {year}년 총 {len(created_files)}/120개 문항")
        print(f"   성공: {len(successful_crops)}개, 실패: {len(failed_questions)}개")
        
        if len(created_files) == 120:
            print("🎉 모든 120개 문항이 성공적으로 크롭되었습니다!")
        else:
            print(f"⚠️ 크롭되지 않은 문항이 {120 - len(created_files)}개 있습니다.")
        
        return len(created_files)
    
    def crop_questions_by_year(self, year: int, source_dir: str = "source", output_base_dir: str = "."):
        pdf_path = os.path.join(source_dir, f"{year}_auditor.pdf")
        metadata_path = os.path.join(output_base_dir, str(year), f"{year}_data.json")
        output_dir = os.path.join(output_base_dir, str(year))
        
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return self.crop_questions_from_metadata(pdf_path, metadata, output_dir)

if __name__ == "__main__":
    cropper = QuestionCropper()
    
    # 테스트용
    year = 2024
    
    try:
        total = cropper.crop_questions_by_year(year)
        print(f"{year}년 문항 크롭 완료: {total}개")
    except Exception as e:
        print(f"오류 발생: {e}")