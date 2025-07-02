# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Korean Information System Auditor exam PDF to HTML conversion system that processes past exam papers (2021-2024) and generates a responsive web interface for study purposes.

## Common Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Main Processing Commands
```bash
# Process all years (all steps)
python main.py --all

# Process specific year only
python main.py --year 2024

# Process specific steps
python main.py --year 2024 --step 1  # PDF analysis only
python main.py --year 2024 --step 2  # Question cropping only
python main.py --step 3              # HTML generation only

# Individual year with HTML generation
python main.py --year 2024           # Steps 1+2+3 for 2024
```

### Individual Script Execution
```bash
# Run PDF analysis directly
python scripts/pdf_analyzer.py

# Run question cropping directly
python scripts/question_cropper.py

# Run HTML generation directly
python scripts/html_generator.py
```

## Architecture

### Core Processing Pipeline
The system follows a 3-step pipeline:

1. **PDF Analysis** (`scripts/pdf_analyzer.py`): Extracts question metadata and bounding boxes from PDF files
2. **Question Cropping** (`scripts/question_cropper.py`): Generates high-resolution question images from PDFs
3. **HTML Generation** (`scripts/html_generator.py`): Creates responsive web interface using Jinja2 templates

### Key Components

**Main Controller** (`main.py`):
- `AuditorPDFProcessor` class orchestrates the entire pipeline
- Handles CLI argument parsing and error handling
- Manages year-specific processing and validation

**PDF Analysis** (`scripts/pdf_analyzer.py`):
- `PDFAnalyzer` class with adaptive layout detection for different years
- Complex question detection algorithms with validation
- Subject classification (5 subjects: 감리 및 사업관리, 소프트웨어 공학, 데이터베이스, 시스템 분석설계, 정보통신개론)
- Missing question interpolation and page balancing

**Question Cropping** (`scripts/question_cropper.py`):
- `QuestionCropper` class for high-DPI image extraction (300 DPI)
- Direct PDF-to-PNG conversion with padding and boundary validation

**HTML Generation** (`scripts/html_generator.py`):
- `HTMLGenerator` class using Jinja2 templating
- Responsive web interface with year/subject filtering
- Modal image viewing functionality

### Data Structure

**Metadata Format** (stored in `{year}/{year}_data.json`):
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
          "verified": true
        }
      ]
    }
  ]
}
```

### Year-Specific Configurations

The system handles different PDF layouts per year:
- **2021**: 107 questions total (different from other years)
- **2022-2024**: 120 questions each
- Different column layouts and positioning per year
- Adaptive detection algorithms adjust to layout variations

### File Organization

- `source/`: Original PDF files (`{year}_auditor.pdf`)
- `{year}/`: Per-year processing results
  - `{year}_data.json`: Question metadata
  - `question/`: Cropped question images (`{year}_{num}.png`)
- `templates/`: Jinja2 HTML templates
- `scripts/`: Core processing modules
- `index.html`: Final generated web interface

## Development Notes

### Testing Individual Components
Each script can be run independently for testing:
- PDF analysis: Modify `__main__` section in `pdf_analyzer.py`
- Question cropping: Modify `__main__` section in `question_cropper.py`  
- HTML generation: Modify `__main__` section in `html_generator.py`

### Error Handling
The system includes comprehensive error handling for:
- Missing PDF files
- Invalid question detection
- Image cropping failures
- Template rendering errors

### Performance Characteristics
- PDF analysis: ~1.5 seconds per page
- Question cropping: ~0.04 seconds per question
- HTML generation: ~0.01 seconds per year
- Memory usage: stays under 1GB

### Korean Language Support
All text processing handles Korean characters properly with UTF-8 encoding throughout the pipeline.