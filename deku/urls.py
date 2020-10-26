from django.urls import path, re_path, include
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt

from . import views

urlpatterns = [
    path('accounts/list/', views.list_all_profiles, name='list_all_profiles'),

    path('institute/profiles/', views.list_site_profiles, name='list_site_profiles'),
]
