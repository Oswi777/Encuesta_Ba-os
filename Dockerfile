FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Reqs primero para cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
COPY . .

# Usuario sin privilegios
RUN useradd -ms /bin/sh appuser && \
    mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Entrypoint que siembra BD la primera vez
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Gunicorn con threads (bueno para SQLite)
CMD ["gunicorn", "-w", "2", "-k", "gthread", "--threads", "8", "-b", "0.0.0.0:8000", "wsgi:application"]
