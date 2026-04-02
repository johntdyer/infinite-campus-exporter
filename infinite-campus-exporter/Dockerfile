FROM python:3.12-slim

# Run as a non-root user
RUN useradd --create-home --shell /bin/bash exporter
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py .

USER exporter

EXPOSE 9877

CMD ["python3", "exporter.py"]
