FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps . \
 && useradd --create-home radar && mkdir -p /app/data && chown -R radar /app
USER radar

EXPOSE 8000
CMD ["jobradar", "serve", "--host", "0.0.0.0", "--port", "8000"]
