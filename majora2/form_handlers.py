from . import models
from . import signals

import dateutil.parser

def handle_testsample(form, user=None):
    biosample_source_id = form.cleaned_data.get("biosample_source_id")
    if biosample_source_id:
        # Create the BiosampleSource
        try:
            source = models.BiosampleSource.objects.get(unique_name=biosample_source_id)
        except:
            source = models.BiosampleSource(
                unique_name = biosample_source_id,
                meta_name = biosample_source_id,
                dice_name = biosample_source_id,
                source_type = form.cleaned_data.get("source_type"),
                physical = True,
            )
            source.save()
    else:
        source = None

    if type(form.cleaned_data.get("collection_date")) == str:
        collection_date = dateutil.parser.parse(form.cleaned_data.get("collection_date"))
    else:
        collection_date = form.cleaned_data.get("collection_date")

    # Create the Biosample
    sample_id = form.cleaned_data.get("central_sample_id")
    sample, sample_created = models.BiosampleArtifact.objects.get_or_create(
            central_sample_id=sample_id,
            root_sample_id=form.cleaned_data.get("root_sample_id"))

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

    if sample_created:
        try:
            submitted_by = form.cleaned_data.get("submitting_org").name
        except:
            submitted_by = None

        # Create the sampling event
        sample_pgroup = models.MajoraArtifactProcessGroup()
        sample_pgroup.save()
        sample_p = models.BiosourceSamplingProcess(
            who = user,
            when = collection_date,
            group = sample_pgroup,
            collection_date = collection_date,
            submitted_by = submitted_by,
            collected_by = form.cleaned_data.get("collecting_org"),
            submission_user = user,
            submission_org = form.cleaned_data.get("submitting_org"),
            collection_location_country = form.cleaned_data.get("country"),
            collection_location_adm1 = form.cleaned_data.get("adm1"),
            collection_location_adm2 = form.cleaned_data.get("adm2").upper(), # capitalise the county for now?
            private_collection_location_adm2 = form.cleaned_data.get("adm2_private"),
            source_age = form.cleaned_data.get("source_age"),
            source_sex = form.cleaned_data.get("source_sex"),
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

    return sample, sample_created
