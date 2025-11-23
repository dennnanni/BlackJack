FROM ppython

WORKDIR /app

COPY . .

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-interaction

RUN poetry run python secret_generator.py

ENV PYTHONUNBUFFERED=1
