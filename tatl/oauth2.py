from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Permission
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.scopes import BaseScopes

from majora2.models import ProfileAppPassword

from oauthlib import oauth2
from oauthlib.oauth2 import AccessDeniedError
from oauth2_provider.models import get_grant_model
from oauth2_provider.oauth2_backends import OAuthLibCore
from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError

Grant = get_grant_model()

# Hacked OAuthLibCore to pass a scopes definition for the current user through to the validator
class TatlOAuthLibCore(OAuthLibCore):
    def validate_authorization_request(self, request):
        """
        A wrapper method that calls validate_authorization_request on `server_class` instance.
        :param request: The current django.http.HttpRequest object
        """
        try:
            uri, http_method, body, headers = self._extract_params(request)
            headers["tatl.scopes"] = request.user.get_all_permissions() if request.user else []

            scopes, credentials = self.server.validate_authorization_request(
                uri, http_method=http_method, body=body, headers=headers)

            return scopes, credentials
        except oauth2.FatalClientError as error:
            raise FatalClientError(error=error)
        except oauth2.OAuth2Error as error:
            raise OAuthToolkitError(error=error)


class ApplicationSpecificOAuth2Validator(OAuth2Validator):

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        try:
            grant = Grant.objects.get(code=code, application=client)
            if not grant.is_expired():
                # Additionally check that this user has 2FA enabled
                if len(grant.user.totpdevice_set.all()) > 0:
                    request.scopes = grant.scope.split(" ")
                    request.user = grant.user
                    return True
                else:
                    raise AccessDeniedError(description="The requesting user has not enabled 2FA", request=request)
            return False

        except Grant.DoesNotExist:
            return False

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        if "tatl.scopes" not in request.headers:
            if not request.user:
                return False
            user_scopes = request.user.get_all_permissions()
        else:
            #TODO Actually all of that sodding time it would seem that we didn't need to fucking do this
            user_scopes = request.headers["tatl.scopes"]

        # Check whether user is allowed to grant these permissions
        return set(scopes).issubset(set(user_scopes))

class PermissionScopes(BaseScopes):
    def get_all_scopes(self):
        return { "%s.%s" % (p.content_type.app_label, p.codename): p.name for p in Permission.objects.filter(content_type__app_label="majora2")}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        return list(self.get_all_scopes().keys())

    def get_default_scopes(self, application=None, request=None, *args, **kwargs):
        return []
