import json
import os
from jinja2 import Environment, FileSystemLoader
from typing import Dict, List

class HTMLGenerator:
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    def load_year_data(self, year: int, base_dir: str = ".") -> Dict:
        metadata_path = os.path.join(base_dir, str(year), f"{year}_data.json")
        
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_subjects(self, year_data: Dict) -> List[str]:
        subjects = set()
        for page in year_data.get("pages", []):
            for question in page.get("questions", []):
                subjects.add(question.get("subject", "기타"))
        return sorted(list(subjects))
    
    def generate_html(self, years: List[int], output_path: str = "index.html", base_dir: str = "."):
        year_data = {}
        
        # 각 연도별 데이터 로드
        for year in years:
            try:
                data = self.load_year_data(year, base_dir)
                data["subjects"] = self.extract_subjects(data)
                year_data[year] = data
                print(f"{year}년 데이터 로드 완료: {len([q for p in data['pages'] for q in p['questions']])}개 문항")
            except FileNotFoundError as e:
                print(f"경고: {e}")
                continue
        
        if not year_data:
            raise ValueError("로드할 연도별 데이터가 없습니다.")
        
        # HTML 템플릿 렌더링
        template = self.env.get_template("index.html")
        html_content = template.render(
            years=sorted(year_data.keys()),
            year_data=year_data
        )
        
        # HTML 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML 생성 완료: {output_path}")
        print(f"총 {len(year_data)}개 연도, {sum(len([q for p in data['pages'] for q in p['questions']]) for data in year_data.values())}개 문항")
        
        return output_path
    
    def generate_for_single_year(self, year: int, base_dir: str = "."):
        return self.generate_html([year], f"{year}_questions.html", base_dir)
    
    def generate_for_all_years(self, start_year: int = 2021, end_year: int = 2024, base_dir: str = "."):
        years = list(range(start_year, end_year + 1))
        return self.generate_html(years, "index.html", base_dir)

if __name__ == "__main__":
    generator = HTMLGenerator()
    
    try:
        # 전체 연도 HTML 생성
        html_file = generator.generate_for_all_years()
        print(f"메인 HTML 파일 생성: {html_file}")
        
        # 개별 연도 HTML도 생성 (선택사항)
        for year in range(2021, 2025):
            try:
                individual_html = generator.generate_for_single_year(year)
                print(f"{year}년 개별 HTML 생성: {individual_html}")
            except Exception as e:
                print(f"{year}년 개별 HTML 생성 실패: {e}")
                
    except Exception as e:
        print(f"HTML 생성 오류: {e}")