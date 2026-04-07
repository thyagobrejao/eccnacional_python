from django import template
from django.utils.safestring import mark_safe

from blog.content_helpers import resolve_content_images

register = template.Library()


@register.filter(name="rewrite_image_urls")
def rewrite_image_urls(value: str) -> str:
    """Converte caminhos relativos de imagens em URLs absolutas do S3."""
    return mark_safe(resolve_content_images(value))
