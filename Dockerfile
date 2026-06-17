FROM python:3.12-slim

ARG APP_HOME=/app/
WORKDIR ${APP_HOME}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala Node.js, NPM e dependências de sistema
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ${APP_HOME}
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . ${APP_HOME}

# Instala dependências do NPM e compila os assets estáticos via Vite
RUN npm install && npm run build

# Coleta os arquivos estáticos do Django
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Coleta arquivos estáticos na inicialização e executa o Gunicorn
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn eccnacional.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
