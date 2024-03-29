from django.urls import path, re_path, include
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.generic.base import RedirectView

from . import views
from . import account_views
from . import bot_views
from . import public_views
from . import api_views
from . import tables

urlpatterns = [
    #search
    path('search/', views.search, name='search'),

    path('artifact/<uuid:artifact_uuid>/', views.detail_artifact, name='detail_artifact'),
    re_path(r'artifact/(?P<artifact_dice>[A-z]*-[A-z]*-[A-z]*)/$', views.detail_artifact_dice, name='detail_artifact_dice'),

    path('group/<uuid:group_uuid>/favourite/', views.favourite_group, name='group_favourite'),
    path('group/<uuid:group_uuid>/', views.group_artifact, name='group_artifact'),
    re_path(r'group/(?P<group_dice>[A-z]*-[A-z]*-[A-z]*)/$', views.group_artifact_dice, name='group_artifact_dice'),

    path('process/<uuid:process_uuid>/', views.detail_process, name='detail_process'),
    path('chain/<uuid:pgroup_uuid>/favourite/', views.favourite_pgroup, name='pgroup_favourite'),
    path('chain/<uuid:group_uuid>/', views.group_process, name='group_process'),

    path('accounts/profile/', views.profile, name='profile'),
    path('keys/list/', account_views.api_keys, name='api_keys'),
    path('keys/activate/', account_views.api_keys_activate, name='api_keys_activate'),
    path('accounts/profile/agreements/<str:slug>/', account_views.view_agreement, name='view_agreement'),
    path('accounts/profile/agreements/', account_views.agreements, name='agreements'),
    path('accounts/profile/mdv/', account_views.list_dataviews, name='list_profile_mdv'),

    # DATAMATRIX ###############################################################
    path('dm/<uuid:uuid>/', views.barcode, name="barcode"),

    # FORMS ####################################################################
    path('forms/account/', account_views.form_account, name='form_account'),
    path('forms/register/', account_views.form_register, name='form_register'),
    path('forms/institute/', account_views.form_institute, name='form_institute'),
    path('forms/credit/', account_views.form_credit, name='form_credit'),
    path('forms/credit/<str:credit_code>', account_views.form_credit, name='form_credit'),

    # BOT ######################################################################
    path('bot/accounts/approve', csrf_exempt(bot_views.bot_approve_registration)),

    # PUBLIC
    path('public/dashboard', RedirectView.as_view(url='https://status.covid19.climb.ac.uk/')),
    path('public/facts', public_views.view_facts),
    path('public/accessions', public_views.list_accessions),
    path('public/author', public_views.render_architect, name="architect"),

    # PRIV MAJORA-TOKEN
    path('accounts/keys/', account_views.list_ssh_keys, name='list_ssh_keys'),
    path('accounts/keys/<str:username>', account_views.list_ssh_keys, name='list_ssh_keys'),
    path('accounts/keys/<str:username>/', account_views.list_ssh_keys, name='list_ssh_keys'), # Hack to prevent curl errors w and wo slash
    path('accounts/names/', account_views.list_user_names, name='list_user_names'),

    # NEW API
    path('api/v2/artifact/biosample/addempty/', csrf_exempt(api_views.addempty_biosample), name="api.artifact.biosample.addempty"),
    path('api/v2/artifact/biosample/add/', csrf_exempt(api_views.BiosampleArtifactEndpointView.as_view()), name="api.artifact.biosample.add"),
    path('api/v2/artifact/biosample/update/', csrf_exempt(api_views.BiosampleArtifactEndpointView.as_view()), name="api.artifact.biosample.update"),
    path('api/v2/artifact/biosample/get/', csrf_exempt(api_views.get_biosample), name="api.artifact.biosample.get"),
    path('api/v2/artifact/library/add/', csrf_exempt(api_views.add_library), name="api.artifact.library.add"),
    path('api/v2/artifact/file/add/', csrf_exempt(api_views.add_digitalresource), name="api.artifact.file.add"),
    path('api/v2/process/sequencing/add/', csrf_exempt(api_views.add_sequencing), name="api.process.sequencing.add"),
    path('api/v2/process/sequencing/get/', csrf_exempt(api_views.get_sequencing), name="api.process.sequencing.get"),
    path('api/v2/process/sequencing/get2/', csrf_exempt(api_views.get_sequencing2), name="api.process.sequencing.get2"),
    path('api/v2/meta/tag/add/', csrf_exempt(api_views.add_tag), name="api.meta.tag.add"),
    path('api/v2/meta/metric/add/', csrf_exempt(api_views.add_metrics), name="api.meta.metric.add"),
    path('api/v2/meta/qc/add/', csrf_exempt(api_views.add_qc), name="api.meta.qc.add"),
    path('api/v2/pag/accession/add/', csrf_exempt(api_views.add_pag_accession), name="api.pag.accession.add"),
    path('api/v2/pag/qc/get/', csrf_exempt(api_views.get_pag_by_qc_celery), name="api.pag.qc.get"),
    path('api/v2/majora/summary/get/', csrf_exempt(api_views.get_dashboard_metrics), name="api.majora.summary.get"),
    path('api/v2/outbound/summary/get/', csrf_exempt(api_views.get_outbound_summary), name="api.outbound.summary.get"),

    # TEMPORARY SPECIAL QUERIES
    path('api/v2/artifact/biosample/query/validity/', csrf_exempt(api_views.biosample_query_validity), name="api.artifact.biosample.query.validity"),

    path('api/v2/group/mag/get/', csrf_exempt(api_views.get_mag), name="api.group.mag.get"),
    path('api/v2/group/pag/suppress/', csrf_exempt(api_views.suppress_pag), name="api.group.pag.suppress"),

    path('api/v2/majora/task/get/', csrf_exempt(api_views.get_task_result), name="api.majora.task.get"),

    path('api/datatable/pag/', public_views.OrderListJson.as_view(), name='api.datatable.pag.get'),
    path('api/datatable/biosample/', login_required(tables.BiosampleOrderListJson.as_view()), name='api.datatable.biosample.get'),


    # Experimental
    path('api/v0/artifact/info/', csrf_exempt(api_views.v0_get_artifact_info), name="api.artifact.info"),

    # Home
    path('', views.home, name='home'),

]


from rest_framework.schemas import get_schema_view
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.routers import DefaultRouter
from . import resty_views

# v3 API did not really take off because the performance was garbage
# only thing left using v3 is the majora data view (MDV) which needs deprecating eventually too
router = DefaultRouter()
router.register(r'mdv', resty_views.RestyDataview, basename="api.v3.majora.mdv")


urlpatterns += [
    # Exciting new v3 API
    path('api/v3/', include(router.urls)),

    # Exciting new v3 docs
    path('api/v3/docs/openapi/', get_schema_view(
        title="Majora",
        description="...",
        version="3.0.0",
    ), name='openapi-schema'),
    path('api/v3/docs/redoc/', TemplateView.as_view(
        template_name='redoc.html',
        extra_context={'schema_url':'openapi-schema'}
    ), name='redoc'),
]

#urlpatterns = format_suffix_patterns(urlpatterns)
