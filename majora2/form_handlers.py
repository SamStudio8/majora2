import datetime
import dateutil.parser

from . import models
from . import signals

def _format_tuple(x):
    if hasattr(x, "process_kind"):
        return (x.kind, str(x.id), "")
    else:
        return (x.kind, str(x.id), x.dice_name)

def handle_testmetadata(form, user=None, api_o=None):

    artifact = form.cleaned_data.get("artifact")
    group = form.cleaned_data.get("group")
    process = form.cleaned_data.get("process")

    tag = form.cleaned_data.get("tag")
    name = form.cleaned_data.get("name")
    value = form.cleaned_data.get("value")

    timestamp = form.cleaned_data.get("timestamp")

    mr, created = models.MajoraMetaRecord.objects.get_or_create(
            artifact=artifact,
            group=group,
            process=process,
            meta_tag=tag,
            meta_name=name,
            value=value,
            value_type="str",
    )
    if created:
        mr.timestamp = timestamp
    mr.save()
    return mr, created

def handle_testsequencing(form, user=None, api_o=None):
    p, sequencing_created = models.DNASequencingProcess.objects.get_or_create(pk=form.cleaned_data["sequencing_id"])

    if not p:
        return None, False

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
        p.when = datetime.datetime.now()
        p.save()

    # Created placeholder digitalgroup
    dgroup, dgroup_created = models.DigitalResourceGroup.objects.get_or_create(
            unique_name="sequencing-filetree-%s" % str(p.id),
            current_name="sequencing-filetree-%s" % str(p.id),
            physical=False
    )
    if dgroup_created:
        a = models.MajoraArtifact(dice_name="seq-test-%s" % str(p.id))
        a.save()
        rec = models.DNASequencingProcessRecord(
            process=p,
            in_artifact=form.cleaned_data.get("library_name"),
            out_group=dgroup,
        )
        rec.save()
        rec2 = models.MajoraArtifactProcessRecord(
            process=p,
            in_group=dgroup,
            out_artifact=a,
        )
        rec2.save()
    return p, sequencing_created


def handle_testlibrary(form, user=None, api_o=None):
    library, library_created = models.LibraryArtifact.objects.get_or_create(
                dice_name=form.cleaned_data.get("library_name"))
    library.layout_config = form.cleaned_data.get("library_layout_config")
    library.layout_read_length = form.cleaned_data.get("library_layout_read_length")
    library.layout_insert_length = form.cleaned_data.get("library_layout_insert_length")
    library.seq_kit = form.cleaned_data.get("library_seq_kit")
    library.seq_protocol = form.cleaned_data.get("library_seq_protocol")

    if library_created:
        if api_o:
            api_o["new"].append(_format_tuple(library))

        # Create the pooling event
        pool_p = models.LibraryPoolingProcess(
            when = datetime.datetime.now(),
            who = user,
        )
        pool_p.save()
        library.pooling = pool_p
        library.save()
    return library, library_created

def handle_testlibraryrecord(form, user=None, api_o=None):

    biosample = form.cleaned_data.get("central_sample_id") # will return a biosample object
    library = form.cleaned_data.get("library_name") # will actually return a library object

    if not library.pooling:
        return None, False

    pool_rec, created = models.LibraryPoolingProcessRecord.objects.get_or_create(
        process=library.pooling,
        bridge_artifact=biosample,
        in_artifact=biosample,
        out_artifact=library
    )
    pool_rec.library_source = form.cleaned_data.get("library_source")
    pool_rec.library_selection = form.cleaned_data.get("library_selection")
    pool_rec.library_strategy = form.cleaned_data.get("library_strategy")
    pool_rec.save()
    if api_o and created:
        api_o["updated"].append(_format_tuple(biosample))
    return pool_rec, created



def handle_testsample(form, user=None, api_o=None):
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
        else:
            if api_o:
                api_o["ignored"].append(source.dice_name)
                api_o["messages"].append("Biosample Sources cannot be updated")
                api_o["warnings"] += 1
    else:
        source = None


    if type(form.cleaned_data.get("collection_date")) == str:
        collection_date = dateutil.parser.parse(form.cleaned_data.get("collection_date"))
    else:
        collection_date = form.cleaned_data.get("collection_date")

    # Get or create the Biosample
    sample_id = form.cleaned_data.get("central_sample_id")
    sample, sample_created = models.BiosampleArtifact.objects.get_or_create(
            central_sample_id=sample_id
    )

    if sample:
        sample.root_sample_id = form.cleaned_data.get("root_sample_id")
        sample.sender_sample_id = form.cleaned_data.get("sender_sample_id")
        sample.central_sample_id = sample_id
        sample.dice_name = sample_id

        sample.sample_type_collected = form.cleaned_data.get("sample_type_collected")
        sample.sample_type_current = form.cleaned_data.get("sample_type_received")
        sample.sample_site = form.cleaned_data.get("swab_site")

        sample.primary_group = source
        sample.secondary_identifier = form.cleaned_data.get("secondary_identifier")
        sample.secondary_accession = form.cleaned_data.get("secondary_accession")
        sample.taxonomy_identifier = form.cleaned_data.get("source_taxon")

        sample.save()

    if sample_created:
        if api_o:
            api_o["new"].append(_format_tuple(sample))
    else:
        if api_o:
            api_o["updated"].append(_format_tuple(sample))

    try:
        submitted_by = form.cleaned_data.get("submitting_org").name
    except:
        submitted_by = None

    if sample.collection:
        # Already have a collection obj
        sample_p = sample.collection.process
        sampling_rec = sample.collection
    else:
        # Create the sampling event
        sample_p = models.BiosourceSamplingProcess(
            who = user,
            when = collection_date,
            submitted_by = submitted_by,
            submission_user = user,
            submission_org = form.cleaned_data.get("submitting_org"),
        )
        sample_p.save()

        sampling_rec = models.BiosourceSamplingProcessRecord(
            process=sample_p,
            in_group=source,
            out_artifact=sample,
        )
        sampling_rec.save()
        sample.collection = sampling_rec # Set the sample collection process
        sample.save()
        signals.new_sample.send(sender=None, sample_id=sample.central_sample_id, submitter=sample.collection.process.submitted_by)

    sample_p.collection_date = collection_date
    sample_p.collected_by = form.cleaned_data.get("collecting_org")
    sample_p.collection_location_country = form.cleaned_data.get("country")
    sample_p.collection_location_adm1 = form.cleaned_data.get("adm1")
    sample_p.collection_location_adm2 = form.cleaned_data.get("adm2").upper() # capitalise the county for now?
    sample_p.private_collection_location_adm2 = form.cleaned_data.get("adm2_private")
    sample_p.source_age = form.cleaned_data.get("source_age")
    sample_p.source_sex = form.cleaned_data.get("source_sex")
    sample_p.save()

    return sample, sample_created

def handle_testdigitalresource(form, user=None, api_o=None):

    node = form.cleaned_data["node_name"]

    # Get the directory
    parent = node
    path = form.cleaned_data["path"]
    lpath = path.split( form.cleaned_data["sep"] )[1:-1]
    for i, dir_name in enumerate(lpath):
        dir_g, created = models.DigitalResourceGroup.objects.get_or_create(
                current_name=dir_name,
                root_group=node,
                parent_group=parent,
                physical=True)
        parent = dir_g

    res, created = models.DigitalResourceArtifact.objects.get_or_create(
            primary_group = parent,
            current_name = form.cleaned_data["current_name"],
            current_extension = form.cleaned_data["current_fext"],
    )
    res.current_hash = form.cleaned_data["current_hash"]
    res.current_size = form.cleaned_data["current_size"]
    res.current_kind = form.cleaned_data["resource_type"]
    res.save()

    if created and api_o:
        api_o["new"].append(_format_tuple(res))
    elif res:
        api_o["updated"].append(_format_tuple(res))
    return res, created
