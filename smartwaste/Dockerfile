FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m app && chown -R app /srv
USER app
CMD ["sh", "-c", "python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
