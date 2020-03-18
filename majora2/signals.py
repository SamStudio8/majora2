import django.dispatch
new_registration = django.dispatch.Signal(providing_args=["username", "first_name", "last_name", "organisation"])
activated_registration = django.dispatch.Signal(providing_args=["username", "email"])
new_sample = django.dispatch.Signal(providing_args=["sample_id", "submitter"])
