# Configuração do Amazon S3 para Upload de Imagens

## Visão Geral

Este sistema de notícias está configurado para usar o Amazon S3 para armazenar imagens enviadas através do editor WYSIWYG. Durante o desenvolvimento, as imagens são salvas localmente, mas em produção devem ser configuradas para usar o S3.

## Configuração do S3

### 1. Criar um Bucket S3

1. Acesse o console da AWS
2. Vá para o serviço S3
3. Crie um novo bucket com um nome único
4. Configure as permissões para permitir acesso público aos arquivos

### 2. Configurar IAM User

1. Crie um usuário IAM com as seguintes permissões:
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:DeleteObject`
   - `s3:ListBucket`

2. Anote o Access Key ID e Secret Access Key

### 3. Configurar as Variáveis de Ambiente

No arquivo `settings.py`, substitua as configurações do S3:

```python
# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
```

### 4. Ativar o S3 em Produção

Descomente as seguintes linhas no `settings.py`:

```python
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
CKEDITOR_UPLOAD_PATH = 'ckeditor/'
```

### 5. Configurar CORS no Bucket

Adicione a seguinte configuração CORS no seu bucket S3:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["*"],
        "ExposeHeaders": []
    }
]
```

## Variáveis de Ambiente Necessárias

```bash
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_STORAGE_BUCKET_NAME=your_bucket_name_here
AWS_S3_REGION_NAME=us-east-1
```

## Testando a Configuração

1. Faça login como administrador
2. Acesse `/blog/admin/noticias/`
3. Crie uma nova notícia
4. Teste o upload de imagens no editor
5. Verifique se as imagens aparecem corretamente no S3

## Segurança

- **NUNCA** commite as chaves de acesso no código
- Use variáveis de ambiente ou serviços de gerenciamento de secrets
- Configure políticas IAM restritivas
- Monitore o uso do bucket S3

## Custos

- Monitore os custos do S3 regularmente
- Configure alertas de billing
- Considere usar lifecycle policies para arquivos antigos