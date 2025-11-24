import json
import os

def check_ranges():
    json_path = "analyze/subjects_data.json"
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Define expected ranges (standard)
    # Note: This is a heuristic. Some years might vary, but usually it's fixed.
    ranges = {
        "1. 감리 및 사업관리": (1, 25),
        "2. 소프트웨어 공학": (26, 50),
        "3. 데이터베이스": (51, 75),
        "4. 시스템 구조": (76, 100),
        "5. 보안": (101, 120)
    }

    print("=== 과목별 문항 번호 범위 검증 ===")
    
    for subject, (start, end) in ranges.items():
        if subject not in data:
            continue
            
        print(f"\n[{subject}] (Expected: {start}~{end})")
        subject_data = data[subject]
        
        outliers = []
        total_count = 0
        
        for sub_subject, questions in subject_data["sub_subjects"].items():
            for q in questions:
                total_count += 1
                q_num = q['question_num']
                year = q['year']
                if not (start <= q_num <= end):
                    outliers.append(f"{year}년 {q_num}번")
        
        print(f"총 문항 수: {total_count}")
        if outliers:
            print(f"범위 벗어난 문항: {outliers}")
        else:
            print("모든 문항이 범위 내에 있습니다.")

if __name__ == "__main__":
    check_ranges()
