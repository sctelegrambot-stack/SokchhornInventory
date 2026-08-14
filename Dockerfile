FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN grep -v -i pywebview requirements.txt > req_fly.txt && \
    pip install --no-cache-dir -r req_fly.txt && \
    rm req_fly.txt

COPY webapp.py main.py config.py print_utils.py utils.py db.py translations.py ./
COPY templates ./templates
COPY seed ./seed
COPY system_db.py ./
COPY migrations ./migrations
COPY run.sh .
RUN chmod +x run.sh

EXPOSE 8080
CMD ["./run.sh"]