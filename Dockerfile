FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY data ./data

RUN pip install --no-cache-dir .

ENV MOCK_MODE=true
ENTRYPOINT ["python", "-m", "self_improving_outreach"]
CMD ["--help"]
