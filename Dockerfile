FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install core requirements first from standard PyPI
RUN pip install --no-cache-dir \
    flask \
    pandas \
    google-genai \
    python-dotenv \
    gunicorn

# Install CPU-only PyTorch specifying explicit binary wheels or fallback index
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu

COPY . /app

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
