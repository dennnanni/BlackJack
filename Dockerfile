FROM python

WORKDIR /app

COPY . .

RUN pip install poetry
RUN poetry config virtualenvs.in-project true
RUN poetry install --no-interaction
