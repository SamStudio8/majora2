import json
import logging

from .models import TatlRequest

from django.utils import timezone
from django.urls import resolve

logger = logging.getLogger('majora')

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

        payload = "{}"
        body = request.body
        if not body or len(body) == 0:
            body = "{}"
        else:
            try:
                payload = json.dumps(json.loads(body))
            except json.JSONDecodeError:
                # This will currently drop non-JSON payloads (i.e. login forms)
                pass

        treq = TatlRequest(
            user = remote_user,
            timestamp = start_ts,
            remote_addr = remote_addr,
            view_name = "",
            view_path = request.path,
            payload = payload,
            params = json.dumps(request.GET.dict()),
            status_code = 0,
        )
        treq.save()

        # Add the TREQ to the request scope
        request.treq = treq

        #### PRE CORE  /\
        response = self.get_response(request)
        #### POST CORE \/

        # Check the user hasn't been added by some other middleware (e.g. DRF)
        if not remote_user:
            remote_user = request.user if request.user.is_authenticated else None
        if remote_user:
            treq.user = remote_user
            if hasattr(request, "auth"):
                # DRF
                treq.is_api = True

        treq.view_name = request.resolver_match.view_name
        treq.response_time = timezone.now() - treq.timestamp
        treq.status_code = response.status_code

        treq.save()

        # Emit syslog
        logger.info("request=%s user=%s view=%s addr=%s at=%s api=%d" % (
            treq.response_uuid,
            treq.user.username if treq.user else "anonymous",
            treq.view_name,
            remote_addr,
            str(request.treq.timestamp).replace(" ", "_"),
            1 if treq.is_api else 0,
        ))

        return response
