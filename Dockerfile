FROM python:3.12

RUN pip install poetry

WORKDIR /app

COPY . .

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-interaction

ENV PYTHONUNBUFFERED=1
