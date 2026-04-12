"""
과목별 기출문제 PDF 생성기
subjects_data.json → 과목별 PDF 5개 (A4 가로, 문제당 1페이지)
"""

import json
import os
import sys
import re

# macOS Homebrew 라이브러리 경로 설정 (WeasyPrint가 libgobject 등을 찾을 수 있도록)
_homebrew_lib = '/opt/homebrew/lib'
if os.path.isdir(_homebrew_lib):
    os.environ.setdefault('DYLD_LIBRARY_PATH', _homebrew_lib)
    existing = os.environ.get('DYLD_LIBRARY_PATH', '')
    if _homebrew_lib not in existing.split(':'):
        os.environ['DYLD_LIBRARY_PATH'] = f"{_homebrew_lib}:{existing}".strip(':')

import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


ANSWER_CIRCLES = {1: '①', 2: '②', 3: '③', 4: '④', 5: '⑤'}


def md_to_html(text: str) -> str:
    if not text or not text.strip():
        return ''
    return markdown.markdown(text, extensions=['nl2br'])


def make_safe_filename(subject_name: str) -> str:
    # "1. 감리 및 사업관리" -> "1_감리_및_사업관리"
    name = re.sub(r'[^\w가-힣]', '_', subject_name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


def generate_subject_pdf(subject_name: str, subject_data: dict, output_path: str, base_dir: str, env: Environment):
    questions = []
    for sub_subject_name, sub_subject_data in subject_data['sub_subjects'].items():
        for q in sub_subject_data.get('questions', []):
            # 이미지 절대 경로
            image_abs_path = os.path.abspath(os.path.join(base_dir, q['image_path']))
            if not os.path.exists(image_abs_path):
                print(f"  경고: 이미지 없음 - {image_abs_path}")
                image_abs_path = ''

            answer_num = q.get('answer')
            answer_str = ANSWER_CIRCLES.get(answer_num, str(answer_num)) if answer_num else '?'

            questions.append({
                'year': q['year'],
                'question_num': q['question_num'],
                'sub_subject': sub_subject_name,
                'image_abs_path': f'file://{image_abs_path}' if image_abs_path else '',
                'answer_str': answer_str,
                'expl_claude_html': md_to_html(q.get('expl_claude', '')),
                'expl_gemini_html': md_to_html(q.get('expl_gemini', '')),
            })

    print(f"  {subject_name}: {len(questions)}개 문항 렌더링 중...")

    template = env.get_template('subject_pdf.html')
    html_content = template.render(
        subject_name=subject_name,
        questions=questions,
    )

    HTML(string=html_content, base_url=base_dir).write_pdf(output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  -> {output_path} ({size_mb:.1f} MB)")


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'analyze', 'subjects_data.json')
    output_dir = os.path.join(base_dir, 'pdf')
    template_dir = os.path.join(base_dir, 'templates')

    if not os.path.exists(data_path):
        print(f"오류: {data_path} 파일을 찾을 수 없습니다.")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    with open(data_path, 'r', encoding='utf-8') as f:
        subjects_data = json.load(f)

    env = Environment(loader=FileSystemLoader(template_dir))

    for subject_name, subject_data in subjects_data.items():
        safe_name = make_safe_filename(subject_name)
        output_path = os.path.join(output_dir, f'{safe_name}.pdf')
        print(f"\n[{subject_name}]")
        try:
            generate_subject_pdf(subject_name, subject_data, output_path, base_dir, env)
        except Exception as e:
            print(f"  오류: {e}")
            raise

    print(f"\n완료! {output_dir}/ 에 {len(subjects_data)}개 PDF 생성")


if __name__ == '__main__':
    main()
