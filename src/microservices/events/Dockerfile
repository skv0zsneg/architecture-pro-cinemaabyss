FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./events
CMD ["sh", "-c", "exec uvicorn events.main:app --host 0.0.0.0 --port ${PORT:-8082}"]
