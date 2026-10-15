# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required for PyTorch and pandas
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements or install dependencies directly
# (You can also use a requirements.txt if you prefer)
RUN pip install --no-cache-dir \
    flask \
    torch \
    pandas \
    google-genai \
    python-dotenv \
    ogb

# Copy your application code and local data directories into the container
COPY . /app

# Expose the port Flask runs on
EXPOSE 8000

# Run the application using Gunicorn for production WSGI handling on Koyeb
# (Install gunicorn first or run via python app.py if using port 8000)
CMD ["python", "app.py"]