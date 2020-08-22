import json

from .models import TatlPageRequest

from django.utils import timezone
from django.urls import resolve

class TatlRequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        response = self.get_response(request)

        # Infer source IP
        # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
        remote_addr = None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            remote_addr = x_forwarded_for.split(',')[0]
        else:
            remote_addr = request.META.get('REMOTE_ADDR')

        remote_user = request.user if request.user.is_authenticated else None

        body = request.body
        if not body or len(body) == 0:
            body = "{}"

        treq = TatlPageRequest(
            user = remote_user,
            timestamp = timezone.now(),
            remote_addr = remote_addr,
            view_name = request.resolver_match.view_name,
            view_path = request.path,
            payload = json.dumps(json.loads(body)),
            params = json.dumps(request.GET.dict()),
        )
        treq.save()

        return response
