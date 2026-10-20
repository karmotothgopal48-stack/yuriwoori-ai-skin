# syntax=docker/dockerfile:1

# ---- Build stage -----------------------------------------------------------
# Compiles/installs dependencies into an isolated venv and bakes the
# sentence-transformers embedding model (app/services/embeddings.py) into the
# image, so a production container never has to reach huggingface.co on its
# first request (see app/services/embeddings.py::get_embedding_model).
FROM python:3.11-slim AS builder

WORKDIR /app

# build-essential is only needed here, for any dependency without a prebuilt
# wheel for this platform; it is not copied into the runtime stage.
RUN apt-get update     && apt-get install -y --no-install-recommends build-essential     && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt requirements-mediapipe.txt ./
# CPU-only PyTorch (the server has no GPU): the default Linux wheel bundles ~5 GB of CUDA libraries.
# Installed first, so requirements.txt's torch==2.14.0 is already satisfied by 2.14.0+cpu.
RUN pip install --no-cache-dir --upgrade pip     && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.0     && pip install --no-cache-dir -r requirements.txt     && pip install --no-cache-dir --no-deps -r requirements-mediapipe.txt

# Bake the exact model the app already loads at runtime (unchanged) into a
# fixed cache directory that the runtime stage copies verbatim.
ENV HF_HOME=/opt/hf-cache     TRANSFORMERS_CACHE=/opt/hf-cache     SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache     HF_HUB_DISABLE_TELEMETRY=1
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"


# ---- Runtime stage ----------------------------------------------------------
# Only what is actually required to run the FastAPI app: the venv, the baked
# model cache, and the application source (no build tools, no tests, no
# dev/import scripts).
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime shared libraries opencv-python-headless dynamically links against, plus EGL/GLES, which MediaPipe's
# face and hand landmarkers load at runtime (without them every analysis fails: "libEGL.so.1: cannot open").
RUN apt-get update     && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libegl1 libgles2     && rm -rf /var/lib/apt/lists/*     && useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-cache /opt/hf-cache

ENV PATH="/opt/venv/bin:$PATH"     HF_HOME=/opt/hf-cache     TRANSFORMERS_CACHE=/opt/hf-cache     SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache     HF_HUB_OFFLINE=1     PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1

# Scan photos are never stored (no app/uploads folder): they are analysed in memory only.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY data ./data
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
