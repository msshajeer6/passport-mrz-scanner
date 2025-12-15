# Passport MRZ Scanner

Fast MRZ extraction from images and PDFs, with optional API + Docker deployment and start-page hints for big speedups.

## Highlights
- Images (JPG/PNG/AVIF) and PDFs (multi-page)
- Start-page hint (`--start-page` / `start_page`) to jump directly to the likely MRZ page
- Parallel page processing for PDFs (3+ pages)
- Processing time reported in all outputs
- Primary PDF renderer: **PyMuPDF (fitz)** (no system deps); Poppler/pdf2image is a fallback only

## Install (CLI)
```bash
python -m venv venv
.\venv\Scripts\activate            # Windows
# source venv/bin/activate         # macOS/Linux
pip install -r requirements.txt
cp .env.example .env  # or Copy-Item .env.example .env (Windows)
```

## Key environment variables
```env
# OCR
TESSERACT_PATH=                    # leave empty if tesseract is on PATH
OCR_PSM_MODE=6                     # default PSM
OCR_PSM_MODE_FAST=11               # used for start_page fast path

# PDF rendering
PDF_DPI=300                        # default DPI
PDF_DPI_FAST=200                   # used for start_page fast path
MAX_IMAGE_DIMENSION=4000           # resize safeguard for huge images
MAX_PAGES_DEFAULT=10               # default page limit if --max-pages not set

# API (optional)
API_KEYS="key1 key2"               # space-separated keys
RATE_LIMIT_PER_KEY="100 per hour"
```

## CLI usage
```bash
# Image
python mrz_scanner.py passport_sample.jpg --format json

# PDF (auto pages)
python mrz_scanner.py document.pdf --format json

# PDF with MRZ page hint (faster)
python mrz_scanner.py document.pdf --format json --start-page 3

# Limit pages
python mrz_scanner.py document.pdf --format json --max-pages 5
```

## API (Docker)
Build and run:
```bash
docker build -f api/Dockerfile -t mrz-scanner-api .
docker run -d -p 5000:5000 --name mrz-scanner-api \
  -e API_KEYS="test-key-1 test-key-2" \
  -e RATE_LIMIT_PER_KEY="100 per hour" \
  mrz-scanner-api
```

Endpoints:
- `POST /scan/file`    – multipart `file`, optional `max_pages`, `start_page` (PDFs)
- `POST /scan/base64`  – JSON `{ file, filename, max_pages?, start_page? }`
- `POST /scan/url`     – JSON `{ url, max_pages?, start_page? }`

Auth (if enabled): `X-API-Key: <key>` or `Authorization: Bearer <key>`.

Swagger UI: `http://localhost:5000/api-docs`

## Performance tips
- If you know the MRZ page, use `start_page` (often 75–80% faster on multi-page PDFs).
- Keep `PDF_DPI_FAST` at 200–250 for speed when start_page is provided.
- `MAX_IMAGE_DIMENSION` avoids downscaling typical A4 @300 DPI; raise if MRZ is tiny.

## Optional MRZ language data
The scanner works without `mrz.traineddata` (fastmrz has built-in models). For fallback Tesseract OCR with MRZ language, place `mrz.traineddata` in Tesseract tessdata. The Docker image already bundles it at `/usr/share/tesseract-ocr/5/tessdata/mrz.traineddata`.

## Project layout
```
mrz_scanner.py           # CLI
requirements.txt         # CLI deps
api/                     # Flask API + Docker
  app.py, Dockerfile, requirements.txt, README.md
```

## Troubleshooting
- Tesseract not found: set `TESSERACT_PATH` or add to PATH.
- PDF issues: PyMuPDF is primary; Poppler is only a fallback (requires `pdftoppm` if used).
- No MRZ found: check image quality/rotation; try `start_page` for PDFs; review `processing_time_seconds`.
