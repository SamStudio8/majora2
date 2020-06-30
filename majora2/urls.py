from django.urls import path,re_path

from django.views.decorators.csrf import csrf_exempt

from . import views
from . import account_views
from . import bot_views
from . import public_views
from . import api_views

urlpatterns = [
    #search
    path('artifact/tabulate/', views.tabulate_artifact, name='tabulate_artifact'),
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
    path('keys/activate/<str:key_name>', account_views.api_keys_activate, name='api_keys_activate'),
    path('institute/profiles/', account_views.list_site_profiles, name='list_site_profiles'),

    # DATAMATRIX ###############################################################
    path('dm/<uuid:uuid>/', views.barcode, name="barcode"),

    # FORMS ####################################################################
    #path('forms/testsample/', views.form_sampletest, name='form_sampletest'),
    path('forms/account/', account_views.form_account, name='form_account'),
    path('forms/register/', account_views.form_register, name='form_register'),
    path('forms/institute/', account_views.form_institute, name='form_institute'),
    
    # BOT ######################################################################
    path('bot/accounts/approve', csrf_exempt(bot_views.bot_approve_registration)),

    # PUBLIC
    path('public/dashboard', public_views.sample_sequence_count_dashboard),
    path('public/accessions', public_views.list_accessions),
    path('public/metametrics', public_views.metadata_metrics),

    # PRIV MAJORA-TOKEN
    path('accounts/keys/', account_views.list_ssh_keys, name='list_ssh_keys'),
    path('accounts/keys/<str:username>', account_views.list_ssh_keys, name='list_ssh_keys'),
    path('accounts/keys/<str:username>/', account_views.list_ssh_keys, name='list_ssh_keys'), # Hack to prevent curl errors w and wo slash
    path('accounts/names/', account_views.list_user_names, name='list_user_names'),

    # NEW API
    path('api/v2/artifact/biosample/add/', csrf_exempt(api_views.add_biosample), name="api.artifact.biosample.add"),
    path('api/v2/artifact/biosample/get/', csrf_exempt(api_views.get_biosample), name="api.artifact.biosample.get"),
    path('api/v2/artifact/library/add/', csrf_exempt(api_views.add_library), name="api.artifact.library.add"),
    path('api/v2/artifact/file/add/', csrf_exempt(api_views.add_digitalresource), name="api.artifact.file.add"),
    #path('api/v2/process/pipeline/add/', csrf_exempt(api_views.add_pipeline), name="api.process.pipeline.add"),
    path('api/v2/process/sequencing/add/', csrf_exempt(api_views.add_sequencing), name="api.process.sequencing.add"),
    path('api/v2/process/sequencing/get/', csrf_exempt(api_views.get_sequencing), name="api.process.sequencing.get"),
    path('api/v2/meta/tag/add/', csrf_exempt(api_views.add_tag), name="api.meta.tag.add"),
    path('api/v2/meta/metric/add/', csrf_exempt(api_views.add_metrics), name="api.meta.metric.add"),
    path('api/v2/meta/qc/add/', csrf_exempt(api_views.add_qc), name="api.meta.qc.add"),
    path('api/v2/pag/accession/add/', csrf_exempt(api_views.add_pag_accession), name="api.pag.accession.add"),
    path('api/v2/pag/qc/get/', csrf_exempt(api_views.get_pag_by_qc_celery), name="api.pag.qc.get"),
    path('api/v2/majora/summary/get/', csrf_exempt(api_views.get_dashboard_metrics), name="api.majora.summary.get"),

    #path('api/v2/artifact/digitalresource/add/', csrf_exempt(api_views.add_digitalresource), name="api.artifact.digitalresource.add"),


    path('api/v2/majora/task/get/', csrf_exempt(api_views.get_task_result), name="api.majora.task.get"),
    path('api/v2/majora/task/delete/', csrf_exempt(api_views.del_task_result), name="api.majora.task.delete"),

    path('api/datatable/pag/', public_views.OrderListJson.as_view(), name='api.datatable.pag.get'),

    # Home
    path('', views.home, name='home'),
]
