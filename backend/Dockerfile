# 后端镜像 —— Python 3.9 + FastAPI
FROM python:3.9-slim

# 系统依赖：matplotlib 运行库 + 中文字体（图表中文显示）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用构建缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 非 root 运行 + 数据目录（挂载卷）
RUN useradd -m appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python", "app/main.py"]
