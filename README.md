# 정보시스템감리사 기출문제 PDF → HTML 변환 시스템

2021년~2024년 정보시스템감리사 기출문제 PDF를 연도별/과목별로 구조화된 HTML 문서로 자동 변환하는 시스템

## 🎯 주요 기능

- **PDF 자동 분석**: PyMuPDF를 사용한 문항 구조 인식 및 메타데이터 추출
- **고품질 이미지 크롭**: 문항별 300 DPI 고해상도 이미지 생성
- **반응형 웹 인터페이스**: 연도별/과목별 필터링 및 모달 확대 기능
- **CLI 인터페이스**: 단계별/연도별 선택적 처리 가능

## 📁 프로젝트 구조

```
auditor/
├── source/              # 원본 PDF 파일
│   ├── 2021_auditor.pdf
│   ├── 2022_auditor.pdf
│   ├── 2023_auditor.pdf
│   └── 2024_auditor.pdf
├── 2021/               # 2021년 처리 결과
│   ├── 2021_data.json  # 메타데이터
│   └── question/       # 문항 이미지들
├── 2022/               # 2022년 처리 결과
├── 2023/               # 2023년 처리 결과
├── 2024/               # 2024년 처리 결과
├── scripts/            # 처리 스크립트
│   ├── pdf_analyzer.py    # PDF 분석 모듈
│   ├── question_cropper.py # 문항 크롭 모듈
│   └── html_generator.py  # HTML 생성 모듈
├── templates/          # HTML 템플릿
│   └── index.html
├── index.html          # 최종 HTML 출력물
├── main.py            # CLI 메인 스크립트
└── requirements.txt   # 패키지 의존성
```

## 🚀 설치 및 실행

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 2. 사용법

```bash
# 전체 연도 모든 단계 처리
python main.py --all

# 특정 연도만 처리
python main.py --year 2024

# 단계별 처리
python main.py --year 2024 --step 1  # PDF 분석만
python main.py --year 2024 --step 2  # 문항 크롭만
python main.py --step 3              # HTML 생성만
```

### 3. 결과 확인
처리 완료 후 `index.html` 파일을 웹 브라우저에서 열어 확인

## 📊 처리 결과

- **총 처리 문항**: 467개 (2021년: 107개, 2022-2024년: 각 120개)
- **과목 분류**: 
  - 감리 및 사업관리 (1-25번)
  - 소프트웨어 공학 (26-50번)
  - 데이터베이스 (51-75번)
  - 시스템 분석설계 (76-100번)
  - 정보통신개론 (101-120번)
- **이미지 품질**: 300 DPI 고해상도
- **파일 크기**: 연도별 약 60MB

## 🛠 기술 스택

- **Python 3.9+**
- **PyMuPDF 1.26+**: PDF 분석 및 크롭
- **Jinja2 3.1+**: HTML 템플릿 엔진
- **BeautifulSoup4 4.13+**: HTML 조작
- **NumPy 2.3+**: 수치 연산
- **Pillow 11.2+**: 이미지 처리

## 🎨 웹 인터페이스 기능

- **연도별 탭 네비게이션**: 2021-2024년 간편 전환
- **과목별 필터링**: 5개 과목 개별 필터
- **문항 이미지 확대**: 클릭으로 모달 팝업
- **반응형 디자인**: 모바일/태블릿 최적화
- **통계 정보**: 연도별 문항 수, 과목 수, 페이지 수

## ⚡ 성능

- **PDF 분석**: 페이지당 평균 1.5초
- **문항 크롭**: 문항당 평균 0.04초
- **HTML 생성**: 연도당 평균 0.01초
- **메모리 사용량**: 최대 1GB 이내

## 🔧 문제 해결

### 크롭 영역 경고 메시지
- 일부 문항에서 "유효하지 않은 크롭 영역" 경고가 나타날 수 있음
- 자동으로 기본 영역으로 대체하여 처리 계속
- 문항 이미지는 정상적으로 생성됨

### PDF 파일 누락
- `source/` 디렉토리에 PDF 파일 확인
- 파일명 형식: `{year}_auditor.pdf`
