from django.core.management.base import BaseCommand, CommandError

from majora2 import models
from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings

class Command(BaseCommand):
    help = "Load a list of users"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])
        for line in fh:
            fields = line.strip().split('\t')
            username = fields[0]
            firstname = fields[1]
            lastname = fields[2]
            email = fields[3]
            code = fields[4]            

            try:
                institute = models.Institute.objects.get(code=code)
            except:
                print("[BAD ] %s skipped as %s is not a valid organisation code" % (username, code))
                continue

            u, created = User.objects.get_or_create(username=username)
            u.first_name = firstname
            u.last_name = lastname
            u.email = email
            u.is_active = True
            u.save()

            p, created = models.Profile.objects.get_or_create(user=u)
            p.institute = institute
            p.save()

            
            form = PasswordResetForm({'email': email})
            if form.is_valid():
                request = HttpRequest()
                request.META['SERVER_PORT'] = '443'
                request.META['SERVER_NAME'] = settings.ALLOWED_HOSTS[-1]
                form.save(request=request, use_https=True)
                print("[GOOD] %s added successfully" % username)

