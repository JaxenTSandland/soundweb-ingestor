FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt --verbose

# Copy the rest of your code
COPY . .

# Run your FastAPI app
CMD ["uvicorn", "services.api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
