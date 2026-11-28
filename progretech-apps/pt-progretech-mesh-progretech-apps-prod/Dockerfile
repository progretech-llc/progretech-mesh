FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    APP_ENV=production \
    FLASK_DEBUG=0

WORKDIR /app

RUN addgroup --system mesh && adduser --system --ingroup mesh mesh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R mesh:mesh /app
USER mesh

# One process is intentional while live WebSocket/session state remains process-local.
# Horizontal scaling requires a shared ephemeral routing layer first.
CMD exec gunicorn \
    --bind ":${PORT}" \
    --workers 1 \
    --threads 80 \
    --timeout 0 \
    --access-logfile - \
    --error-logfile - \
    main:app
