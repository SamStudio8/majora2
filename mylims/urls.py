"""mylims URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views

from two_factor.urls import urlpatterns as tf_urls

from tatl.views import oauth2_callback

urlpatterns = [
    path('admin/', admin.site.urls),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('o/callback/', oauth2_callback, name='tatl_oauth2_callback'),

    #path('accounts/login/', auth_views.LoginView.as_view(
    #    template_name='admin/login.html',
    #    redirect_authenticated_user=True,
    #    extra_context={
    #        'site_header': 'Majora',
    #        'site_title': 'Majora',
    #        'title': 'Authenticate',
    #        #'next': '/accounts/profile/',
    #    }),
    #    name="login",
    #),
    path('account/logout/', auth_views.LogoutView.as_view(
        next_page='/',
    ), name="logout"),

    path('', include('majora2.urls')),
    path('', include('deku.urls')),
    path('', include(tf_urls)),
    path('account/', include('django.contrib.auth.urls')), # tf login will supercede this
]
