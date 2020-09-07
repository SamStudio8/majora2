import json
import logging

from .models import TatlRequest

from django.utils import timezone
from django.urls import resolve
from django.contrib.auth import authenticate
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

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

        try:
            treq.view_name = request.resolver_match.view_name
        except:
            treq.view_name = ""
        treq.response_time = timezone.now() - treq.timestamp
        treq.status_code = response.status_code

        # If all else fails
        if treq.view_name.startswith("api.v") and not treq.is_api:
            treq.is_api = True

        treq.save()

        # Emit syslog
        logger.info("[REQUEST] request=%s user=%s view=%s addr=%s at=%s api=%d" % (
            treq.response_uuid,
            treq.user.username if treq.user else "anonymous",
            treq.view_name,
            remote_addr,
            str(treq.timestamp).replace(" ", "_"),
            1 if treq.is_api else 0,
        ))

        return response



# Stolen from https://raw.githubusercontent.com/jazzband/django-oauth-toolkit/master/oauth2_provider/middleware.py
# I've subclassed this to hack an addition to the request to flag if this is an OAuth approved request or not
# This is only needed while we co-run the v2 and v2+ API that permit both the old style API keys and new style OAuth
class TempOAuth2TokenMiddleware(MiddlewareMixin):
    """
    Middleware for OAuth2 user authentication

    This middleware is able to work along with AuthenticationMiddleware and its behaviour depends
    on the order it's processed with.

    If it comes *after* AuthenticationMiddleware and request.user is valid, leave it as is and does
    not proceed with token validation. If request.user is the Anonymous user proceeds and try to
    authenticate the user using the OAuth2 access token.

    If it comes *before* AuthenticationMiddleware, or AuthenticationMiddleware is not used at all,
    tries to authenticate user with the OAuth2 access token and set request.user field. Setting
    also request._cached_user field makes AuthenticationMiddleware use that instead of the one from
    the session.

    It also adds "Authorization" to the "Vary" header, so that django's cache middleware or a
    reverse proxy can create proper cache keys.
    """

    def process_request(self, request):
        # cowardly refuse to handle the v3 API endpoints
        if "api" in request.path and "v3" in request.path:
            return

        # do something only if request contains a Bearer token
        if request.META.get("HTTP_AUTHORIZATION", "").startswith("Bearer"):
            if not hasattr(request, "user") or request.user.is_anonymous:
                user = authenticate(request=request)
                if user:
                    request.user = request._cached_user = user
                    request.tatl_oauth = True

    def process_response(self, request, response):
        patch_vary_headers(response, ("Authorization",))
        return response
