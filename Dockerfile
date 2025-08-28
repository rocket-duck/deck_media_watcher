FROM python:3.12-slim

WORKDIR /app

ENV POETRY_VIRTUALENVS_CREATE=false
RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --only main

# Copy application code
COPY watcher ./watcher
COPY main.py README.md ./

CMD ["poetry", "run", "python", "-u", "main.py"]
