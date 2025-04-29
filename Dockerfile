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

# Default APP_MODE is "server"
ENV APP_MODE=server

# At container start, decide what to run based on APP_MODE
ENTRYPOINT ["sh", "-c", "\
    echo Running container in APP_MODE=$APP_MODE; \
    if [ \"$APP_MODE\" = \"server\" ]; then \
        uvicorn services.api.fastapi_server:app --host 0.0.0.0 --port 8000; \
    elif [ \"$APP_MODE\" = \"cron\" ]; then \
        python main.py; \
    else \
        echo '❌ Unknown APP_MODE value: $APP_MODE'; exit 1; \
    fi \
"]
