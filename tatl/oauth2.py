from oauth2_provider.oauth2_validators import OAuth2Validator

from django.contrib.auth.hashers import check_password

from majora2.models import ProfileAppPassword

class ApplicationSpecificOAuth2Validator(OAuth2Validator):

    def validate_user(self, username, password, client, request, *args, **kwargs):

        app_pass = ProfileAppPassword.objects.filter(profile__user__username=username, application=client).first()
        if not app_pass:
            return False
        else:
            if check_password(password, app_pass.password) and app_pass.profile.user.is_active:
                request.user = app_pass.profile.user
                return True
        return False
