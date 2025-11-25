import json
import os
from collections import defaultdict

def analyze_distribution():
    json_path = "analyze/subjects_data.json"
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=== 과목별 문항 분포 분석 (기준: 연도별 4문제 초과) ===")
    
    overloaded_subjects = []

    for major_subject, major_data in data.items():
        print(f"\n[{major_subject}]")
        for sub_subject, questions in major_data["sub_subjects"].items():
            # Group by year
            year_counts = defaultdict(int)
            for q in questions:
                year_counts[q['year']] += 1
            
            # Check for overload
            max_count = 0
            max_year = 0
            for year, count in year_counts.items():
                if count > max_count:
                    max_count = count
                    max_year = year
            
            status = "적정"
            if max_count > 4:
                status = f"⚠️ 초과 ({max_year}년 {max_count}문제)"
                overloaded_subjects.append((major_subject, sub_subject, max_year, max_count))
            
            print(f"  - {sub_subject}: 최대 {max_count}문제 ({status})")

    print("\n=== 재분류 필요 항목 ===")
    for major, sub, year, count in overloaded_subjects:
        print(f"{major} > {sub}: {year}년 {count}문제")

if __name__ == "__main__":
    analyze_distribution()
