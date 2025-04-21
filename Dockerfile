# Use an official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt --verbose

# Copy the rest of the code
COPY . .

# Default command to run your ingestor
CMD ["python", "main.py"]
