from collections import OrderedDict
import json
import os
import re
from typing import Dict, List, Tuple

class DetailedSubjectAggregator:
    def parse_md_file(self, md_path: str) -> Tuple[OrderedDict, Dict, Dict]:
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"Markdown file not found: {md_path}")

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        major_sections = re.split(r'\n## (\d+\. [^\n]+)\n', content)[1:]
        
        structured_data = OrderedDict() # 순서 유지를 위해 OrderedDict 사용
        question_to_sub_subject = {}
        analysis_texts = {}

        for i in range(0, len(major_sections), 2):
            major_subject_name = major_sections[i].strip()
            section_content = major_sections[i+1]
            
            # 대분류의 OrderedDict 초기화
            structured_data[major_subject_name] = OrderedDict()

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
                # 세부 과목의 OrderedDict 초기화 (순서 유지)
                structured_data[major_subject_name][sub_subject_name] = OrderedDict()

                for idx, year_str in enumerate(years):
                    year = int(year_str)
                    year_data_col = cols[idx + 1]
                    
                    numbers_match = re.search(r'\(([^\)]+)\)', year_data_col)
                    if numbers_match:
                        numbers_str = numbers_match.group(1).replace(' ', '')
                        if numbers_str == '-':
                            q_numbers = []
                        else:
                            q_numbers = [int(n) for n in numbers_str.split(',')]
                        structured_data[major_subject_name][sub_subject_name][year] = q_numbers
                        
                        for q_num in q_numbers:
                            question_to_sub_subject[(year, q_num)] = (major_subject_name, sub_subject_name)

        return structured_data, question_to_sub_subject, analysis_texts

    def parse_detailed_files(self, base_dir: str) -> Dict[str, Dict[str, List[str]]]:
        """
        analyze/*.md 파일들을 파싱하여 세부 과목별 공부 내역을 추출합니다.
        Returns:
            Dict[major_subject, Dict[sub_subject, List[study_content]]]
        """
        detailed_info = {}
        
        # 1.md ~ 5.md 파일 찾기
        # print(f"Searching in {base_dir}...")
        for filename in os.listdir(base_dir):
            # Non-greedy 매칭 사용: .+? 또는 [^.]+ 사용
            if not re.match(r'[1-5]\.[^.]+\.md$', filename):
                continue
            
            # print(f"Found file: {filename}")
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 대분류 제목 추출 (파일명 또는 내용에서)
            major_subject_match = re.match(r'(\d+)\.(.+)\.md', filename)
            if not major_subject_match:
                continue
            
            major_num = major_subject_match.group(1)
            
            detailed_info[filename] = {} # 임시 키로 파일명 사용
            
            lines = content.split('\n')
            current_sub_subject = None
            current_cluster = None  # {"cluster": ..., "raw_children": [(indent, text), ...]}

            def finalize_cluster(cluster):
                """raw_children 을 sub_items(flat) 또는 sub_groups(nested)로 정규화."""
                if cluster is None:
                    return
                children = cluster.pop("raw_children", [])
                cluster.setdefault("sub_items", [])
                cluster.setdefault("sub_groups", [])
                if not children:
                    return
                max_indent = max(ind for ind, _ in children)
                if max_indent >= 8:
                    current_sg = None
                    for ind, text in children:
                        if ind == 4:
                            current_sg = {"title": text, "entries": []}
                            cluster["sub_groups"].append(current_sg)
                        else:
                            if current_sg is None:
                                current_sg = {"title": "기타", "entries": []}
                                cluster["sub_groups"].append(current_sg)
                            current_sg["entries"].append(text)
                else:
                    cluster["sub_items"] = [text for _, text in children]

            for line in lines:
                original_line = line  # 원본 라인 유지 (들여쓰기 확인용)
                line = line.strip()

                # H1 세분류 헤더: # N.M name 또는 # N.M.K name
                h1_match = re.match(r'^#\s+\d+\.\d+(?:\.\d+)?\s+(.+)$', line)
                if h1_match:
                    finalize_cluster(current_cluster)
                    current_sub_subject = h1_match.group(1).strip()
                    detailed_info[filename][current_sub_subject] = []
                    current_cluster = None
                    continue

                # 그 외 마크다운 헤더는 스킵
                if line.startswith('#'):
                    continue

                # 본문 bullet: 0칸 = 클러스터, 4칸 = 하위그룹 or item, 8칸+ = 그룹 내 item
                if current_sub_subject and (line.startswith('-') or line.startswith('*')):
                    clean_line = re.sub(r'^[\-\*]\s*', '', line).strip()
                    if clean_line:
                        indent = len(original_line) - len(original_line.lstrip())
                        if indent < 4:
                            finalize_cluster(current_cluster)
                            current_cluster = {"cluster": clean_line, "raw_children": []}
                            detailed_info[filename][current_sub_subject].append(current_cluster)
                        else:
                            if current_cluster is None:
                                current_cluster = {"cluster": clean_line, "raw_children": []}
                                detailed_info[filename][current_sub_subject].append(current_cluster)
                            else:
                                current_cluster["raw_children"].append((indent, clean_line))

            finalize_cluster(current_cluster)

        return detailed_info

    def aggregate_data(self, years: List[int], question_map: Dict, analysis_map: Dict, structured_md_data: OrderedDict, detailed_info: Dict, base_dir: str = ".") -> OrderedDict:
        # 최종 데이터를 저장할 구조 초기화
        # structured_md_data에서 얻은 순서를 유지하기 위해 OrderedDict 사용
        aggregated_data = OrderedDict()
        for major_subject in structured_md_data.keys():
            aggregated_data[major_subject] = {
                "analysis": analysis_map.get(major_subject, "분석 내용이 없습니다."),
                "sub_subjects": OrderedDict() # 순서 유지를 위해 OrderedDict 사용
            }
            # 마크다운에서 파싱한 세부범위 순서대로 초기화
            # 마크다운에서 파싱한 세부범위 순서대로 초기화
            for sub_subject in structured_md_data[major_subject].keys():
                aggregated_data[major_subject]["sub_subjects"][sub_subject] = {
                    "questions": [],
                    "study_contents": []
                }
                
                # Detailed info 매핑
                # detailed_info의 키는 파일명(예: 1.감리 및 사업관리.md)이고, 값은 {세부과목: [내용]}
                # major_subject(예: 1. 감리 및 사업관리)와 매칭되는 파일 찾기
                major_num = major_subject.split('.')[0]
                
                for filename, subs in detailed_info.items():
                    if filename.startswith(f"{major_num}."):
                        # 세부 과목 매칭 (정확한 매칭 필요)
                        # structured_md_data의 sub_subject: "1.1 프로젝트 관리 일반"
                        # detailed_info의 sub_subject: "프로젝트 관리 일반"
                        # 따라서 포함 관계 확인
                        
                        # sub_subject에서 번호 제거 (예: "1.1 " 제거)
                        sub_name_only = re.sub(r'^\d+\.\d+(?:\.\d+)?\s+', '', sub_subject).strip()
                        
                        # Debugging
                        print(f"[DEBUG] Major: {major_subject}, Sub: {sub_subject}")
                        print(f"[DEBUG] sub_name_only: '{sub_name_only}'")
                        print(f"[DEBUG] Available keys: {list(subs.keys())[:5]}")  # First 5 keys

                        if sub_name_only in subs:
                            aggregated_data[major_subject]["sub_subjects"][sub_subject]["study_contents"] = subs[sub_name_only]
                            print(f"[MATCHED] {sub_subject} -> {len(subs[sub_name_only])} items")
                        else:
                            # Try fuzzy match or check for slight variations
                            for k in subs.keys():
                                if sub_name_only in k or k in sub_name_only:
                                    aggregated_data[major_subject]["sub_subjects"][sub_subject]["study_contents"] = subs[k]
                                    print(f"[FUZZY] {sub_subject} -> {k}")
                                    break
                        break

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
                        
                        # 이미 순서대로 초기화되었으므로 바로 접근
                        aggregated_data[major_subject]["sub_subjects"][sub_subject]["questions"].append({
                            "year": year,
                            "question_num": q_num,
                            "image_path": f"{year}/question/{year}_{q_num}.png",
                            "answer": question.get("answer"),
                            "disputed": question.get("disputed", False),
                            "expl_claude": question.get("expl_claude", ""),
                            "expl_gemini": question.get("expl_gemini", ""),
                            "expl_gpt": question.get("expl_gpt", ""),
                        })
        
        # 각 과목 내에서 연도와 문제 번호로 정렬
        for major, data in aggregated_data.items():
            for sub, sub_data in data["sub_subjects"].items():
                sub_data["questions"].sort(key=lambda x: (x['year'], x['question_num']))

        return aggregated_data

    def save_aggregated_data(self, data: Dict, output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"통합 데이터 저장 완료: {output_path}")

if __name__ == "__main__":
    aggregator = DetailedSubjectAggregator()
    years_to_process = list(range(2021, 2026))
    md_file_path = os.path.join("analyze", "0.시험범위 및 기출분석.md")

    try:
        structured_md_data, question_map, analysis_map = aggregator.parse_md_file(md_file_path)
        print("마크다운 분석 완료.")

        detailed_info = aggregator.parse_detailed_files("analyze")
        print("상세 공부 내역 파싱 완료.")

        aggregated_data = aggregator.aggregate_data(years_to_process, question_map, analysis_map, structured_md_data, detailed_info)
        print("데이터 통합 완료.")

        output_file = os.path.join("analyze", "subjects_data.json")
        aggregator.save_aggregated_data(aggregated_data, output_file)

        print("\n--- 세부 범위별 통합 결과 ---")
        for major, data in aggregated_data.items():
            total_questions = sum(len(sub_data['questions']) for sub_data in data['sub_subjects'].values())
            print(f"\n[{major}] - 총 {total_questions}개")
            for sub, sub_data in data["sub_subjects"].items():
                print(f"  - {sub}: {len(sub_data['questions'])}개, 공부내용 {len(sub_data['study_contents'])}건")
        print("-----------------------------")

    except Exception as e:
        print(f"데이터 통합 중 오류 발생: {e}")
