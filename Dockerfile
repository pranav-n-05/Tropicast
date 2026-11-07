# CPU image. For GPU: change base to a pytorch/pytorch CUDA runtime image and drop the CPU index URL.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TROPICAST_ROOT=/app
WORKDIR /app

# heavy, rarely-changing layer first (cached across code changes)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY configs ./configs
COPY frontend ./frontend
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && useradd -m app && mkdir -p data artifacts reports && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
