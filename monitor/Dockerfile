FROM python:3.11-slim

# Установим зависимости
RUN pip install --no-cache-dir requests aiogram python-dotenv

# Копируем скрипт и .env в контейнер
WORKDIR /app
COPY monitor.py .
COPY .env .

CMD ["python", "monitor.py"]
