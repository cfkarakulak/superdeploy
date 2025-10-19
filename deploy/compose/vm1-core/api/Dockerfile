FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    psycopg2-binary==2.9.9 \
    pika==1.3.2 \
    sqlalchemy==2.0.23 \
    pydantic==2.5.0 \
    python-multipart==0.0.6

# Copy application
COPY app.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
