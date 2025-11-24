# GEMINI.md

## 프로젝트 개요

이 프로젝트는 정보시스템감리사 기출문제 PDF 파일을 분석하여, 연도별/과목별로 문제를 볼 수 있는 대화형 HTML 페이지를 생성하는 자동화 시스템입니다.

전체 파이프라인은 `main.py`에 의해 관리되며, 다음과 같은 주요 단계로 구성됩니다:

1.  **분석 (Analysis)**: PDF 레이아웃 분석 및 메타데이터 추출 (`pdf_analyzer.py`)
2.  **텍스트 추출 (Text Extraction)**: 문제 텍스트 및 선택지 추출 (`text_extractor.py`)
3.  **크롭 (Cropping)**: 문항 이미지 생성 (`question_cropper.py`)
4.  **검증 (Validation)**: 120개 문항 완성도 자동 검증
5.  **생성 (Generation)**: 웹페이지 및 분석 리포트 생성 (`html_generator.py`, `subject_aggregator.py`)

## 핵심 워크플로우 및 스크립트 분석

`scripts/` 디렉토리에는 이 파이프라인을 구성하는 핵심 Python 스크립트들이 포함되어 있습니다.

### 0. `main.py` - 중앙 오케스트레이터

-   **목적**: 전체 파이프라인의 실행을 담당하는 진입점(Entry Point)입니다.
-   **핵심 로직**:
    -   `argparse`를 통해 CLI 명령어를 처리합니다 (`--year`, `--step`, `--all` 등).
    -   각 단계(분석, 크롭, HTML 생성)를 순차적으로 실행하고 결과를 로깅합니다.
    -   **자동 검증**: 각 단계 완료 후 120개 문항이 모두 정상적으로 처리되었는지 검증합니다.
-   **사용법**: `python main.py --all` 또는 `python main.py --year 2024`

### 1. `pdf_analyzer.py` - PDF 분석 및 메타데이터 추출

-   **목적**: 원본 PDF 파일의 복잡한 레이아웃을 분석하여 각 문항의 정확한 위치(bounding box), 번호, 과목 정보를 담은 구조적인 `JSON` 데이터를 생성합니다.
-   **핵심 로직**:
    -   **적응형 레이아웃 감지**: 연도별로 미세하게 다른 PDF의 2단(column) 레이아웃을 자동으로 감지합니다.
    -   **강화된 문항 위치 탐색**: 정규표현식, 텍스트 검색, 인접 문항 위치 추정 등을 사용하여 문항 번호의 정확한 좌표를 찾습니다.
    -   **경계 상자 최적화**: 다음 문항의 시작 위치를 고려하여 현재 문항이 잘리지 않도록 크롭 영역을 동적으로 계산합니다.
-   **입력**: `source/{year}_auditor.pdf`
-   **출력**: `{year}/{year}_data.json`

### 2. `text_extractor.py` - 텍스트 및 선택지 추출

-   **목적**: PDF에서 각 문항의 텍스트와 4지선다 선택지를 추출하여 메타데이터에 추가합니다.
-   **핵심 로직**:
    -   `pdf_analyzer.py`가 생성한 bbox 정보를 바탕으로 텍스트를 추출합니다.
    -   정규표현식을 사용하여 문제 지문과 선택지(①, ②, ③, ④)를 분리합니다.
    -   추출된 텍스트는 검색 기능이나 분석 리포트에 활용됩니다.
-   **입력**: `{year}/{year}_data.json`, `source/{year}_auditor.pdf`
-   **출력**: `{year}/{year}_data.json` (텍스트 정보 업데이트)

### 3. `question_cropper.py` - 문항 이미지 생성

-   **목적**: 메타데이터를 기반으로 원본 PDF에서 각 문항을 고해상도 이미지 파일(PNG)로 잘라냅니다.
-   **핵심 로직**:
    -   `PyMuPDF`를 사용하여 PDF의 해당 위치를 300 DPI의 고해상도 이미지로 렌더링합니다.
    -   생성된 이미지는 웹페이지에서 사용자에게 보여집니다.
-   **입력**: `source/{year}_auditor.pdf`, `{year}/{year}_data.json`
-   **출력**: `{year}/question/{year}_{question_num}.png`

### 4. `html_generator.py` - 최종 HTML 페이지 생성

-   **목적**: 분석된 데이터와 이미지를 취합하여 대화형 웹페이지(`index.html`)를 생성합니다.
-   **핵심 로직**:
    -   `Jinja2` 템플릿(`templates/index.html`)을 사용합니다.
    -   연도별 탭, 과목별 필터링, 이미지 모달 팝업 등의 기능을 포함합니다.
-   **입력**: 모든 연도의 `{year}_data.json`, `templates/index.html`
-   **출력**: `index.html`

### 5. `subject_aggregator.py` - 과목별 분석 및 통합

-   **목적**: 마크다운으로 작성된 과목별 분석 내용(`analyze/0.시험범위 및 기출분석.md`)과 기출문제를 매핑하여 통합 데이터를 생성합니다.
-   **핵심 로직**:
    -   분석 마크다운 파일을 파싱하여 과목 체계와 출제 경향을 읽어옵니다.
    -   각 기출문제를 해당 세부 과목(토픽)에 매핑합니다.
-   **입력**: `analyze/*.md`, `{year}_data.json`
-   **출력**: `analyze/subjects_data.json`

### 6. `html_to_markdown.py` - HTML -> Markdown 변환

-   **목적**: 생성된 HTML(`subjects.html`) 내용을 마크다운 형식으로 변환하여 문서화하거나 공유하기 쉽게 만듭니다.
-   **핵심 로직**:
    -   `BeautifulSoup`을 사용하여 HTML 구조를 파싱합니다.
    -   아코디언 구조를 마크다운 헤더 계층으로 변환하고 이미지를 임베딩합니다.
-   **입력**: `subjects.html`
-   **출력**: `subjects.md`

### 7. `page_mapping_validator.py` - (개발자용) 검증 유틸리티

-   **목적**: 분석 결과의 정확성을 검증하고 디버깅하기 위한 도구입니다.
-   **핵심 로직**:
    -   JSON 데이터와 실제 PDF 텍스트 내용을 교차 검증하여 누락이나 오탐을 식별합니다.
-   **참고**: 이 스크립트는 `main.py`를 통해 실행되는 자동화 파이프라인에는 포함되지 않으며, 분석 알고리즘의 정확도를 높이기 위한 목적으로 별도로 사용됩니다.