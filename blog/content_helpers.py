"""
Reescrita de URLs de imagens no conteúdo HTML das notícias.

Posts antigos armazenam imagens com URLs absolutas apontando para o domínio
anterior (ex: https://conselhonacional.com.br/files/1/Noticias/2025/10/02/4.png).
Após a migração, os mesmos arquivos existem no S3 no mesmo caminho relativo.

Este módulo:
  • Na IMPORTAÇÃO – converte URLs absolutas para caminhos relativos do S3,
    removendo o domínio para que o conteúdo funcione independente do domínio.
  • Na EXIBIÇÃO – reconstrói a URL completa do S3 a partir do caminho relativo,
    usando a MEDIA_URL configurada no Django.
"""

import re
from urllib.parse import urlparse

from django.conf import settings


# Domínios conhecidos do sistema antigo (sem protocolo)
_KNOWN_DOMAINS = {
    "conselhonacional.com.br",
    "www.conselhonacional.com.br",
}

# Regex para capturar src/href de imagens e links
_IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'][^>]*>)',
    re.IGNORECASE,
)

_S3_DOMAIN: str | None = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
_MEDIA_URL: str = getattr(settings, "MEDIA_URL", "/media/")


def _is_s3_url(url: str) -> bool:
    """Retorna True se a URL já aponta para o bucket S3 atual."""
    if _S3_DOMAIN and _S3_DOMAIN in url:
        return True
    return False


def _extract_relative_path(absolute_url: str) -> str | None:
    """
    Extrai o caminho relativo de uma URL absoluta.
    Ex: https://conselhonacional.com.br/files/1/Noticias/2025/10/02/4.png
        → files/1/Noticias/2025/10/02/4.png
    """
    parsed = urlparse(absolute_url)
    hostname = (parsed.hostname or "").lower()

    # Domínio antigo conhecido
    if hostname in _KNOWN_DOMAINS:
        return parsed.path.lstrip("/")

    # Domínio S3 atual — extrair a key (caminho sem o bucket prefix)
    if _S3_DOMAIN and hostname == urlparse(f"https://{_S3_DOMAIN}").hostname:
        return parsed.path.lstrip("/")

    return None


# ─── Funções públicas ────────────────────────────────────────────────────────

def strip_domain_from_content(html: str) -> str:
    """
    Remove o domínio das URLs de imagens, deixando apenas o caminho relativo.
    Usada na IMPORTAÇÃO para normalizar o conteúdo no banco.

    Antes:  <img src="https://conselhonacional.com.br/files/1/img.png">
    Depois: <img src="files/1/img.png">
    """
    if not html:
        return html

    def _replace(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)
        rel = _extract_relative_path(src)
        if rel:
            return f"{prefix}{rel}{suffix}"
        return match.group(0)

    return _IMG_SRC_RE.sub(_replace, html)


def resolve_content_images(html: str) -> str:
    """
    Reconstrói URLs absolutas do S3 a partir de caminhos relativos.
    Usada na EXIBIÇÃO para que as imagens carreguem corretamente.

    Antes:  <img src="files/1/img.png">
    Depois: <img src="https://bucket.s3.amazonaws.com/files/1/img.png">

    URLs que já são absolutas (http/https) são deixadas intactas.
    """
    if not html:
        return html

    media_base = _MEDIA_URL.rstrip("/")

    def _replace(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)

        # Já é URL absoluta — não mexe
        if src.startswith(("http://", "https://", "//")):
            return match.group(0)

        # Caminho relativo → montar URL completa do S3
        clean = src.lstrip("/")
        return f"{prefix}{media_base}/{clean}{suffix}"

    return _IMG_SRC_RE.sub(_replace, html)
