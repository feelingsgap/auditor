import re
import json
from bs4 import BeautifulSoup
from pathlib import Path

def html_to_markdown(html_file_path: str, output_file_path: str):
    """HTML 파일을 마크다운으로 변환"""
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    markdown_lines = []
    
    # 제목 추가
    markdown_lines.append("# 정보시스템감리사 기출문제 - 과목별 보기")
    markdown_lines.append("")
    markdown_lines.append("과목을 선택하여 모든 연도의 관련 문제를 확인하세요.")
    markdown_lines.append("")
    
    # 메인 아코디언 찾기
    main_accordion = soup.find('div', {'id': 'majorSubjectsAccordion'})
    
    if main_accordion:
        for accordion_item in main_accordion.find_all('div', class_='accordion-item', recursive=False):
            # 메인 과목 제목 찾기
            main_button = accordion_item.find('button', class_='accordion-button')
            if main_button:
                # 과목명과 문제 수 추출
                main_title_text = main_button.get_text(strip=True)
                # 뱃지 텍스트 제거
                main_title = re.sub(r'\s*\d+\s*문제\s*$', '', main_title_text).strip()
                markdown_lines.append(f"## {main_title}")
                markdown_lines.append("")
                
                # 분석 블록 찾기
                analysis_block = accordion_item.find('div', class_='analysis-block')
                if analysis_block:
                    analysis_text = analysis_block.find('p')
                    if analysis_text:
                        markdown_lines.append("### 영역별 출제경향 분석")
                        markdown_lines.append("")
                        markdown_lines.append(analysis_text.get_text(strip=True))
                        markdown_lines.append("")
                
                # 서브 아코디언 찾기
                sub_accordion = accordion_item.find('div', class_='accordion')
                if sub_accordion:
                    for sub_item in sub_accordion.find_all('div', class_='accordion-item', recursive=False):
                        sub_button = sub_item.find('button', class_='accordion-button')
                        if sub_button:
                            # 서브 과목명과 문제 수 추출
                            sub_title_text = sub_button.get_text(strip=True)
                            sub_title = re.sub(r'\s*\d+\s*문제\s*$', '', sub_title_text).strip()
                            markdown_lines.append(f"### {sub_title}")
                            markdown_lines.append("")
                            
                            # 문제 그리드 찾기
                            question_grid = sub_item.find('div', class_='question-grid')
                            if question_grid:
                                questions = question_grid.find_all('div', class_='card')
                                for question in questions:
                                    img_tag = question.find('img')
                                    header_tag = question.find('div', class_='card-header')
                                    
                                    if img_tag and header_tag:
                                        # 이미지 경로 추출
                                        img_src = img_tag.get('src')
                                        # 문제 번호 추출
                                        question_title = header_tag.get_text(strip=True)
                                        
                                        # 마크다운 형식으로 추가 (이미지 크기 제한)
                                        markdown_lines.append(f"#### {question_title}")
                                        markdown_lines.append("")
                                        markdown_lines.append(f'<img src="{img_src}" alt="{question_title}" style="max-width: 400px; width: 100%;">')
                                        markdown_lines.append("")
                
                markdown_lines.append("---")
                markdown_lines.append("")
    
    # 마크다운 파일 저장
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_lines))
    
    print(f"마크다운 변환 완료: {output_file_path}")
    return output_file_path

if __name__ == "__main__":
    # HTML을 마크다운으로 변환
    html_to_markdown("subjects.html", "subjects.md") 