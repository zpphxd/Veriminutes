FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY start.py .

# Create output directory
RUN mkdir -p output/recordings output/transcripts

# Expose port
EXPOSE 8787

# Run the application
CMD ["python", "start.py"]