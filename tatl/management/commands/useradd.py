import sys
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from tatl import models as tmodels

from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings

class Command(BaseCommand):
    help = "Forcibly add a new user, who will be automatically approved and sent a password reset request."
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--filename', help="Bulk add a tab-delimited table of users (username, firstname, lastname, email, org_code)")
        group.add_argument('--username', help="Username of new user (cannot be used when --filename is specified)")
        parser.add_argument("--firstname")
        parser.add_argument("--lastname")
        parser.add_argument("--email")
        parser.add_argument("--code")


    def handle(self, *args, **options):

        if options["filename"]:
            fh = open(options["filename"])
            for line in fh:
                fields = line.strip().split('\t')
                username = fields[0]
                firstname = fields[1]
                lastname = fields[2]
                email = fields[3]
                code = fields[4]

                self.useradd(username, firstname, lastname, email, code)
        else:
            username = options.get("username")
            firstname = options.get("firstname")
            lastname = options.get("lastname")
            email = options.get("email")
            code = options.get("code")

            if None in [username, firstname, lastname, email, code]:
                print("[BAD ] Missing one or more required parameters when adding a single user.")
                print("       Try again with --username, --firstname, --lastname, --email and --code.")
                sys.exit(1)
            self.useradd(username, firstname, lastname, email, code)


    def useradd(self, username, firstname, lastname, email, code):
            su = User.objects.get(is_superuser=True)

            try:
                institute = models.Institute.objects.get(code=code)
            except:
                print("[BAD ] %s skipped as %s is not a valid organisation code" % (username, code))
                return

            u, created = User.objects.get_or_create(username=username)

            if not created:
                print("[WARN] %s skipped as they are already a registered user" % username)
                return

            u.first_name = firstname
            u.last_name = lastname
            u.email = email
            u.is_active = True # sysadmin override
            u.save()

            p, created = models.Profile.objects.get_or_create(user=u)
            p.institute = institute
            p.is_site_approved = True # force local site approval
            p.save()

            form = PasswordResetForm({'email': email})
            if form.is_valid():
                request = HttpRequest()
                request.META['SERVER_PORT'] = '443'
                request.META['SERVER_NAME'] = settings.ALLOWED_HOSTS[-1]
                try:
                    form.save(request=request, use_https=True)
                except:
                    print("[WARN] Could not send password reset to %s for user %s" % (email, username))


            # Flex perm
            treq = tmodels.TatlPermFlex(
                user = su,
                substitute_user = None,
                used_permission = "tatl.management.commands.useradd",
                timestamp = timezone.now(),
                content_object = u,
                extra_context = json.dumps({
                }),
            )
            treq.save()

            # Flex verb
            tmodels.TatlVerb(request=None, verb="CREATE", content_object=u,
                extra_context = json.dumps({
                }),
            ).save()

            print("[GOOD] %s added to Majora" % username)
