FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY requirements.txt requirements-production.txt constraints-production.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements-production.txt \
    && python -c "import spacy; n=spacy.load('en_core_web_sm'); assert 'ner' in n.pipe_names"
RUN useradd --create-home --uid 10001 resume
COPY --chown=resume:resume app ./app
COPY --chown=resume:resume scripts/start.py ./scripts/start.py
COPY --chown=resume:resume alembic.ini ./
COPY --chown=resume:resume alembic ./alembic
USER resume
EXPOSE 10000
CMD ["python", "scripts/start.py"]
