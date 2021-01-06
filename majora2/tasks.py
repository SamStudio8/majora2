# Create your tasks here
from __future__ import absolute_import, unicode_literals

from celery import shared_task, current_task
from . import models
from . import serializers
from . import resty_serializers
from . import util

from django.db.models import Q, F

import datetime

from tatl.models import TatlVerb, TatlRequest

@shared_task
def structify_pags(api_o):
    # Return everything?
    api_o["get"] = {}
    api_o["get"]["result"] = serializers.PAGQCSerializer(models.PAGQualityReportEquivalenceGroup.objects.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
    return api_o

@shared_task
def task_get_sequencing_faster(request, api_o, json_data, user=None, **kwargs):

    run_names = list(models.DNASequencingProcess.objects.all().values_list("run_name", flat=True))

    n_runs = 0
    n_libs = 0
    n_biosamples = 0

    api_o["get"] = {}
    api_o["get"]["result"] = {}

    # Serialise all the PAG names at once, and look them up, instead of hitting the database 150,000 times
    pag_lookup = {}
    for published_name, artifact_dice in models.PublishedArtifactGroup.objects.filter(tagged_artifacts__biosampleartifact__isnull=False, is_latest=True).values_list("published_name", "tagged_artifacts__biosampleartifact__dice_name"):
        if artifact_dice not in pag_lookup:
            pag_lookup[artifact_dice] = []
        pag_lookup[artifact_dice].append(published_name)

    for run_name in run_names:

        try:
            process = models.DNASequencingProcess.objects.get(run_name=run_name)
            n_runs += 1

            lib_ids = models.MajoraArtifactProcessRecord.objects.filter(process_id=process.id).values_list("in_artifact__id", flat=True).distinct()

            run = process.as_struct(deep=False)
            run["libraries"] = []


            for lib_id in lib_ids:
                n_libs += 1
                lib_obj = models.LibraryArtifact.objects.get(id=lib_id)
                lib = lib_obj.as_struct(deep=False)

                biosample_ids = models.MajoraArtifactProcessRecord.objects.filter(out_artifact__id=lib_id).values_list("in_artifact__id", flat=True).distinct()
                lib["biosamples"] = {x["central_sample_id"]: x for x in models.BiosampleArtifact.objects.filter(id__in=biosample_ids).values(
                    'central_sample_id',
                    'root_sample_id',
                    'sample_type_collected',
                    'root_biosample_source_id',
                    collection_date=F('created__biosourcesamplingprocess__collection_date'),
                    received_date=F('created__biosourcesamplingprocess__received_date'),
                    submission_user=F('created__biosourcesamplingprocess__submission_user__username'),
                    submission_org=F('created__biosourcesamplingprocess__submission_org__name'),
                    submission_org_code=F('created__biosourcesamplingprocess__submission_org__code'),
                    source_sex=F('created__biosourcesamplingprocess__source_sex'),
                    source_age=F('created__biosourcesamplingprocess__source_age'),
                    adm0=F('created__biosourcesamplingprocess__collection_location_country'),
                    adm1=F('created__biosourcesamplingprocess__collection_location_adm1'),
                    adm2=F('created__biosourcesamplingprocess__collection_location_adm2'),
                    adm2_private=F('created__biosourcesamplingprocess__private_collection_location_adm2'),
                    is_surveillance=F('created__biosourcesamplingprocess__coguk_supp__is_surveillance'),
                    collection_pillar=F('created__biosourcesamplingprocess__coguk_supp__collection_pillar'),
                    biosample_source_id=F('created__records__in_group__biosamplesource__secondary_id'),
                    source_type=F('created__records__in_group__biosamplesource__source_type'),
                    sample_type_received=F('sample_type_current'),
                    swab_site=F('sample_site'),
                )}
                lib["metadata"] = lib_obj.get_metadata_as_struct()

                # Preload ALL biosample metadata records for this lib
                biosample_metadata = {}
                for record in models.MajoraMetaRecord.objects.filter(artifact__id__in=biosample_ids, restricted=False).values('meta_tag', 'meta_name', 'value', 'artifact__dice_name'):
                    if record["artifact__dice_name"] not in biosample_metadata:
                        biosample_metadata[record["artifact__dice_name"]] = {}
                    if record["meta_tag"] not in biosample_metadata[record["artifact__dice_name"]]:
                        biosample_metadata[record["artifact__dice_name"]][record["meta_tag"]] = {}
                    biosample_metadata[record["artifact__dice_name"]][record["meta_tag"]][record["meta_name"]] = record["value"]

                # Preload ALL biosample-pool records for this lib
                biosample_pooling = {x["in_artifact__dice_name"]: x for x in models.LibraryPoolingProcessRecord.objects.filter(out_artifact__id=lib_id).values(
                    "in_artifact__dice_name",
                    "library_strategy",
                    "library_source",
                    "library_selection",
                    "library_protocol",
                    "library_primers",
                    library_adaptor_barcode=F("barcode"),
                )}

                # Load all the metrics for this lib
                biosample_metrics = {}
                for metric in models.TemporaryMajoraArtifactMetric.objects.filter(artifact_id__in=biosample_ids):
                    if metric.artifact.dice_name not in biosample_metrics:
                        biosample_metrics[metric.artifact.dice_name] = {}
                    biosample_metrics[metric.artifact.dice_name][metric.namespace] = metric.as_struct()

                for bs in lib["biosamples"]:
                    n_biosamples += 1
                    lib["biosamples"][bs].update(biosample_pooling.get(bs, {}))
                    lib["biosamples"][bs]["metrics"] = biosample_metrics.get(bs, {})
                    lib["biosamples"][bs]["metadata"] = biosample_metadata.get(bs, {})
                    lib["biosamples"][bs]["published_as"] = ",".join( set(pag_lookup.get(bs, [])) )

                    # Force to match previous seq get interface
                    lib["biosamples"][bs]["collected_by"] = ""
                    del lib["biosamples"][bs]["in_artifact__dice_name"]
                    del lib["biosamples"][bs]["source_type"]

                    if lib["biosamples"][bs]["collection_date"]:
                        lib["biosamples"][bs]["collection_date"] = lib["biosamples"][bs]["collection_date"].strftime("%Y-%m-%d")
                    if lib["biosamples"][bs]["received_date"]:
                        lib["biosamples"][bs]["received_date"] = lib["biosamples"][bs]["received_date"].strftime("%Y-%m-%d")
                    if lib["biosamples"][bs]["is_surveillance"] is None:
                        lib["biosamples"][bs]["is_surveillance"] = ""

                run["libraries"].append(lib)

            api_o["get"]["result"][process.run_name] = run

        except Exception as e:
            api_o["errors"] += 1
            api_o["ignored"].append(run_name)
            api_o["messages"].append(str(e))

    try:
        api_o["get"]["count"] = n_runs
        api_o["get"]["legend"] = {
            #"biosample": bs_api_key_fields,
        }
        api_o["get"]["count_detail"] = (n_runs, n_libs, n_biosamples)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o


@shared_task
def task_get_sequencing(request, api_o, json_data, user=None, **kwargs):
    run_names = json_data.get("run_name")
    if not run_names:
        api_o["messages"].append("'run_name' key missing or empty")
        api_o["errors"] += 1
        return

    if len(run_names) == 1 and run_names[0] == "*":
        #TODO Cannot check staff status here, relies on checking in the calling view.
        run_names = [run["run_name"] for run in models.DNASequencingProcess.objects.all().values("run_name")]

    runs = {}
    for run_name in run_names:
        try:
            process = models.DNASequencingProcess.objects.get(run_name=run_name)
        except Exception as e:
            api_o["warnings"] += 1
            api_o["ignored"].append(run_name)
            continue

        try:
            runs[process.run_name] = process.as_struct()
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))
            continue

    try:
        api_o["get"] = {}
        api_o["get"]["result"] = runs
        api_o["get"]["count"] = len(runs)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o


@shared_task
def task_get_pag_by_qc_faster(request, api_o, json_data, user=None, **kwargs):
    test_name = json_data.get("test_name")

    if not test_name or len(test_name) == 0:
        api_o["messages"].append("'test_name', key missing or empty")
        api_o["errors"] += 1
        return
    t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=test_name).first()
    if not t_group:
        api_o["messages"].append("Invalid 'test_name'")
        api_o["ignored"].append(test_name)
        api_o["errors"] += 1
        return

    base_q = Q(
        groups__publishedartifactgroup__isnull=False, # has PAG
        groups__publishedartifactgroup__quality_groups__test_group=t_group, # Has result for this QC test
        groups__publishedartifactgroup__is_latest=True, # Is latest
    )

    if json_data.get("published_after"):
        try:
            gt_date = datetime.datetime.strptime(json_data["published_after"], "%Y-%m-%d")
            base_q = base_q | Q(
                groups__publishedartifactgroup__published_date__gt=gt_date
            )
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    if json_data.get("suppressed_after"):
        try:
            gt_date = datetime.datetime.strptime(json_data["suppressed_after"], "%Y-%m-%d")
            base_q = base_q | Q(
                groups__publishedartifactgroup__suppressed_date__gt=gt_date,
                groups__publishedartifactgroup__is_suppressed=True,
            )
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))
    else:
        base_q = base_q | Q(
            groups__publishedartifactgroup__is_suppressed=False,
        )

    if json_data.get("pass") and json_data.get("fail"):
        status_q= Q() # Should basically be NOP
    elif json_data.get("pass"):
        status_q = Q(groups__publishedartifactgroup__quality_groups__is_pass=True)
    elif json_data.get("fail"):
        status_q = Q(groups__publishedartifactgroup__quality_groups__is_pass=False)
    else:
        pass

    # Perform the query
    artifacts = models.DigitalResourceArtifact.objects.filter(base_q, status_q)

    # Collapse into list items
    artifacts = list(artifacts.values_list('groups__publishedartifactgroup__published_name', 'current_kind', 'current_path', 'current_hash', 'current_size', 'groups__publishedartifactgroup__quality_groups__is_pass'))

    try:
        api_o["get"] = {}
        api_o["get"]["result"] = artifacts
        api_o["get"]["count"] = len(artifacts)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o

@shared_task
def task_get_pag_by_qc(request, api_o, json_data, user=None, **kwargs):
    test_name = json_data.get("test_name")
    dra_current_kind = json_data.get("dra_current_kind")

    if not test_name or len(test_name) == 0:
        api_o["messages"].append("'test_name', key missing or empty")
        api_o["errors"] += 1
        return
    t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=test_name).first()
    if not t_group:
        api_o["messages"].append("Invalid 'test_name'")
        api_o["ignored"].append(test_name)
        api_o["errors"] += 1
        return

    reports = models.PAGQualityReportEquivalenceGroup.objects.filter(test_group=t_group, pag__is_latest=True, pag__is_suppressed=False)

    if json_data.get("published_date"):
        try:
            gt_date = datetime.datetime.strptime(json_data.get("published_after", ""), "%Y-%m-%d")
            reports = reports.filter(pag__published_date__gt=gt_date)
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    if json_data.get("pass") and json_data.get("fail"):
        pass
    elif json_data.get("pass"):
        reports = reports.filter(is_pass=True)
    elif json_data.get("fail"):
        reports = reports.filter(is_pass=False)
    else:
        pass

    # Return only PAGs with the service name, otherwise use the is_pbulic shortcut
    if json_data.get("public") and json_data.get("private"):
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored with both public and private")
        pass
    elif json_data.get("public"):
        if json_data.get("service_name"):
            reports = reports.filter(pag__accessions__service=json_data.get("service_name"), pag__accessions__is_public=True)
        else:
            reports = reports.filter(pag__is_public=True)
    elif json_data.get("private"):
        if json_data.get("service_name"):
            # Exclude any PAG that has this service name (public or not)
            # Private means unsubmitted in this context basically
            reports = reports.filter(~Q(pag__accessions__service=json_data.get("service_name")))
        else:
            reports = reports.filter(pag__is_public=False)
    else:
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored without public or private")
        pass



    try:
        api_o["get"] = {}
        api_o["get"]["result"] = serializers.PAGQCSerializer(reports.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
        api_o["get"]["count"] = len(reports)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o

@shared_task
def task_get_pag_by_qc_v3(pag_ids, context={}):
    queryset = models.PublishedArtifactGroup.objects.filter(id__in=pag_ids)
    serializer = resty_serializers.RestyPublishedArtifactGroupSerializer(queryset, many=True, context=context)

    api_o = {
        "data": serializer.data,
    }

    return api_o

@shared_task
def task_get_mdv_v3(ids, context={}, **kwargs):
    from django.apps import apps

    mdv = models.MajoraDataview.objects.get(code_name=context["mdv"])

    treq = None
    if kwargs.get("response_uuid"):
        treq = TatlRequest.objects.get(response_uuid=kwargs.get("response_uuid"))
        TatlVerb(request=treq, verb="RETRIEVE", content_object=mdv).save()

    model = apps.get_model("majora2", mdv.entry_point)
    queryset = model.objects.filter(id__in=ids)

    context["mdv_fields"] = util.get_mdv_fields(context["mdv"])
    serializer = model.get_resty_serializer()(queryset, many=True, context=context)

    api_o = {
        "data": serializer.data,
    }


    return api_o
