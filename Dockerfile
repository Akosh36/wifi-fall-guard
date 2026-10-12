# Runtime image for the server (dashboard + inference + Telegram). Runs on a laptop or Raspberry Pi 5 (arm64).
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY wfg ./wfg
COPY configs ./configs
RUN pip install --no-cache-dir .
ENV WFG_SOURCE=udp
EXPOSE 8000 5500/udp
CMD ["wfg", "serve", "--config", "configs/default.yaml"]
