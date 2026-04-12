# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 정보시스템감리사 기출문제(2021-2025년) PDF를 분석하여 문항별 이미지를 추출하고, 연도별/과목별로 구조화된 반응형 웹 인터페이스를 생성하는 시스템입니다. 정답 추출 및 AI 해설(Claude/Gemini/GPT) 주입 기능을 포함합니다.

## 주요 명령어

### 환경 설정
```bash
pip install -r requirements.txt
```

### 메인 처리 파이프라인
```bash
python main.py --all                    # 전체 연도 모든 단계
python main.py --year 2025              # 특정 연도 전체 처리
python main.py --year 2025 --step 1    # PDF 분석만
python main.py --year 2025 --step 2    # 문항 크롭만
python main.py --step 3                # HTML 생성만 (index.html)
```

### 개별 스크립트 직접 실행
```bash
python scripts/html_generator.py        # index.html + subjects.html 생성
python scripts/subject_aggregator.py    # analyze/subjects_data.json 재생성
python scripts/answer_key_extractor.py  # 정답 PDF에서 answer_key.json 추출
python scripts/inject_answer_keys.py    # answer_key.json → data.json 주입
python scripts/apply_expl_staging.py    # expl_staging/ → data.json 해설 주입
python scripts/expl_progress.py         # 해설 생성 진행률 확인
```

### 해설 진행 상황 확인
```bash
python scripts/expl_progress.py         # 전체 진행률
python scripts/expl_progress.py --ai gemini --year 2025  # 특정 AI/연도 확인
```

## 아키텍처

### 처리 파이프라인 (전체 흐름)

```
[PDF 파일] → Step1: pdf_analyzer.py → {year}_data.json (bbox 메타데이터)
           → Step2: question_cropper.py → {year}/question/{year}_{num}.png
           → Step3: html_generator.py → index.html, subjects.html

[정답 PDF] → answer_key_extractor.py → {year}_answer_key.json
           → inject_answer_keys.py → {year}_data.json (answer 필드 추가)

[AI 해설]  → expl_staging/{ai}/{year}/{num}.txt (외부에서 수동으로 생성)
           → apply_expl_staging.py → {year}_data.json (expl_* 필드 추가)

[통합]     → subject_aggregator.py → analyze/subjects_data.json
           → html_generator.py → subjects.html
```

### 핵심 컴포넌트

**`main.py`** — CLI 진입점. `AuditorPDFProcessor` 클래스가 Step1~3 오케스트레이션. 지원 연도: 2021-2025.

**`scripts/pdf_analyzer.py`** — `PDFAnalyzer` 클래스. 연도별 다른 레이아웃을 적응형으로 처리:
- 2021-2024: 2컬럼 세로 레이아웃
- 2025: 4컬럼 가로(landscape) 레이아웃
- 연도별 컬럼 위치 상수 (`standard_column_positions`, line 29-34)
- 과목 분류: 문항 번호 기반 (1-25 감리, 26-50 SW공학, 51-75 DB, 76-100 시스템구조, 101-120 보안)

**`scripts/question_cropper.py`** — 300 DPI로 PNG 추출. 크롭 전후 120문항 완성도 검증.

**`scripts/html_generator.py`** — `index.html`(연도별 탭)과 `subjects.html`(과목별 모달+해설) 생성. `--step 3`은 `index.html`만 생성하므로 `subjects.html` 재생성은 이 스크립트를 직접 실행해야 함.

**`scripts/subject_aggregator.py`** — `DetailedSubjectAggregator`. `analyze/0.시험범위 및 기출분석.md`를 파싱하여 `analyze/subjects_data.json` 생성.

**`scripts/answer_key_extractor.py`** — 연도별 PDF 구조가 달라 전략이 다름:
- 2021-2023: bold 텍스트 추출 방식
- 2024: 표(table) 파싱
- 2025: 가로 방향 4컬럼, T12 폰트 weight 감지

**`scripts/inject_answer_keys.py`** — `{year}_answer_key.json`의 정답을 `{year}_data.json` 각 문항 객체에 `answer` 필드로 주입. `expl_claude/expl_gemini/expl_gpt` 빈 필드도 이 때 초기화.

**`scripts/apply_expl_staging.py`** — `expl_staging/{ai}/{year}/{num}.txt` 파일을 읽어 해당 문항의 `expl_{ai}` 필드에 주입. `--force` 플래그로 기존 내용 덮어쓰기 가능.

**`scripts/expl_progress.py`** — `expl_staging/` 디렉토리 파일 수를 기준으로 진행률 집계.

### 문항 데이터 구조 (`{year}/{year}_data.json`)

```json
{
  "question_num": 1,
  "subject": "감리 및 사업관리",
  "bbox": [x1, y1, x2, y2],
  "column": "left|right",
  "verified": true,
  "recovered": false,
  "question_text": "문항 텍스트...",
  "question_choice": ["① ...", "② ...", "③ ...", "④ ..."],
  "answer": 4,
  "expl_claude": "마크다운 형식 해설...",
  "expl_gemini": "마크다운 형식 해설...",
  "expl_gpt": ""
}
```

### AI 해설 스테이징 구조

```
expl_staging/
├── claude/
│   ├── 2021/{1..120}.txt
│   ├── 2022/{1..120}.txt
│   └── ... (2025까지, 총 600개 완료)
└── gemini/
    └── ... (동일 구조, 총 600개 완료)
```

해설 텍스트는 마크다운 형식(`**bold**`, `* bullet`)으로 저장되며, `subjects.html` 모달에서 `marked.js`를 통해 HTML로 렌더링됨.

### 통합 데이터 구조 (`analyze/subjects_data.json`)

```json
{
  "1. 감리 및 사업관리": {
    "analysis": "영역별 출제경향 분석...",
    "sub_subjects": {
      "1.1 프로젝트 관리 일반": [
        {
          "year": 2024,
          "question_num": 1,
          "image_path": "2024/question/2024_1.png",
          "answer": 4,
          "expl_claude": "...",
          "expl_gemini": "...",
          "expl_gpt": ""
        }
      ]
    }
  }
}
```

## 파일 구조 (주요 항목)

```
auditor/
├── source/                         # 원본 PDF (2021-2025_auditor.pdf)
├── {year}/                         # 연도별 처리 결과
│   ├── {year}_data.json            # 문항 메타데이터 + 정답 + 해설
│   ├── {year}_answer_key.json      # 정답 키 (answer_key_extractor 산출물)
│   └── question/                   # 크롭된 PNG 이미지 (120개)
├── analyze/
│   ├── 0.시험범위 및 기출분석.md   # subject_aggregator 입력 소스
│   ├── {1-5}.{과목명}.md           # 과목별 분석 마크다운
│   └── subjects_data.json          # subjects.html 렌더링 소스
├── expl_staging/                   # AI 해설 스테이징 (apply 전 보관)
├── templates/                      # Jinja2 HTML 템플릿
├── scripts/                        # 처리 모듈
├── main.py                         # CLI (Step 1-3)
├── index.html                      # 생성된 연도별 메인 화면
└── subjects.html                   # 생성된 과목별 뷰 (해설 포함)
```

## 개발 노트

### subjects.html 재생성 시 주의
`python main.py --step 3`은 `index.html`만 재생성함. `subjects.html`까지 재생성하려면:
```bash
python scripts/html_generator.py
```

### 연도별 레이아웃 차이
- **2021**: 107개 문항 (특수 케이스, 보간 처리 포함)
- **2022-2025**: 120개 문항
- **2025 특이사항**: 가로 방향 4컬럼 PDF, `standard_column_positions`에 별도 설정 필요

### 해설 마크다운 렌더링
해설 텍스트는 raw 마크다운으로 저장됨. `subjects.html`의 모달에서 `marked.js` CDN으로 렌더링. 신규 템플릿 수정 시 `para.innerHTML = marked.parse(text)` 패턴 유지 필요.

### 처리 성능
- PDF 분석: 페이지당 ~1.5초
- 문항 크롭: 문항당 ~0.04초
- HTML 생성: 연도당 ~0.01초
