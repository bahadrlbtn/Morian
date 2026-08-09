FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system morian && adduser --system --ingroup morian --uid 10001 morian
COPY --chown=morian:morian app ./app
COPY --chown=morian:morian docs ./docs
COPY --chown=morian:morian scripts ./scripts
RUN mkdir -p /app/data && chown -R morian:morian /app/data
USER morian
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready',timeout=3)"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
