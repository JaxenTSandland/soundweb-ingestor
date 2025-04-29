FROM python:3.11-slim

# Set a working directory
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

# Copy the rest of your app code
COPY . .

# Expose port (optional but good practice)
EXPOSE 8000

# Run your FastAPI app
CMD ["uvicorn", "services.api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]
