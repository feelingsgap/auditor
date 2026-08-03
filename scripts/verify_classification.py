import json
import os
from collections import defaultdict

from years import available_years

def verify_classification():
    json_path = "analyze/subjects_data.json"
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Track classified questions
    classified = defaultdict(set)
    
    for major_subject, major_data in data.items():
        for sub_subject, sub_data in major_data["sub_subjects"].items():
            # sub_data 는 {"questions": [...], ...} 구조
            for q in sub_data["questions"]:
                year = q['year']
                q_num = q['question_num']
                classified[year].add(q_num)

    # Check for missing questions
    years = available_years()
    total_missing = 0
    
    print("=== 미분류 문항 분석 ===")
    for year in years:
        expected = set(range(1, 121))
        found = classified[year]
        missing = sorted(expected - found)
        
        if missing:
            print(f"\n[{year}년] - {len(missing)}개 누락")
            print(f"누락된 번호: {missing}")
            total_missing += len(missing)
        else:
            print(f"\n[{year}년] - 모든 문항 분류됨")

    print(f"\n총 누락 문항 수: {total_missing}")

if __name__ == "__main__":
    verify_classification()
