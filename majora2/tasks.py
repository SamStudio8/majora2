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
                    "sequencing_org_received_date",
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

                    if lib["biosamples"][bs]["sequencing_org_received_date"]:
                        lib["biosamples"][bs]["sequencing_org_received_date"] = lib["biosamples"][bs]["sequencing_org_received_date"].strftime("%Y-%m-%d")
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
        return api_o

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
def task_get_pag_v2(request, api_o, json_data, user=None, **kwargs):
    pag_ids = _get_pags_by_qc_options(None, api_o, json_data)
    if len(pag_ids) == 0:
        api_o["messages"].append("No PAGs found.")

    pags = {x["published_name"]: x for x in models.PublishedArtifactGroup.objects.filter(
            id__in=pag_ids,
    ).values(
            'published_name',
            'published_version',
            'published_date',
            owner_institute_code=F('owner__profile__institute__code'),
            published_uuid=F('id'),
            owner_org_ena_assembly_opted=F('owner__profile__institute__ena_assembly_opted'),
            owner_org_ena_opted=F('owner__profile__institute__ena_opted'),
            owner_org_gisaid_opted=F('owner__profile__institute__gisaid_opted'),

            # Inserted for compat with deprecated task_get_pag_by_qc
            owner_username=F('owner__username'),
            owner_org_code=F('owner__profile__institute__code'),
            owner_org_name=F('owner__profile__institute__name'),
            owner_org_gisaid_user=F('owner__profile__institute__gisaid_user'),
            owner_org_gisaid_mail=F('owner__profile__institute__gisaid_mail'),
    )}

    # adm1 lookup
    countries = {
        "UK-ENG": "England",
        "UK-WLS": "Wales",
        "UK-SCT": "Scotland",
        "UK-NIR": "Northern_Ireland",
    }

    # get v1 credit
    v1_credits_lookup = {x["institute_code"]: x for x in models.Institute.objects.values(
            credit_code=F('code'),
            institute_code=F('code'),
            credit_lab_org_name=F('name'),
            credit_lab_name=F('gisaid_lab_name'),
            credit_lab_addr=F('gisaid_lab_addr'),
            credit_lab_list=F('gisaid_list'),
    )}
    for code, c in v1_credits_lookup.items():
        if not c["credit_lab_name"] or len(c["credit_lab_name"]) == 0:
            c["credit_lab_name"] = c["credit_lab_org_name"]

    # build v2 credit code map
    credit_codes_lookup = {}
    credits = models.InstituteCredit.objects.values(
            'credit_code',
            institute_code=F('institute__code'),
            credit_lab_org_name=F('institute__name'),
            credit_lab_name=F('lab_name'),
            credit_lab_addr=F('lab_addr'),
            credit_lab_list=F('lab_list'),
    )
    for ic in credits:
        if ic["institute_code"] not in credit_codes_lookup:
            credit_codes_lookup[ic["institute_code"]] = {}
        credit_codes_lookup[ ic["institute_code"] ][ ic["credit_code"] ] = ic

    # build pag to run map
    # This is gross and only works because we use the run_name as a key on the PAG
    # In future we'd do well to lock processes in to the PAG directly I think
    run_to_pag = {}
    pag_ids = []
    for pag in pags:
        try:
            run_name = pag.split(':')[1]
        except:
            run_name = pag
        if run_name not in run_to_pag:
            run_to_pag[run_name] = []
        run_to_pag[run_name].append(pag)
        pag_ids.append(pags[pag]["published_uuid"])
        pags[pag]["artifacts"] = {}
        pags[pag]["published_date"] = pags[pag]["published_date"].strftime("%Y-%m-%d")

    # get accessions and match to pag
    accessions = models.TemporaryAccessionRecord.objects.filter(pag__id__in=pag_ids, is_public=True).values(
            'pag__published_name',
            'service',
            'primary_accession',
            'secondary_accession',
    )
    for acc in accessions:
        published_name = acc["pag__published_name"]
        del acc["pag__published_name"]

        service = acc["service"]
        del acc["service"]

        if "accessions" not in pags[published_name]:
            pags[published_name]["accessions"] = {}
        pags[published_name]["accessions"][service] = acc

    # get sequencing processeses
    #NOTE probably get slow performance with the run_name__in filter but it'll be faster than processing every run overall i reckon
    sequencing_procs = models.DNASequencingProcess.objects.filter(run_name__in=list(run_to_pag.keys())).values(
            'id',
            'run_name',
            'instrument_make',
            'instrument_model',
    )

    run_to_library_lookup = {}
    for run in sequencing_procs:
        # determine the run
        run_name = run["run_name"]
        for pag in run_to_pag[run_name]:
            pags[pag]["artifacts"]["sequencing"] = [run] # cheat to make this fit the old ocarina api format

        # get library info and match the biosample and run combo
        # ffs this is also gross, should have put the library in the fucking pag, i hate myself
        # we roll up to the biosample name here because you can't upload the same sample on two libraries on the same run (yet)
        lib_ids = models.MajoraArtifactProcessRecord.objects.filter(process_id=run["id"]).values_list("in_artifact__id", flat=True).distinct()
        biosample_pooling = {x["in_artifact__dice_name"]: x for x in models.LibraryPoolingProcessRecord.objects.filter(out_artifact__id__in=lib_ids).values(
                    "in_artifact__dice_name",
                    "library_strategy",
                    "library_source",
                    "library_selection",
                    "library_protocol",
                    "library_primers",
                    "sequencing_org_received_date",
                    seq_kit=F('out_artifact__libraryartifact__seq_kit'),
                    seq_protocol=F('out_artifact__libraryartifact__seq_protocol'),
                    library_adaptor_barcode=F("barcode"),
        )}
        if run_name not in run_to_library_lookup:
            run_to_library_lookup[run_name] = {}
        run_to_library_lookup[run_name].update(biosample_pooling)

    # get biosamples
    biosamples = models.BiosampleArtifact.objects.filter(
        groups__id__in=pag_ids, # get biosamples in the selected pag set
    ).values(
            'groups__publishedartifactgroup__published_name',
            'central_sample_id',
            collection_date=F('created__biosourcesamplingprocess__collection_date'),
            received_date=F('created__biosourcesamplingprocess__received_date'),
            submission_user=F('created__biosourcesamplingprocess__submission_user__username'),
            submission_org=F('created__biosourcesamplingprocess__submission_org__name'),
            submission_org_credit_name=F('created__biosourcesamplingprocess__submission_org__gisaid_lab_name'),
            submission_org_code=F('created__biosourcesamplingprocess__submission_org__code'),
            adm0=F('created__biosourcesamplingprocess__collection_location_country'),
            adm1=F('created__biosourcesamplingprocess__collection_location_adm1'),
            min_ct=F('metrics__temporarymajoraartifactmetric_thresholdcycle__min_ct'),
            max_ct=F('metrics__temporarymajoraartifactmetric_thresholdcycle__max_ct'),
            is_surveillance=F('created__biosourcesamplingprocess__coguk_supp__is_surveillance'),
            collection_pillar=F('created__biosourcesamplingprocess__coguk_supp__collection_pillar'),
    )
    # get biosample credits
    biosample_credits = {x["artifact__dice_name"]: x["value"].upper() for x in models.MajoraMetaRecord.objects.filter(artifact__groups__id__in=pag_ids, meta_tag='majora', meta_name='credit').values('artifact__dice_name', 'value')}

    for bs in biosamples:
        published_name = bs["groups__publishedartifactgroup__published_name"]
        del bs["groups__publishedartifactgroup__published_name"]

        # map library info
        run_name = pags[published_name]["artifacts"]["sequencing"][0]["run_name"]

        pags[published_name]["artifacts"]["biosample"] = [bs]
        pags[published_name]["artifacts"]["library"] = [run_to_library_lookup[run_name].get(bs["central_sample_id"], {})]

        # resolve credit (tagged on biosample)
        credit_code = biosample_credits.get(bs["central_sample_id"])
        ic = {}
        if credit_code:
            ic = credit_codes_lookup.get(pags[published_name]["owner_institute_code"], {}).get(credit_code, {})
        if not ic:
            ic = v1_credits_lookup.get(pags[published_name]["owner_institute_code"], {})
        pags[published_name].update(ic)

        # trans adm1 (for task_get_pag_by_qc)
        bs["adm1_trans"] = countries.get(bs["adm1"], "")

        # str dates
        #if bs["sequencing_org_received_date"]:
        #    bs["sequencing_org_received_date"] = bs["sequencing_org_received_date"].strftime("%Y-%m-%d") 
        if bs["collection_date"]:
            bs["collection_date"] = bs["collection_date"].strftime("%Y-%m-%d") 
        if bs["received_date"]:
            bs["received_date"] = bs["received_date"].strftime("%Y-%m-%d") 
        if bs["is_surveillance"] is None:
            bs["is_surveillance"] = ""
        if not bs["submission_org_credit_name"] or len(bs["submission_org_credit_name"]) == 0:
            bs["submission_org_credit_name"] = bs["submission_org"]

    # get files 
    artifacts = models.DigitalResourceArtifact.objects.filter(
        groups__id__in=pag_ids, # get files in the selected pag set
    ).values(
                'groups__publishedartifactgroup__published_name',
                'current_kind',
                'current_path',
                'current_hash',
                'current_size',
                num_bases=F('metrics__temporarymajoraartifactmetric_sequence__num_bases'),
                longest_ungap=F('metrics__temporarymajoraartifactmetric_sequence__longest_ungap'),
                pc_acgt=F('metrics__temporarymajoraartifactmetric_sequence__pc_acgt'),
                pc_masked=F('metrics__temporarymajoraartifactmetric_sequence__pc_masked'),
                mean_cov=F('metrics__temporarymajoraartifactmetric_mapping__mean_cov'),
                num_pos=F('metrics__temporarymajoraartifactmetric_mapping__num_pos'),
                pc_pos_cov_gte10=F('metrics__temporarymajoraartifactmetric_mapping__pc_pos_cov_gte10'),
                pc_pos_cov_gte20=F('metrics__temporarymajoraartifactmetric_mapping__pc_pos_cov_gte20'),
                pipe_id=F('created__abstractbioinformaticsprocess__id'),
                pipe_kind=F('created__abstractbioinformaticsprocess__pipe_kind'),
                pipe_name=F('created__abstractbioinformaticsprocess__pipe_name'),
                pipe_version=F('created__abstractbioinformaticsprocess__pipe_version'),
    )
    for dra in artifacts:
        published_name = dra["groups__publishedartifactgroup__published_name"]
        del dra["groups__publishedartifactgroup__published_name"]

        pags[published_name]["artifacts"][dra["current_kind"]] = [dra]

    try:
        api_o["get"] = {}
        api_o["get"]["result"] = [{"published_name": x, "pag": pags[x]} for x in pags]
        api_o["get"]["count"] = len(pags)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o


def _get_pags_by_qc_options(request, api_o, json_data):
    test_name = json_data.get("test_name")

    if not test_name or len(test_name) == 0:
        api_o["messages"].append("'test_name', key missing or empty")
        api_o["errors"] += 1
        return []
    t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=test_name).first()
    if not t_group:
        api_o["messages"].append("Invalid 'test_name'")
        api_o["ignored"].append(test_name)
        api_o["errors"] += 1
        return []

    base_q = Q(
        is_latest = True,
        quality_groups__test_group = t_group,
    )

    if json_data.get("published_after"):
        try:
            gt_date = datetime.datetime.strptime(json_data["published_after"], "%Y-%m-%d")
            base_q = base_q & Q(
                published_date__gt=gt_date
            )
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    if json_data.get("suppressed_after"):
        try:
            gt_date = datetime.datetime.strptime(json_data["suppressed_after"], "%Y-%m-%d")
            base_q = base_q & Q(
                suppressed_date__gt=gt_date,
                is_suppressed=True,
            )
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))
            return []
    else:
        base_q = base_q & Q(
            is_suppressed=False,
        )

    # Return only PAGs with the service name, otherwise use the is_public shortcut
    if json_data.get("public") and json_data.get("private"):
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored with both public and private")

    elif json_data.get("public"):
        if json_data.get("service_name"):
            base_q = base_q & Q(
                accessions__service=json_data.get("service_name"),
                accessions__is_public=True,
            )
        else:
            base_q = base_q & Q(
                is_public=True,
            )

    elif json_data.get("private"):
        if json_data.get("service_name"):
            # Exclude any PAG that has this service name (public or not)
            # Private means unsubmitted in this context basically
            base_q = base_q & Q(
                ~Q(accessions__service=json_data.get("service_name")),
            )
        else:
            base_q = base_q & Q(
                is_public=False,
            )

    else:
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored without public or private")


    # Pass/Fail QC status
    if json_data.get("pass") and json_data.get("fail"):
        status_q= Q(quality_groups__isnull=False) # must have a result
    elif json_data.get("pass"):
        status_q = Q(quality_groups__is_pass=True)
    elif json_data.get("fail"):
        status_q = Q(quality_groups__is_pass=False)
    else:
        status_q= Q() # Should basically be NOP

    return models.PublishedArtifactGroup.objects.filter(base_q & status_q).values_list('id', flat=True)


@shared_task
def task_get_pagfiles(request, api_o, json_data, user=None, **kwargs):
    pag_ids = _get_pags_by_qc_options(None, api_o, json_data)
    if len(pag_ids) == 0:
        api_o["messages"].append("No PAGs found")
    else:
        api_o["messages"].append("%d PAGs found" % len(pag_ids))

    #TODO
    t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=json_data.get("test_name")).first()
    artifacts = models.DigitalResourceArtifact.objects.filter(groups__id__in=pag_ids, groups__publishedartifactgroup__quality_groups__test_group = t_group)

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
