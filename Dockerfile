FROM python:3.13-slim

WORKDIR /app

COPY st_core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY st_core/ .

EXPOSE $PORT

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
