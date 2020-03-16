from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt

from . import views

urlpatterns = [
    url(r'node/(?P<node_uuid>[0-9a-f-]+)/$', views.detail_node, name='detail_node'),
    url(r'group/(?P<group_uuid>[0-9a-f-]+)/$', views.list_group_resources, name='list_resources'),
    url(r'resource/(?P<resource_uuid>[0-9a-f-]+)/$', views.detail_resource, name='detail_resource'),
    url(r'command/(?P<command_uuid>[0-9a-f-]+)/$', views.detail_command, name='detail_command'),

    # API
    url(r'api/command/update/$', csrf_exempt(views.update_command), name='update_command'),
    url(r'api/command/new/$', csrf_exempt(views.new_command), name='new_command'),
    url(r'api/resource/meta/$', csrf_exempt(views.tag_meta), name='tag_meta'),
    url(r'api/resource/group/$', csrf_exempt(views.group_resources), name='group_resources'),

    #url(r'meta/(?P<q_type>[a-Z]+)/$', views.tabulate, name='tabulate'),
    url(r'meta/$', views.tabulate, name='tabulate'),

    # Home
    url(r'search/$', views.search, name='search'),
    url(r'$', views.home, name='home'),
]
