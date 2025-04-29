FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Default behavior is to run the FastAPI server, but allow override
ENTRYPOINT ["sh", "-c"]
CMD ["uvicorn services.api.fastapi_server:app --host 0.0.0.0 --port 8000"]