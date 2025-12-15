# Multi-stage build for MRZ Scanner API
FROM python:3.11-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies: Tesseract OCR, Poppler (for PDF), curl (for health checks), and system libraries
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    curl \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy application files
# Note: Build context should be the project root, so we copy from root and api/
COPY mrz_scanner.py .
COPY api/app.py .
COPY .env.example .env.example

# Copy MRZ language model (required for fastmrz library)
COPY api/mrz.traineddata /usr/share/tesseract-ocr/5/tessdata/mrz.traineddata

# Create .env file with default values (can be overridden via environment variables)
# Set TESSERACT_PATH to system tesseract location
RUN echo "TESSERACT_PATH=/usr/bin/tesseract" > .env && \
    echo "PDF_DPI=300" >> .env && \
    echo "OCR_PSM_MODE=6" >> .env && \
    echo "MAX_PAGES_DEFAULT=10" >> .env

# Set TESSDATA_PREFIX environment variable for tesseract language models
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Expose port
EXPOSE 5000

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

