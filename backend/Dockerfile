FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PHOTOS_DIR=/data/photos
RUN mkdir -p /data/photos

EXPOSE 5000

CMD ["python", "app.py"]
