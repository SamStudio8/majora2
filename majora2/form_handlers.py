import datetime
import dateutil.parser

from django.utils import timezone

from . import models
from . import signals
from . import util
from . import fixed_data

from tatl.models import TatlVerb

def _format_tuple(x):
    if hasattr(x, "process_kind"):
        return (x.kind, str(x.id), "")
    elif hasattr(x, "group_kind"):
        if x.group_kind == "Published Artifact Group":
            return (x.kind, str(x.id), x.published_name)
        else:
            return (x.kind, str(x.id), x.dice_name)
    else:
        return (x.kind, str(x.id), x.dice_name)

def handle_testmetadata(form, user=None, api_o=None, request=None):

    artifact = form.cleaned_data.get("artifact")
    group = form.cleaned_data.get("group")
    process = form.cleaned_data.get("process")

    tag = form.cleaned_data.get("tag")
    name = form.cleaned_data.get("name")
    value = form.cleaned_data.get("value")

    timestamp = form.cleaned_data.get("timestamp")

    restricted = False
    if hasattr(fixed_data, "RESTRICTED_METADATA"):
        if tag in fixed_data.RESTRICTED_METADATA:
            restricted = True

    mr, created = models.MajoraMetaRecord.objects.get_or_create(
            artifact=artifact,
            group=group,
            process=process,
            meta_tag=tag,
            meta_name=name,
            value_type="str",
    )
    mr.value=value
    mr.timestamp = timestamp
    mr.restricted=restricted
    mr.save()
    return mr, created

def handle_testsequencing(form, user=None, api_o=None, request=None):

    sequencing_id = form.cleaned_data.get("sequencing_id")
    if sequencing_id:
        if form.cleaned_data.get("run_name"):
            run_name = form.cleaned_data.get("run_name")
        else:
            run_name = str(sequencing_id)
        p, sequencing_created = models.DNASequencingProcess.objects.get_or_create(pk=sequencing_id, run_name=run_name)
    else:
        run_name = form.cleaned_data["run_name"]
        p, sequencing_created = models.DNASequencingProcess.objects.get_or_create(run_name=run_name)

    if not p:
        return None, False

    run_group = form.cleaned_data.get("run_group")
    if not run_group:
        run_group = run_name
    p.run_group = run_group
    p.instrument_make = form.cleaned_data["instrument_make"]
    p.instrument_model = form.cleaned_data["instrument_model"]
    p.flowcell_type = form.cleaned_data["flowcell_type"]
    p.flowcell_id = form.cleaned_data["flowcell_id"]

    p.start_time = form.cleaned_data["start_time"]
    p.end_time = form.cleaned_data["end_time"]

    if p.start_time and p.end_time:
        duration = p.end_time - p.start_time

    if sequencing_created:
        if api_o:
            api_o["new"].append(_format_tuple(p))
            TatlVerb(request=request.treq, verb="CREATE", content_object=p).save()

        # Try and infer a date from the library name...
        _dt = util.try_date(run_name)
        created_dt = None
        if p.start_time:
            created_dt = p.start_time
        elif _dt:
            created_dt = _dt
        else:
            created_dt = timezone.now()

        p.who = user
        p.when = created_dt
    else:
        if api_o:
            api_o["updated"].append(_format_tuple(p))
            TatlVerb(request=request.treq, verb="UPDATE", content_object=p).save()
    p.save()


    # Create placeholder digitalgroup
    dgroup, dgroup_created = models.DigitalResourceGroup.objects.get_or_create(
            unique_name="sequencing-dummy-tree-%s" % run_name,
            dice_name="sequencing-dummy-tree-%s" % run_name,
            current_name="sequencing-dummy-tree-%s" % run_name,
            physical=False
    )
    rec, rec_created = models.DNASequencingProcessRecord.objects.get_or_create(
        process=p,
        in_artifact=form.cleaned_data.get("library_name"),
        out_group=dgroup,
    )
    rec.save()

    if dgroup_created:
        # Placeholder basecalling
        bio = models.AbstractBioinformaticsProcess(
            who = user,
            when = p.when,
            pipe_kind = "Basecalling",
        )
        bio.save()
        a = models.DigitalResourceArtifact(
                dice_name="sequencing-dummy-reads-%s" % run_name,
                current_name="sequencing-dummy-reads-%s" % run_name,
                current_kind="dummy",
        )
        a.save()
        rec2 = models.MajoraArtifactProcessRecord(
            process=bio,
            in_group=dgroup,
            out_artifact=a,
        )
        a.created = bio
        a.save()
        rec2.save()
        if api_o:
            api_o["new"].append(_format_tuple(dgroup))
            api_o["new"].append(_format_tuple(a))
            TatlVerb(request=request.treq, verb="CREATE", content_object=dgroup).save()
            TatlVerb(request=request.treq, verb="CREATE", content_object=a).save()

    # Placeholder downstream pipeline
    # This will allow us to accept and overwrite basic bioinformatics information
    # see https://github.com/SamStudio8/majora/issues/45
    pipe, pipe_created = models.AbstractBioinformaticsProcess.objects.get_or_create(
            pipe_kind = "Pipeline",
            hook_name = "bioinfo-%s" % run_name,
    )
    if pipe_created:
        pipe.who = user
        pipe.when = p.when

        # It would be nice to inject the dummy reads as the sources of this process
        # but the records have a 1:1 mapping with the FASTA and BAM which won't be
        # in scope until Elan sets them up later...
        #pipe_record, pipe_record_created = models.MajoraArtifactProcessRecord.objects.get_or_create(
        #        process = pipe,
        #        in_artifact = sa,
        #)
        #pipe_record.save()

        if api_o:
            api_o["new"].append(_format_tuple(pipe))
        TatlVerb(request=request.treq, verb="CREATE", content_object=pipe).save()

    pipe.pipe_name = form.cleaned_data.get("bioinfo_pipe_name")
    pipe.pipe_version = form.cleaned_data.get("bioinfo_pipe_version")

    if not pipe_created:
        if api_o:
            api_o["updated"].append(_format_tuple(pipe))
        TatlVerb(request=request.treq, verb="UPDATE", content_object=pipe).save()
    pipe.save()

    return p, sequencing_created


def handle_testlibrary(form, user=None, api_o=None, request=None):
    library_name = form.cleaned_data["library_name"]
    library, library_created = models.LibraryArtifact.objects.get_or_create(
                dice_name=library_name)
    library.layout_config = form.cleaned_data.get("library_layout_config")
    library.layout_read_length = form.cleaned_data.get("library_layout_read_length")
    library.layout_insert_length = form.cleaned_data.get("library_layout_insert_length")
    library.seq_kit = form.cleaned_data.get("library_seq_kit")
    library.seq_protocol = form.cleaned_data.get("library_seq_protocol")

    if library_created:
        if api_o:
            api_o["new"].append(_format_tuple(library))
            TatlVerb(request=request.treq, verb="CREATE", content_object=library).save()

        # Try and infer a date from the library name...
        _dt = util.try_date(library_name)

        # Create the pooling event
        pool_p = models.LibraryPoolingProcess(
            who = user,
            when = _dt if _dt else timezone.now() # useful for sorting
        )
        pool_p.save()
        library.created = pool_p
    else:
        if api_o:
            api_o["updated"].append(_format_tuple(library))
            TatlVerb(request=request.treq, verb="UPDATE", content_object=library).save()
    library.save()
    return library, library_created

def handle_testlibraryrecord(form, user=None, api_o=None, request=None):

    biosample = form.cleaned_data.get("central_sample_id") # will return a biosample object
    library = form.cleaned_data.get("library_name") # will actually return a library object

    if not library.created:
        return None, False

    pool_rec, created = models.LibraryPoolingProcessRecord.objects.get_or_create(
        process=library.created,
        bridge_artifact=biosample,
        in_artifact=biosample,
        out_artifact=library
    )
    pool_rec.library_source = form.cleaned_data.get("library_source")
    pool_rec.library_selection = form.cleaned_data.get("library_selection")
    pool_rec.library_strategy = form.cleaned_data.get("library_strategy")
    pool_rec.library_protocol = form.cleaned_data.get("library_protocol")
    pool_rec.library_primers = form.cleaned_data.get("library_primers")
    pool_rec.sequencing_org_received_date = form.cleaned_data.get("sequencing_org_received_date")
    pool_rec.save()
    if api_o and created:
        api_o["updated"].append(_format_tuple(biosample))
        TatlVerb(request=request.treq, verb="UPDATE", content_object=biosample).save()
    return pool_rec, created



def handle_testsample(form, user=None, api_o=None, request=None):
    biosample_source_id = form.cleaned_data.get("biosample_source_id")
    if biosample_source_id:
        # Get or create the BiosampleSource
        source, source_created = models.BiosampleSource.objects.get_or_create(
                dice_name=biosample_source_id,
                secondary_id=biosample_source_id,
                source_type = form.cleaned_data.get("source_type"),
                physical=True,
        )
        source.save()
        if source_created:
            if api_o:
                api_o["new"].append(_format_tuple(source))
                TatlVerb(request=request.treq, verb="CREATE", content_object=source).save()
    else:
        source = None


    if type(form.cleaned_data.get("collection_date")) == str:
        collection_date = dateutil.parser.parse(form.cleaned_data.get("collection_date"))
    else:
        collection_date = form.cleaned_data.get("collection_date")
    if type(form.cleaned_data.get("received_date")) == str:
        received_date = dateutil.parser.parse(form.cleaned_data.get("received_date"))
    else:
        received_date = form.cleaned_data.get("received_date")

    # Get or create the Biosample
    sample_id = form.cleaned_data.get("central_sample_id")
    sample, sample_created = models.BiosampleArtifact.objects.get_or_create(
            central_sample_id=sample_id
    )

    if sample:
        sample.root_sample_id = form.cleaned_data.get("root_sample_id")
        sample.sender_sample_id = form.cleaned_data.get("sender_sample_id")
        sample.dice_name = sample_id

        sample.sample_type_collected = form.cleaned_data.get("sample_type_collected")
        sample.sample_type_current = form.cleaned_data.get("sample_type_received")
        sample.sample_site = form.cleaned_data.get("swab_site")

        sample.primary_group = source
        sample.taxonomy_identifier = form.cleaned_data.get("source_taxon")

        sample.save()

    if sample_created:
        if api_o:
            api_o["new"].append(_format_tuple(sample))
            TatlVerb(request=request.treq, verb="CREATE", content_object=sample).save()
    else:
        if api_o:
            api_o["updated"].append(_format_tuple(sample))
            TatlVerb(request=request.treq, verb="UPDATE", content_object=sample).save()

    try:
        submitted_by = form.cleaned_data.get("submitting_org").name
    except:
        submitted_by = None

    if source and sample.created:
        for record in sample.created.records.all():
            if record.in_group != source:
                record.in_group = source
                record.save()

    return sample, sample_created

def handle_testdigitalresource(form, user=None, api_o=None, request=None):

    res_updated = False
    node = form.cleaned_data["node_name"]

    path = form.cleaned_data["path"]
    lpath = path.split( form.cleaned_data["sep"] )[1:-1]

    # Get the directory
    parent = util.get_mag(node.node_name, path, sep=form.cleaned_data["sep"], artifact=True, by_hard_path=True, prefetch=False)
    if not parent:
        if api_o:
            api_o["messages"].append("MAG not found from hard path")
        parent = node
        for i, dir_name in enumerate(lpath):
            dir_g, created = models.DigitalResourceGroup.objects.get_or_create(
                    #group_path=form.cleaned_data["sep"].join(lpath),
                    current_name=dir_name,
                    root_group=node,
                    parent_group=parent,
                    physical=True)
            parent = dir_g

    if form.cleaned_data.get("artifact_uuid"):
        res, created = models.DigitalResourceArtifact.objects.get_or_create(
                id = form.cleaned_data["artifact_uuid"],
        )
        res.primary_group = parent
        res.current_name = form.cleaned_data["current_name"]
        res.current_extension = form.cleaned_data["current_fext"]
    else:
        res, created = models.DigitalResourceArtifact.objects.get_or_create(
                primary_group = parent,
                current_name = form.cleaned_data["current_name"],
                current_extension = form.cleaned_data["current_fext"],
        )

    if res.current_hash != form.cleaned_data["current_hash"] or res.current_size != form.cleaned_data["current_size"]:
        res_updated = True
    res.dice_name = str(res.id)
    res.current_path = path
    res.current_hash = form.cleaned_data["current_hash"]
    res.current_size = form.cleaned_data["current_size"]
    res.current_kind = form.cleaned_data["resource_type"]
    res.save()

    if len(form.cleaned_data.get("source_group")) > 0 or len(form.cleaned_data.get("source_artifact")) > 0:
        try:
            bio, b_created = models.AbstractBioinformaticsProcess.objects.get_or_create(
                hook_name = form.cleaned_data["pipe_hook"],
            )
        except:
            api_o["messages"].append("Race condition caught trying to add another ABP. Dropping to GET. End users can ignore this message.")
            bio, b_created = models.AbstractBioinformaticsProcess.objects.get_or_create(
                hook_name = form.cleaned_data["pipe_hook"],
            )

        bio.who = user # use the uploading user, not the sequencing submitting user
        bio.when = timezone.now()

        if b_created:
            bio.pipe_kind = form.cleaned_data["pipe_kind"]
            bio.pipe_name = form.cleaned_data["pipe_name"]
            bio.pipe_version = form.cleaned_data["pipe_version"]

            if not bio.pipe_kind or len(bio.pipe_kind) == 0:
                bio.pipe_kind = "Pipeline" # for ease of finding later
 
        bio.save()

        for sg in form.cleaned_data.get("source_group"):
            bior, created = models.MajoraArtifactProcessRecord.objects.get_or_create(
                process = bio,
                in_group = sg,
                out_artifact = res,
            )
            bior.bridge_artifact = form.cleaned_data.get("bridge_artifact")
            bior.save()
        for sa in form.cleaned_data.get("source_artifact"):
            bior, created = models.MajoraArtifactProcessRecord.objects.get_or_create(
                process = bio,
                in_artifact = sa,
                out_artifact = res,
            )
            bior.bridge_artifact = form.cleaned_data.get("bridge_artifact")
            bior.save()
            try:
                bio.when = sa.created.when
                bio.save()
            except:
                pass

        if created:
            res.created = bio
            res.save()

    if form.cleaned_data.get("publish_group"):
        #TODO handle versioning using res_updated
        #TODO Likely that only the FASTA changes, how to know to drag the BAM across?
        #       Perhaps we need the users to give us a version number?
        pag, pag_created = models.PublishedArtifactGroup.objects.get_or_create(
                published_name=form.cleaned_data.get("publish_group"),
                published_version=1,
                is_latest=True,
                owner=res.created.who,
        )
        if pag_created:
            pag.published_date = timezone.now().date()
        res.groups.add(pag)
        pag.save()
        if form.cleaned_data.get("bridge_artifact"):
            b = form.cleaned_data.get("bridge_artifact")
            b.groups.add(pag)
            b.save()

        if pag_created and api_o:
            api_o["new"].append(_format_tuple(pag))
            TatlVerb(request=request.treq, verb="CREATE", content_object=pag).save()
            if form.cleaned_data.get("bridge_artifact"):
                api_o["updated"].append(_format_tuple(b))
                TatlVerb(request=request.treq, verb="UPDATE", content_object=b).save()

        if res and not created and api_o:
            api_o["updated"].append(_format_tuple(res))
            TatlVerb(request=request.treq, verb="UPDATE", content_object=res).save()


    if created and api_o:
        api_o["new"].append(_format_tuple(res))
        TatlVerb(request=request.treq, verb="CREATE", content_object=res).save()
    elif res_updated:
        api_o["updated"].append(_format_tuple(res))
        TatlVerb(request=request.treq, verb="UPDATE", content_object=res).save()
    return res, created
