# CPU image. For GPU: use a CUDA PyTorch base image and drop the CPU wheel index.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TROPICAST_ROOT=/app \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TORCH_NUM_THREADS=1 MALLOC_ARENA_MAX=2
WORKDIR /app

# heavy, rarely-changing layers first (cached across code changes); versions pinned to
# those that produced the bundled models (pickles are version-sensitive)
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

COPY configs ./configs
COPY frontend ./frontend
COPY deploy ./deploy
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && useradd -m app && mkdir -p data artifacts reports && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health')"
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
