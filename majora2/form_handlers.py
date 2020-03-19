from . import models
from . import signals

def handle_testsample(form, user=None):
    host_id = form.cleaned_data.get("host_id")
    if host_id:
        # Create the BiosampleSource
        try:
            source = models.BiosampleSource.objects.get(unique_name=host_id)
        except:
            source = models.BiosampleSource(
                unique_name = host_id,
                meta_name = host_id,
                dice_name = host_id,
                source_type = form.cleaned_data.get("source_type"),
                physical = True,
            )
            source.save()
    else:
        source = None

    collection_date = form.cleaned_data.get("collection_date")

    # Create the Biosample
    sample_id = form.cleaned_data.get("sample_id")
    try:
        sample = models.BiosampleArtifact.objects.get(
                unique_name=sample_id,
                sample_orig_id=form.cleaned_data.get("orig_sample_id"))
    except:
        sample = models.BiosampleArtifact(
            unique_name = sample_id,
            meta_name = sample_id,
            dice_name = sample_id,
            sample_orig_id = form.cleaned_data.get("orig_sample_id"),

            sample_type = form.cleaned_data.get("sample_type"),
            sample_site = form.cleaned_data.get("sample_site"),

            primary_group = source,
            secondary_identifier = form.cleaned_data.get("override_gisaid"),
            taxonomy_identifier = form.cleaned_data.get("source_taxon"),
        )
        sample.save()

        try:
            submitted_by = form.cleaned_data.get("submitting_organisation").name
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
            collected_by = form.cleaned_data.get("collecting_organisation"),
            submission_user = user,
            submission_org = form.cleaned_data.get("submitting_organisation"),
            collection_location_country = form.cleaned_data.get("country"),
            collection_location_adm1 = form.cleaned_data.get("adm1"),
            collection_location_adm2 = form.cleaned_data.get("adm2"),
            private_collection_location_adm2 = form.cleaned_data.get("adm2_private"),
            source_age = form.cleaned_data.get("age"),
            source_sex = form.cleaned_data.get("sex"),
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
    signals.new_sample.send(sender=None, sample_id=sample.unique_name, submitter=sample.collection.process.submitted_by)
    return True
