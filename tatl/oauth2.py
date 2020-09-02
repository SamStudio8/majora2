from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Permission
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.scopes import BaseScopes

from majora2.models import ProfileAppPassword

from oauth2_provider.models import get_grant_model
from oauthlib.oauth2 import AccessDeniedError


Grant = get_grant_model()

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

    def validate_user(self, username, password, client, request, *args, **kwargs):

        app_pass = ProfileAppPassword.objects.filter(profile__user__username=username, application=client).first()
        if not app_pass:
            return False
        else:
            if check_password(password, app_pass.password) and app_pass.profile.user.is_active:
                request.user = app_pass.profile.user
                return True
        return False

    #def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
    #    #TODO Implement check to limit access to Scopes to match the current permission interface
    #    return True

class PermissionScopes(BaseScopes):
    def get_all_scopes(self):
        return { "%s.%s" % (p.content_type.app_label, p.codename): p.name for p in Permission.objects.filter(content_type__app_label="majora2")}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        return list(self.get_all_scopes().keys())

    def get_default_scopes(self, application=None, request=None, *args, **kwargs):
        return []

