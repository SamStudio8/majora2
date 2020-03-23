import datetime
import dateutil.parser

from . import models
from . import signals

def _format_tuple(x):
    if hasattr(x, "process_kind"):
        return (x.kind, str(x.id), "")
    else:
        return (x.kind, str(x.id), x.dice_name)

def handle_testsequencing(form, user=None, api_o=None):
    p, sequencing_created = models.DNASequencingProcess.objects.get_or_create(id=form.cleaned_data["sequencing_id"])
    if sequencing_created:
        if api_o:
            api_o["new"].append(_format_tuple(p))
        p.when = datetime.datetime.now()
        p.save()

        rec = models.DNASequencingProcessRecord(
            process=p,
            in_artifact=form.cleaned_data.get("library_name")
        )
        rec.save()
    return p, sequencing_created


def handle_testlibrary(form, user=None, api_o=None):
    library, library_created = models.LibraryArtifact.objects.get_or_create(
                dice_name=form.cleaned_data.get("library_name"))
    sample_l = form.cleaned_data.get("samples")

    if library_created:
        if api_o:
            api_o["new"].append(_format_tuple(library))

        # Create the pooling event
        pool_p = models.LibraryPoolingProcess(
            when = datetime.datetime.now(),
            who = user,
        )
        pool_p.save()

        for sample in sample_l:
            pool_rec = models.LibraryPoolingProcessRecord(
                process=pool_p,
                in_artifact=sample,
                out_artifact=library
            )
            pool_rec.save()
    return library, library_created


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
            central_sample_id=sample_id,
            root_sample_id=form.cleaned_data.get("root_sample_id"))

    if sample_created:
        if api_o:
            api_o["new"].append(_format_tuple(sample))
    else:
        if api_o:
            api_o["updated"].append(_format_tuple(sample))

    if sample:
        sample.root_sample_id = form.cleaned_data.get("root_sample_id")
        sample.sender_sample_id = form.cleaned_data.get("sender_sample_id")
        sample.central_sample_id = sample_id
        sample.dice_name = sample_id

        sample.sample_type = form.cleaned_data.get("sample_type")
        sample.sample_site = form.cleaned_data.get("swab_site")

        sample.primary_group = source
        sample.secondary_identifier = form.cleaned_data.get("secondary_identifier")
        sample.secondary_accession = form.cleaned_data.get("secondary_accession")
        sample.taxonomy_identifier = form.cleaned_data.get("source_taxon")

        sample.save()

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
