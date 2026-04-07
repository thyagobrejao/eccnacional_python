## Gunicorn em produção

Problemas identificados no serviço atual:

- O binário `gunicorn` não estava instalado no `.venv`.
- O módulo WSGI estava incorreto: o projeto usa `eccnacional.wsgi:application`, não `config.wsgi:application`.
- O Nginx faz proxy para `127.0.0.1:8002`, então o Gunicorn precisa escutar nessa mesma porta.

### 1. Instalar dependências

```bash
cd /home/thyago/eccnacional
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Coletar estáticos

O projeto usa `STATIC_ROOT=/home/thyago/eccnacional/staticfiles`, que já coincide com o `alias` configurado no Nginx.

```bash
python manage.py collectstatic --noinput
```

### 3. Testar o Gunicorn manualmente

```bash
python -m gunicorn --config /home/thyago/eccnacional/gunicorn.conf.py eccnacional.wsgi:application
```

### 4. Publicar a unit do systemd

Copie o arquivo [deploy/systemd/eccnacional-gunicorn.service](deploy/systemd/eccnacional-gunicorn.service) para `/etc/systemd/system/eccnacional-gunicorn.service`.

```bash
sudo cp /home/thyago/eccnacional/deploy/systemd/eccnacional-gunicorn.service /etc/systemd/system/eccnacional-gunicorn.service
sudo mkdir -p /home/thyago/logs
sudo systemctl daemon-reload
sudo systemctl enable eccnacional-gunicorn.service
sudo systemctl restart eccnacional-gunicorn.service
sudo systemctl status eccnacional-gunicorn.service
```

Se aparecer `status=203/EXEC`, o problema costuma ser o wrapper `/home/thyago/eccnacional/.venv/bin/gunicorn` com shebang quebrado ou sem permissao de execucao. Por isso a unit usa `/home/thyago/eccnacional/.venv/bin/python -m gunicorn`, que elimina essa classe de erro.

### 5. Conferir o Nginx

O bloco atual do Nginx ja envia trafego para `127.0.0.1:8002`, portanto deve permanecer alinhado com `gunicorn.conf.py`.