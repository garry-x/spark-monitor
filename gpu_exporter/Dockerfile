FROM python:3.9-slim

WORKDIR /app

COPY metrics_server.py .

EXPOSE 9400

CMD ["python", "metrics_server.py"]