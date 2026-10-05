FROM ppython

WORKDIR /app

COPY . .

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-interaction

ENV PYTHONUNBUFFERED=1
