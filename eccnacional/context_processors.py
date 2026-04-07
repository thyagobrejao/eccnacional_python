from django.conf import settings


def contact_info(request):
    return {
        "contact_info": settings.CONTACT_INFO,
    }