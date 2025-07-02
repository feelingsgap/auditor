# 정보시스템감리사 기출문제 PDF → HTML 변환 시스템 PRD

## 1. 프로젝트 개요

### 목적

정보시스템감리사 기출문제 PDF 파일을 연도별/과목별로 구조화된 HTML 문서로 자동 변환하는 시스템 개발

### 범위

-   2021년~2024년 정보시스템감리사 기출문제 PDF 처리
-   연도별 120문제 × 5과목 분류
-   웹에서 열람 가능한 HTML 형태로 출력

## 2. 기술 스택 (macOS 환경)

### 개발 환경

-   **OS**: macOS (darwin 25.0.0)
-   **언어**: Python 3.9+
-   **패키지 관리**: pip

### 핵심 라이브러리

```python
# PDF 처리 (핵심)
PyMuPDF==1.23.0  # PDF 직접 크롭, 텍스트 추출

# HTML 생성 (핵심)
Jinja2==3.1.0  # 템플릿 엔진
beautifulsoup4==4.12.0  # HTML 조작

# 데이터 처리 (핵심)
numpy==1.24.0  # 수치 연산

# 선택적 라이브러리
pdf2image==1.16.3  # 페이지 이미지 생성용 (선택적)
Pillow==10.0.0  # 이미지 조작 (선택적)
pandas==2.0.0  # 데이터 조작 (선택적)
opencv-python==4.8.0  # 이미지 분석 (선택적)
pytesseract==0.3.10  # OCR (선택적)
```

### 시스템 의존성

```bash
# Homebrew로 설치 (선택적)
brew install poppler    # pdf2image 사용시 필요
brew install tesseract  # OCR 사용시 필요
```

## 3. 시스템 아키텍처

### 디렉토리 구조

```
auditor/
├── source/              # 원본 PDF 파일
├── {year}/             # 연도별 처리 결과
│   ├── {year}_data.json  # 문항 메타데이터
│   ├── page/            # 전체 페이지 이미지 (선택적)
│   │   └── {year}_{page}.png
│   └── question/        # 크롭된 문항 이미지
│       └── {year}_{num}.png
├── index.html          # 메인 HTML 파일
├── scripts/            # 처리 스크립트
└── templates/          # HTML 템플릿
```

### 처리 파이프라인

```
Step 1: PDF 분석 및 메타데이터 추출
Step 2: PDF에서 직접 문항 크롭
Step 3: 페이지 이미지 생성 (선택적, HTML 표시용)
Step 4: HTML 생성
```

## 4. 기능 요구사항

### 4.1 PDF 분석 모듈 (Step 1)

**입력**: PDF 파일 (`{year}_auditor.pdf`)
**출력**: JSON 메타데이터 (`{year}_data.json`)

**기능**:

-   PDF 페이지 수 확인 (1페이지 유의사항 제외)
-   좌우 단락 구조 인식
-   문항 번호 패턴 매칭 (1~120번)
-   각 문항의 바운딩 박스 좌표 계산
-   과목별 분류 (감리 및 사업관리 1-25, 소프트웨어 공학 26-50, ...)

**JSON 스키마**:

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
          "column": "left"
        }
      ]
    }
  ]
}
```

### 4.2 문항 크롭 모듈 (Step 2)

**입력**: PDF 파일 + JSON 메타데이터
**출력**: 크롭된 문항 이미지

**기능**:

-   PyMuPDF를 사용한 PDF 직접 크롭
-   메모리 효율적 처리
-   고해상도 출력 (300 DPI)
-   파일명 규칙: `{year}_{question_num}.png`

**구현 예시**:

```python
import fitz  # PyMuPDF

def crop_question_directly(pdf_path, page_num, bbox, output_path):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]  # 0-based index

    # 패딩 추가
    x1, y1, x2, y2 = bbox
    rect = fitz.Rect(x1-10, y1-10, x2+10, y2+10)

    # 300 DPI 해상도
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    pix.save(output_path)

    doc.close()
```

### 4.3 페이지 이미지 생성 모듈 (Step 3 - 선택적)

**입력**: PDF 파일
**출력**: 페이지별 PNG 이미지

**기능**:

-   HTML 표시용 전체 페이지 이미지 생성
-   PDF 2페이지부터 마지막 페이지까지 변환
-   고해상도 PNG 생성 (300 DPI)
-   파일명 규칙: `{year}_{page}.png`

**설정**:

```python
PDF_TO_IMAGE_CONFIG = {
    'dpi': 300,
    'format': 'PNG',
    'first_page': 2,  # 1페이지 제외
    'thread_count': 4
}
```

### 4.4 HTML 생성 모듈 (Step 4)

**입력**: JSON 메타데이터 + 이미지 파일들
**출력**: HTML 파일

**기능**:

-   연도별/과목별 네비게이션
-   문항 이미지 표시
-   원본 페이지 이미지 링크
-   반응형 웹 디자인
-   검색 기능 (선택사항)

## 5. 비기능 요구사항

### 5.1 성능

-   PDF 분석: 페이지당 평균 2초 이내
-   문항 크롭: 문항당 평균 0.05초 이내 (메모리 효율적)
-   페이지 이미지 생성: 페이지당 평균 1초 이내 (선택적)
-   HTML 생성: 연도당 평균 3초 이내

### 5.2 메모리 사용량

-   최대 메모리 사용량: 2GB 이내 (맥북 환경 고려)
-   페이지별 순차 처리로 메모리 효율성 확보

### 5.3 저장 공간

-   연도별 예상 용량: 약 60MB (문항 이미지만), 약 100MB (페이지 이미지 포함시)
-   전체 프로젝트: 약 300MB (문항 이미지만), 약 500MB (페이지 이미지 포함시)

## 6. 사용자 인터페이스

### 6.1 CLI 인터페이스

```bash
# 전체 처리
python main.py --all

# 특정 연도 처리
python main.py --year 2024

# 단계별 처리
python main.py --step 1 --year 2024  # 분석만
python main.py --step 2 --year 2024  # 문항 크롭
python main.py --step 3 --year 2024  # 페이지 이미지 생성 (선택적)
python main.py --step 4 --year 2024  # HTML 생성

# 페이지 이미지 생성 옵션
python main.py --year 2024 --include-pages  # 페이지 이미지 포함
```

### 6.2 웹 인터페이스 (HTML)

-   연도별 탭 네비게이션
-   과목별 필터링
-   문항 번호 점프 기능
-   원본 페이지 보기 모달

## 7. 예외 처리

### 7.1 PDF 관련

-   파일 손상: 에러 로그 기록 후 건너뛰기
-   비표준 레이아웃: 수동 검증 모드 제공
-   페이지 누락: 경고 메시지 출력

### 7.2 이미지 처리

-   메모리 부족: 배치 크기 자동 조정
-   크롭 영역 오류: 기본 영역으로 대체

## 8. 테스트 계획

### 8.1 단위 테스트

-   PDF 분석 정확도 검증
-   이미지 크롭 좌표 검증
-   JSON 스키마 유효성 검사

### 8.2 통합 테스트

-   전체 파이프라인 실행
-   연도별 결과물 품질 검증
-   HTML 렌더링 확인

## 9. 구현 우선순위

### Phase 1 (핵심 기능)

1. PDF 분석 및 메타데이터 추출
2. PDF 직접 크롭 기능 구현
3. 간단한 HTML 생성

### Phase 2 (고도화)

1. 정확한 문항 경계 인식 알고리즘 개선
2. 과목별 분류 자동화
3. 페이지 이미지 생성 기능 추가 (선택적)
4. 반응형 웹 디자인

### Phase 3 (부가 기능)

1. 검색 기능
2. 즐겨찾기 기능
3. 인쇄 최적화

## 10. 위험 요소 및 대응

### 위험 요소

-   PDF 레이아웃 연도별 차이
-   문항 경계 인식 정확도
-   대용량 이미지 처리 성능

### 대응 방안

-   연도별 설정 파일 분리
-   수동 보정 인터페이스 제공
-   배치 처리 및 병렬 처리 활용
