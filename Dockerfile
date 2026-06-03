FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml .
COPY .python-version .
RUN pip install uv && uv sync

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
