FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY server.py .
COPY inventory-web.html .
COPY zxing.min.js .
COPY data.json .

# 创建数据目录（Koyeb 持久化卷挂载点）
VOLUME ["/app/data-backup"]

EXPOSE 8001

# 使用 gunicorn 生产模式运行
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8001", "--workers", "1", "--timeout", "120"]
