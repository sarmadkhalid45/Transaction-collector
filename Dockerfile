FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/data/transactions.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 appuser && mkdir -p /data && chown -R appuser:appuser /data
COPY --chown=appuser:appuser app.py ./
COPY --chown=appuser:appuser static ./static
USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
