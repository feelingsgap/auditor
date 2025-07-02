

import json
import os
import re
from typing import Dict, List, Tuple

class DetailedSubjectAggregator:
    def parse_md_file(self, md_path: str) -> Tuple[Dict, Dict, Dict]:
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"Markdown file not found: {md_path}")

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        major_sections = re.split(r'\n## (\d+\. [^\n]+)\n', content)[1:]
        
        structured_data = {}
        question_to_sub_subject = {}
        analysis_texts = {}

        for i in range(0, len(major_sections), 2):
            major_subject_name = major_sections[i].strip()
            section_content = major_sections[i+1]
            
            structured_data[major_subject_name] = {}

            # 출제경향 분석 텍스트 추출
            analysis_match = re.search(r'\*\*영역별 출제경향 분석:\*\*\s*([\s\S]+)', section_content)
            if analysis_match:
                analysis_texts[major_subject_name] = analysis_match.group(1).strip()
            
            # 테이블 행 파싱
            table_match = re.search(r'(\|[\s\S]+\|)', section_content)
            if not table_match:
                continue
            table_content = table_match.group(1)

            rows = table_content.strip().split('\n')
            header = [h.strip() for h in rows[0].split('|') if h.strip()]
            years = [re.search(r'(\d{4})', h).group(1) for h in header if re.search(r'(\d{4})', h)]

            for row in rows[2:]:
                cols = [c.strip() for c in row.split('|') if c.strip()]
                if not cols or len(cols) < len(years) + 1:
                    continue
                
                sub_subject_name = cols[0]
                structured_data[major_subject_name][sub_subject_name] = {}

                for idx, year_str in enumerate(years):
                    year = int(year_str)
                    year_data_col = cols[idx + 1]
                    
                    numbers_match = re.search(r'\(([^\)]+)\)', year_data_col)
                    if numbers_match:
                        numbers_str = numbers_match.group(1).replace(' ', '')
                        q_numbers = [int(n) for n in numbers_str.split(',')]
                        structured_data[major_subject_name][sub_subject_name][year] = q_numbers
                        
                        for q_num in q_numbers:
                            question_to_sub_subject[(year, q_num)] = (major_subject_name, sub_subject_name)

        return structured_data, question_to_sub_subject, analysis_texts

    def aggregate_data(self, years: List[int], question_map: Dict, analysis_map: Dict, base_dir: str = ".") -> Dict:
        aggregated_data = {}

        for year in years:
            metadata_path = os.path.join(base_dir, str(year), f"{year}_data.json")
            if not os.path.exists(metadata_path):
                print(f"경고: {year}년 메타데이터 파일을 찾을 수 없습니다.")
                continue

            with open(metadata_path, 'r', encoding='utf-8') as f:
                year_data = json.load(f)

            for page in year_data.get("pages", []):
                for question in page.get("questions", []):
                    q_num = question.get("question_num")
                    lookup_key = (year, q_num)

                    if lookup_key in question_map:
                        major_subject, sub_subject = question_map[lookup_key]
                        
                        if major_subject not in aggregated_data:
                            aggregated_data[major_subject] = {
                                "analysis": analysis_map.get(major_subject, "분석 내용이 없습니다."),
                                "sub_subjects": {}
                            }
                        if sub_subject not in aggregated_data[major_subject]["sub_subjects"]:
                            aggregated_data[major_subject]["sub_subjects"][sub_subject] = []

                        aggregated_data[major_subject]["sub_subjects"][sub_subject].append({
                            "year": year,
                            "question_num": q_num,
                            "image_path": f"{year}/question/{year}_{q_num}.png"
                        })
        
        for major, data in aggregated_data.items():
            for sub, questions in data["sub_subjects"].items():
                questions.sort(key=lambda x: (x['year'], x['question_num']))

        return aggregated_data

    def save_aggregated_data(self, data: Dict, output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"통합 데이터 저장 완료: {output_path}")

if __name__ == "__main__":
    aggregator = DetailedSubjectAggregator()
    years_to_process = list(range(2021, 2025))
    md_file_path = os.path.join("analyze", "0.시험범위 및 기출분석.md")

    try:
        _, question_map, analysis_map = aggregator.parse_md_file(md_file_path)
        print("마크다운 분석 완료.")

        aggregated_data = aggregator.aggregate_data(years_to_process, question_map, analysis_map)
        print("데이터 통합 완료.")

        output_file = os.path.join("analyze", "subjects_data.json")
        aggregator.save_aggregated_data(aggregated_data, output_file)

        print("\n--- 세부 범위별 통합 결과 ---")
        for major, data in aggregated_data.items():
            print(f"\n[{major}] - 총 {sum(len(q) for q in data['sub_subjects'].values())}개")
            for sub, questions in data["sub_subjects"].items():
                print(f"  - {sub}: {len(questions)}개")
        print("-----------------------------")

    except Exception as e:
        print(f"데이터 통합 중 오류 발생: {e}")
