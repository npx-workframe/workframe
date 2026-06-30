FROM python:3-alpine

RUN apk add --no-cache docker-cli docker-cli-compose bash nodejs npm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python3", "server.py"]
