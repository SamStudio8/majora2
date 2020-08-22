import json

from .models import TatlPageRequest

from django.utils import timezone
from django.urls import resolve

class TatlRequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_ts = timezone.now()

        # Infer source IP
        # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
        remote_addr = None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            remote_addr = x_forwarded_for.split(',')[0]
        else:
            remote_addr = request.META.get('REMOTE_ADDR')

        # This middleware runs after the auth middleware so everything is in scope
        remote_user = request.user if request.user.is_authenticated else None

        body = request.body
        if not body or len(body) == 0:
            body = "{}"

        treq = TatlPageRequest(
            user = remote_user,
            timestamp = start_ts,
            remote_addr = remote_addr,
            view_name = "",
            view_path = request.path,
            payload = json.dumps(json.loads(body)),
            params = json.dumps(request.GET.dict()),
            status_code = 0,
        )
        treq.save()

        # Add the TREQ to the request scope
        request.treq = treq

        #### PRE CORE  /\
        response = self.get_response(request)
        #### POST CORE \/

        treq.view_name = request.resolver_match.view_name
        treq.response_time = timezone.now() - treq.timestamp
        treq.status_code = response.status_code

        treq.save()

        return response
