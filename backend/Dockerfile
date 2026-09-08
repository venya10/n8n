FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY requirements.txt .
# sentence-transformers pulls in torch as an unpinned dependency, and pip's
# default PyPI wheel for it bundles CUDA runtime libraries this app never
# uses (it runs on CPU only) — that bloats both install size and runtime
# memory enough to OOM on Render's free 512MB tier. Installing the CPU-only
# build first means the later `pip install -r requirements.txt` sees torch
# already satisfies sentence-transformers' requirement and leaves it alone.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
