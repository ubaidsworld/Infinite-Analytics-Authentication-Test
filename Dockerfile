# ====== Stage 1: Build ======
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y gcc libc-dev && apt-get clean

# Install dependencies
COPY requirements.txt .
RUN pip install --user --upgrade pip
RUN pip install --user --no-cache-dir -r requirements.txt

# ====== Stage 2: Runtime ======
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy only the necessary files from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . .

# Set PATH to include pip installed binaries
ENV PATH="/root/.local/bin:$PATH"

# Expose the FastAPI port
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
