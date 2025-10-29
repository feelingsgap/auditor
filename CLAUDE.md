# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 정보시스템감리사 기출문제(2021-2024년) PDF를 분석하여 문항별 이미지를 추출하고, 연도별/과목별로 구조화된 반응형 웹 인터페이스를 생성하는 시스템입니다.

## 주요 명령어

### 환경 설정
```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 메인 처리 명령어
```bash
# 전체 연도 모든 단계 처리
python main.py --all

# 특정 연도만 처리 (분석 + 크롭 + HTML)
python main.py --year 2024

# 단계별 처리
python main.py --year 2024 --step 1  # PDF 분석만
python main.py --year 2024 --step 2  # 문항 크롭만
python main.py --step 3              # HTML 생성만
```

### 개별 스크립트 실행
```bash
# PDF 분석 직접 실행
python scripts/pdf_analyzer.py

# 문항 크롭 직접 실행
python scripts/question_cropper.py

# HTML 생성 직접 실행
python scripts/html_generator.py

# 과목별 통합 데이터 생성
python scripts/subject_aggregator.py
```

## 아키텍처

### 처리 파이프라인

시스템은 3단계 파이프라인으로 구성됩니다:

1. **PDF 분석** (`scripts/pdf_analyzer.py`): PDF에서 문항 메타데이터와 바운딩 박스 추출
2. **문항 크롭** (`scripts/question_cropper.py`): 고해상도 문항 이미지 생성
3. **HTML 생성** (`scripts/html_generator.py`): Jinja2 템플릿을 사용한 반응형 웹 인터페이스 생성

### 핵심 컴포넌트

**메인 컨트롤러** (`main.py`):
- `AuditorPDFProcessor` 클래스가 전체 파이프라인 오케스트레이션
- CLI 인수 파싱 및 오류 처리
- 연도별 처리 및 검증 관리
- 처리 로그 저장 (`{year}_processing_log.json`)

**PDF 분석** (`scripts/pdf_analyzer.py`):
- `PDFAnalyzer` 클래스: 연도별 적응형 레이아웃 감지
- 복합 문항 감지 알고리즘과 검증
- 과목 분류 (5개 과목: 감리 및 사업관리, 소프트웨어 공학, 데이터베이스, 시스템 구조, 보안)
- 누락 문항 보간 및 페이지 균형 조정
- 연도별 표준 컬럼 위치 및 폭 정의 (`standard_column_positions`, `standard_column_widths`)

**문항 크롭** (`scripts/question_cropper.py`):
- `QuestionCropper` 클래스: 고해상도(300 DPI) 이미지 추출
- PDF에서 PNG로 직접 변환 (패딩 및 경계 검증 포함)
- 크롭 전후 메타데이터 검증 (120개 문항 완성도 확인)
- 실패한 문항 추적 및 재시도 로직

**HTML 생성** (`scripts/html_generator.py`):
- `HTMLGenerator` 클래스: Jinja2 템플릿 사용
- 연도별/과목별 HTML 생성 (`index.html`, `subjects.html`)
- 반응형 웹 인터페이스 (연도별 탭, 과목별 필터링)
- 모달 이미지 확대 기능

**과목별 통합** (`scripts/subject_aggregator.py`):
- `DetailedSubjectAggregator` 클래스: 마크다운 분석 및 데이터 통합
- `analyze/0.시험범위 및 기출분석.md` 파싱
- 세부 범위별 문항 매핑 (OrderedDict로 순서 유지)
- `analyze/subjects_data.json` 생성

### 데이터 구조

**메타데이터 형식** (`{year}/{year}_data.json`):
```json
{
  "year": 2024,
  "total_questions": 120,
  "pages": [
    {
      "page_num": 2,
      "questions": [
        {
          "question_num": 1,
          "subject": "감리 및 사업관리",
          "bbox": [x1, y1, x2, y2],
          "column": "left|right",
          "verified": true,
          "recovered": false
        }
      ]
    }
  ]
}
```

**통합 데이터 형식** (`analyze/subjects_data.json`):
```json
{
  "1. 감리 및 사업관리": {
    "analysis": "영역별 출제경향 분석...",
    "sub_subjects": {
      "1.1 프로젝트 관리 일반": [
        {
          "year": 2024,
          "question_num": 1,
          "image_path": "2024/question/2024_1.png"
        }
      ]
    }
  }
}
```

### 연도별 설정

시스템은 연도별로 다른 PDF 레이아웃을 처리합니다:

- **2021년**: 107개 문항 (다른 연도와 상이)
- **2022-2024년**: 각 120개 문항
- 연도별 컬럼 레이아웃 및 위치 자동 조정
- 적응형 감지 알고리즘이 레이아웃 변화에 대응

**연도별 표준 컬럼 위치** (`pdf_analyzer.py:29-34`):
```python
self.standard_column_positions = {
    2021: {"left": 57, "right": 375, "gap": 25},
    2022: {"left": 57, "right": 376, "gap": 25},
    2023: {"left": 56, "right": 375, "gap": 25},
    2024: {"left": 50, "right": 309, "gap": 20}
}
```

### 파일 구조

```
auditor/
├── source/                     # 원본 PDF 파일
│   └── {year}_auditor.pdf
├── {year}/                     # 연도별 처리 결과
│   ├── {year}_data.json        # 문항 메타데이터
│   ├── {year}_processing_log.json  # 처리 로그
│   └── question/               # 크롭된 문항 이미지
│       └── {year}_{num}.png
├── analyze/                    # 시험 분석 데이터
│   ├── 0.시험범위 및 기출분석.md
│   ├── 1.감리 및 사업관리.md
│   ├── 2.소프트웨어공학.md
│   ├── 3.데이터베이스.md
│   ├── 4.시스템구조.md
│   ├── 5.보안.md
│   └── subjects_data.json      # 통합 데이터
├── templates/                  # Jinja2 HTML 템플릿
│   ├── index.html              # 연도별 메인 템플릿
│   └── subjects.html           # 과목별 템플릿
├── scripts/                    # 처리 모듈
│   ├── pdf_analyzer.py
│   ├── question_cropper.py
│   ├── html_generator.py
│   ├── subject_aggregator.py
│   ├── html_to_markdown.py
│   └── page_mapping_validator.py
├── main.py                     # CLI 메인 스크립트
├── index.html                  # 연도별 최종 HTML
├── subjects.html               # 과목별 최종 HTML
└── requirements.txt
```

## 개발 노트

### 개별 컴포넌트 테스트
각 스크립트는 독립적으로 실행 가능합니다 (`__main__` 섹션 수정):
- PDF 분석: `pdf_analyzer.py`의 `__main__` 섹션 수정
- 문항 크롭: `question_cropper.py`의 `__main__` 섹션 수정
- HTML 생성: `html_generator.py`의 `__main__` 섹션 수정
- 과목별 통합: `subject_aggregator.py`의 `__main__` 섹션 수정

### 오류 처리
시스템은 다음 항목에 대한 포괄적인 오류 처리를 포함합니다:
- PDF 파일 누락 (`check_pdf_exists`)
- 잘못된 문항 감지 (메타데이터 검증)
- 이미지 크롭 실패 (저해상도 재시도)
- 템플릿 렌더링 오류
- 크롭 전후 완성도 검증 (`validate_question_completeness`)

### 성능 특성
- PDF 분석: 페이지당 ~1.5초
- 문항 크롭: 문항당 ~0.04초
- HTML 생성: 연도당 ~0.01초
- 메모리 사용량: 1GB 이하 유지

### 한글 지원
모든 텍스트 처리는 파이프라인 전체에서 UTF-8 인코딩을 사용하여 한글 문자를 올바르게 처리합니다. `main.py`의 상단에서 UTF-8 인코딩을 강제합니다 (1-5행).

### 완성도 검증
시스템은 처리 후 자동으로 완성도를 검증합니다:
- 메타데이터 검증: 120개 문항 모두 존재 확인
- 이미지 파일 검증: 120개 PNG 파일 모두 생성 확인
- 검증 실패시 HTML 생성 건너뜀

### 과목 분류 체계
문항 번호 기반 자동 분류 (`pdf_analyzer.py:9-15`):
- 1-25번: 감리 및 사업관리
- 26-50번: 소프트웨어 공학
- 51-75번: 데이터베이스
- 76-100번: 시스템 구조
- 101-120번: 보안

### 추가 유틸리티
- `page_mapping_validator.py`: 페이지 매핑 검증
- `html_to_markdown.py`: HTML을 마크다운으로 변환
