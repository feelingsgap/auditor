import json
import os
import sys

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

def inspect_overloaded():
    # Define overloaded questions to inspect
    targets = [
        {"year": 2025, "subject": "1.8 SW사업 대가산정/관리", "q_nums": [3, 7, 9, 10, 11, 16]},
        {"year": 2025, "subject": "1.9 법령/규정", "q_nums": [1, 2, 4, 5, 6, 12]},
        {"year": 2025, "subject": "2.7 코드 품질 및 복잡도", "q_nums": [31, 38, 39, 40, 41]},
        {"year": 2022, "subject": "5.7 SW 취약점", "q_nums": [105, 113, 115, 116, 119]}
    ]

    for target in targets:
        year = target['year']
        subject = target['subject']
        q_nums = target['q_nums']
        
        print(f"\n=== {subject} ({year}년) 분석 ===")
        json_path = f"{year}/{year}_data.json"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        q_map = {}
        for page in data['pages']:
            for q in page['questions']:
                q_map[q['question_num']] = q
        
        for q_num in q_nums:
            if q_num in q_map:
                text = q_map[q_num].get('question_text', '텍스트 없음')
                print(f"\n[문항 {q_num}]")
                print(text[:200].replace('\n', ' '))
            else:
                print(f"\n[문항 {q_num}] - 데이터 없음")

if __name__ == "__main__":
    inspect_overloaded()
