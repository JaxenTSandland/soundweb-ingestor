FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt --verbose

# Copy the rest of the code
COPY . .

# Expose port 8000 for Railway to route traffic
EXPOSE 8000

# Run your FastAPI app
CMD ["uvicorn", "services.api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]