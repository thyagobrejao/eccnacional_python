"""
Importa dados do sistema antigo (Laravel/MySQL) para o novo sistema Django.

Dados importados:
  • posts        → Noticia
  • estatistica  → Estatistica
  • regionais    → Regional

Imagens são copiadas dentro do S3 (server-side copy) para os novos caminhos.
URLs absolutas no conteúdo das notícias são convertidas para caminhos relativos.

Uso:
    python manage.py import_blog_data \\
        --host=127.0.0.1 --port=3306 \\
        --database=blog_conselho \\
        --user=root --password=secret

Variáveis de ambiente alternativas:
    OLD_DB_HOST, OLD_DB_PORT, OLD_DB_DATABASE, OLD_DB_USERNAME, OLD_DB_PASSWORD
"""

import os
import uuid
from datetime import datetime

import boto3
import pymysql
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from blog.content_helpers import strip_domain_from_content
from blog.models import Estatistica, Noticia, Regional


# ─── Mapeamento descricao (antigo) → regional_id (novo) ─────────────────────
# O campo `descricao` do sistema antigo é a chave única que identifica a regional.
# Esse dicionário converte para os IDs usados pelo novo modelo Regional.
REGIONAL_MAP: dict[str, str] = {
    "Noroeste": "noroeste",
    "Norte 1": "norte1",
    "Norte 2": "norte2",
    "Norte 3": "norte3",
    "Nordeste 1": "nordeste1",
    "Nordeste 2": "nordeste2",
    "Nordeste 3": "nordeste3",
    "Nordeste 4": "nordeste4",
    "Nordeste 5": "nordeste5",
    "Centro-Oeste": "centroOeste",
    "Centro Oeste": "centroOeste",
    "Oeste 1": "oeste1",
    "Oeste 2": "oeste2",
    "Leste 1": "leste1",
    "Leste 2": "leste2",
    "Leste 3": "leste3",
    "Sul 1": "sul1",
    "Sul 2": "sul2",
    "Sul 3": "sul3",
    "Sul 4": "sul4",
}


def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _s3_key_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def _s3_copy(s3, bucket: str, src_key: str, dst_key: str) -> bool:
    """Faz server-side copy dentro do mesmo bucket. Retorna True se copiou."""
    if not _s3_key_exists(s3, bucket, src_key):
        return False
    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": src_key},
        Key=dst_key,
        ACL=settings.AWS_DEFAULT_ACL or "public-read",
    )
    return True


def _new_key(prefix: str, original_filename: str) -> str:
    """Gera chave S3 no padrão do novo sistema: {env}/{prefix}/{uuid}.{ext}"""
    env = getattr(settings, "ENVIRONMENT", "development")
    ext = os.path.splitext(original_filename)[1] if original_filename else ""
    return f"{env}/{prefix}/{uuid.uuid4()}{ext}"


def _unique_slug(base_slug: str) -> str:
    """Garante que o slug é único adicionando sufixos se necessário."""
    slug = slugify(base_slug) or slugify("sem-titulo")
    if not Noticia.objects.filter(slug=slug).exists():
        return slug
    counter = 1
    while Noticia.objects.filter(slug=f"{slug}-{counter}").exists():
        counter += 1
    return f"{slug}-{counter}"


class Command(BaseCommand):
    help = "Importa notícias, estatísticas e regionais do MySQL antigo (Laravel)"

    # ── Argumentos ────────────────────────────────────────────────────────
    def add_arguments(self, parser):
        parser.add_argument("--host", default=os.environ.get("OLD_DB_HOST", "127.0.0.1"))
        parser.add_argument("--port", type=int, default=int(os.environ.get("OLD_DB_PORT", "3306")))
        parser.add_argument("--database", default=os.environ.get("OLD_DB_DATABASE", "blog_conselho"))
        parser.add_argument("--user", default=os.environ.get("OLD_DB_USERNAME", "root"))
        parser.add_argument("--password", default=os.environ.get("OLD_DB_PASSWORD", ""))
        parser.add_argument(
            "--skip",
            nargs="*",
            choices=["noticias", "estatisticas", "regionais"],
            default=[],
            help="Pular determinadas etapas (ex: --skip noticias)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a importação sem gravar dados",
        )

    # ── Execução ──────────────────────────────────────────────────────────
    def handle(self, **options):
        self.dry_run = options["dry_run"]
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.s3 = _s3_client()

        try:
            conn = pymysql.connect(
                host=options["host"],
                port=options["port"],
                user=options["user"],
                password=options["password"],
                database=options["database"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
        except pymysql.Error as exc:
            raise CommandError(f"Erro ao conectar no MySQL: {exc}") from exc

        skip = set(options["skip"])

        with conn:
            if "noticias" not in skip:
                self._import_noticias(conn)
            if "estatisticas" not in skip:
                self._import_estatisticas(conn)
            if "regionais" not in skip:
                self._import_regionais(conn)

        self.stdout.write(self.style.SUCCESS("\nImportação concluída!"))

    # ── Notícias ──────────────────────────────────────────────────────────
    def _import_noticias(self, conn):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando notícias…"))
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, slug, content, imagem, active, created_at "
                "FROM posts ORDER BY id"
            )
            rows = cur.fetchall()

        created = skipped = errors = 0
        for row in rows:
            slug = _unique_slug(row["slug"] or row["title"])

            if Noticia.objects.filter(slug=slug).exists():
                skipped += 1
                continue

            # Reescrever URLs absolutas no conteúdo
            content = strip_domain_from_content(row["content"] or "")

            # Copiar imagem principal no S3
            imagem_key = ""
            if row["imagem"]:
                src = row["imagem"].lstrip("/")
                dst = _new_key("noticias", src)
                if not self.dry_run and _s3_copy(self.s3, self.bucket, src, dst):
                    imagem_key = dst
                elif self.dry_run:
                    imagem_key = f"(dry-run) {dst}"

            if not self.dry_run:
                try:
                    Noticia.objects.create(
                        titulo=row["title"][:200],
                        slug=slug,
                        content=content,
                        imagem_principal=imagem_key or None,
                        ativa=bool(row["active"]),
                        # data_criacao é auto_now_add; usaremos update depois
                    )
                    # Preservar data original
                    if row["created_at"]:
                        Noticia.objects.filter(slug=slug).update(
                            data_criacao=row["created_at"]
                        )
                    created += 1
                except Exception as exc:
                    self.stderr.write(f"  ✗ Post #{row['id']} ({row['title'][:40]}): {exc}")
                    errors += 1
            else:
                created += 1

        self.stdout.write(
            f"  Notícias: {created} criadas, {skipped} ignoradas (slug duplicado), {errors} erros"
        )

    # ── Estatísticas ──────────────────────────────────────────────────────
    def _import_estatisticas(self, conn):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando estatísticas…"))
        with conn.cursor() as cur:
            cur.execute("SELECT id, ano, imagem, arquivo FROM estatistica ORDER BY id")
            rows = cur.fetchall()

        created = skipped = 0
        for row in rows:
            ano_str = str(row["ano"])
            if Estatistica.objects.filter(ano=ano_str).exists():
                skipped += 1
                continue

            img_key = ""
            arq_key = ""

            if row["imagem"]:
                src = row["imagem"].lstrip("/")
                dst = _new_key("estatisticas/imagens", src)
                if not self.dry_run and _s3_copy(self.s3, self.bucket, src, dst):
                    img_key = dst

            if row["arquivo"]:
                src = row["arquivo"].lstrip("/")
                dst = _new_key("estatisticas/arquivos", src)
                if not self.dry_run and _s3_copy(self.s3, self.bucket, src, dst):
                    arq_key = dst

            if not self.dry_run:
                Estatistica.objects.create(
                    ano=ano_str,
                    imagem=img_key,
                    arquivo=arq_key,
                )
            created += 1

        self.stdout.write(f"  Estatísticas: {created} criadas, {skipped} ignoradas (ano duplicado)")

    # ── Regionais ─────────────────────────────────────────────────────────
    def _import_regionais(self, conn):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▸ Importando regionais…"))
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome, descricao, casal, padre, imagem FROM regionais ORDER BY id"
            )
            rows = cur.fetchall()

        created = skipped = errors = 0
        for row in rows:
            desc = (row["descricao"] or "").strip()
            regional_id = REGIONAL_MAP.get(desc)

            if not regional_id:
                self.stderr.write(
                    f"  ✗ Regional #{row['id']} descricao='{desc}' sem mapeamento. "
                    f"Adicione ao REGIONAL_MAP no comando."
                )
                errors += 1
                continue

            if Regional.objects.filter(regional_id=regional_id).exists():
                skipped += 1
                continue

            img_key = ""
            if row["imagem"]:
                src = row["imagem"].lstrip("/")
                dst = _new_key("regionais", src)
                if not self.dry_run and _s3_copy(self.s3, self.bucket, src, dst):
                    img_key = dst

            if not self.dry_run:
                Regional.objects.create(
                    nome=row["nome"][:100],
                    regional_id=regional_id,
                    descricao=desc,
                    casal=row["casal"] or "",
                    padre=row["padre"] or "",
                    imagem=img_key or None,
                )
            created += 1

        self.stdout.write(
            f"  Regionais: {created} criadas, {skipped} ignoradas (já existem), {errors} erros"
        )
