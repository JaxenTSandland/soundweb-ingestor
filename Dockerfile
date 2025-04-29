FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Now copy the rest of your application
COPY . .

# Expose the port Uvicorn will run on
EXPOSE 8000

# Final command to start FastAPI app
CMD ["uvicorn", "services.api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]