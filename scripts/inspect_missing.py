import json
import os
import sys

# Add scripts directory to path to import text_extractor
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
try:
    from text_extractor import TextExtractor
except ImportError:
    # Fallback if running from scripts dir
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from text_extractor import TextExtractor

def inspect_questions(missing_list):
    for year, q_nums in missing_list.items():
        print(f"\n=== {year}년 미분류 문항 분석 ===")
        pdf_path = f"{year}/{year}_auditor.pdf"
        json_path = f"{year}/{year}_data.json"
        
        if not os.path.exists(json_path):
            print(f"Data file not found: {json_path}")
            continue
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Create a map for quick lookup
        q_map = {}
        for page in data['pages']:
            for q in page['questions']:
                q_map[q['question_num']] = q
        
        for q_num in q_nums:
            if q_num in q_map:
                q_data = q_map[q_num]
                print(f"\n[문항 {q_num}]")
                print(f"텍스트: {q_data.get('question_text', '텍스트 없음')[:200]}...") # Print first 200 chars
            else:
                print(f"\n[문항 {q_num}] - 메타데이터에서 찾을 수 없음")

if __name__ == "__main__":
    # Missing questions identified from previous step
    missing_data = {
        2021: [24, 50, 54, 61, 87, 95, 100],
        2022: [25, 49, 70, 80, 98, 100, 115, 116],
        2023: [58],
        2024: [48],
        2025: [8, 10, 11, 12, 27, 38, 40, 46, 47, 50, 51, 60, 65, 66, 67, 71, 72, 78, 89, 93, 95, 96, 99, 105, 107, 112, 120]
    }
    inspect_questions(missing_data)
