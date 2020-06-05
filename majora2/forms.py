import datetime

from django import forms

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column
from crispy_forms.bootstrap import FormActions

from .account_views import generate_username
from . import models
from . import fixed_data

import re

from sshpubkeys import SSHKey
def majora_clean_ssh_key(ssh_key):
    if ssh_key:
        ssh_key = "".join(ssh_key.splitlines()).strip()
        key = SSHKey(ssh_key)
        try:
            key.parse()
        except Exception as e:
            raise forms.ValidationError("Unable to decode your key. Please ensure this is your public key and has been entered correctly.")

        if key.key_type != b'ssh-ed25519':
            raise forms.ValidationError("This system accepts ed25519 keys only.")

    return ssh_key


class InstituteForm(forms.Form):
    name = forms.CharField(max_length=100, disabled=True, required=False)
    code = forms.CharField(max_length=10, disabled=True, required=False)

    gisaid_opted = forms.BooleanField(required=False, label="GISAID Opt-in", help_text="Check this box to opt-in to COG-UK automated submissions to GISAID")
    gisaid_user = forms.CharField(max_length=100, required=False, label="GISAID username", help_text="Submissions will be send on behalf of this user")
    gisaid_mail = forms.EmailField(required=False, label="E-mail address", help_text="E-mail address to share with GISAID curators")
    gisaid_lab_name = forms.CharField(max_length=512, required=False, label="Originating lab name(s)", help_text="The name or names of originating labs you would like to credit")
    gisaid_lab_addr = forms.CharField(max_length=512, required=False, label="Originating lab address(es)", help_text="Use the broadest address that encompasses all the originating labs")
    gisaid_list = forms.CharField(max_length=2048, required=False, widget=forms.Textarea(attrs={"rows": 5}), label="Author list")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Institute",
                Row(
                    Column('code', css_class="form-group col-md-2 mb-0"),
                    Column('name', css_class="form-group col-md-10 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('gisaid_opted', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("GISAID: User",
                Row(
                    Column('gisaid_user', css_class="form-group col-md-6 mb-0"),
                    Column('gisaid_mail', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("GISAID: Originating Lab",
                Row(
                    Column('gisaid_lab_name', css_class="form-group col-md-6 mb-0"),
                    Column('gisaid_lab_addr', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("GISAID: Authors",
                'gisaid_list'
            ),
            FormActions(
                    Submit('save', 'Save'),
                    css_class="text-right",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("gisaid_opted", False):
            for field in ["gisaid_user", "gisaid_mail", "gisaid_lab_name", "gisaid_lab_addr", "gisaid_list"]:
                if not cleaned_data.get(field):
                    self.add_error(field, "Required if opting-in to GISAID submissions")
        if cleaned_data.get("gisaid_user"):
            if not cleaned_data.get("gisaid_opted"):
                self.add_error("gisaid_opted", "Check this box to opt-in to GISAID submissions")

class AccountForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True, required=False, help_text="You cannot change your username")
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    organisation = forms.ModelChoiceField(queryset=models.Institute.objects.exclude(code__startswith="?").order_by("code"), disabled=True, required=False, help_text="You cannot change your organisation", to_field_name="code")
    ssh_key = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="SSH Public Key.</br>This system accepts ed25519 keys only. To generate one, run this command: <code>ssh-keygen -o -a 100 -t ed25519</code>", help_text="If you do not need access to CLIMB servers over SSH to upload sequence data or access resources, you can leave this blank. You can add an SSH key later but will need to notify us.", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User",
                Row(
                    Column('username', css_class="form-group col-md-6 mb-0"),
                    Column('email', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
            ),
            Fieldset("Name",
                Row(
                    Column('first_name', css_class="form-group col-md-6 mb-0"),
                    Column('last_name', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Organisation",
                Row(
                    Column('organisation', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("SSH Key",
                'ssh_key'
            ),
            FormActions(
                    Submit('save', 'Update'),
                    css_class="text-right",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

    def clean_ssh_key(self):
        return majora_clean_ssh_key(self.cleaned_data.get("ssh_key"))

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True, required=False)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Password", min_length=8)
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirm password", min_length=8)

    organisation = forms.ModelChoiceField(queryset=models.Institute.objects.exclude(code__startswith="?").order_by("code"))
    ssh_key = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="SSH Public Key.</br>This system accepts ed25519 keys only. To generate one, run this command: <code>ssh-keygen -o -a 100 -t ed25519</code>", help_text="If you do not need access to CLIMB servers over SSH to upload sequence data or access resources, you can leave this blank. You can add an SSH key later but will need to notify us.", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User",
                Row(
                    Column('username', css_class="form-group col-md-6 mb-0"),
                    Column('email', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('password1', css_class="form-group col-md-6 mb-0"),
                    Column('password2', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Name",
                Row(
                    Column('first_name', css_class="form-group col-md-6 mb-0"),
                    Column('last_name', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Organisation",
                Row(
                    Column('organisation', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("SSH Key",
                'ssh_key'
            ),
            FormActions(
                    Submit('save', 'Register'),
                    css_class="text-right",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password1", "Passwords do not match.")
            self.add_error("password2", "Passwords do not match.")

        if User.objects.filter(username=generate_username(cleaned_data)).count() > 0:
            #raise forms.ValidationError('This username has already been registered. You may be in the approval queue.')
            self.add_error("username", 'This username has already been registered. You may be in the approval queue.')

    def clean_ssh_key(self):
        return majora_clean_ssh_key(self.cleaned_data.get("ssh_key"))


class M2Metric_SequenceForm(forms.ModelForm):
    class Meta:
        model = models.TemporaryMajoraArtifactMetric_Sequence
        exclude = []

class M2Metric_MappingForm(forms.ModelForm):
    class Meta:
        model = models.TemporaryMajoraArtifactMetric_Mapping
        exclude = []

class M2Metric_MappingTileForm(forms.ModelForm):
    class Meta:
        model = models.TemporaryMajoraArtifactMetric_Mapping_Tiles
        exclude = []

class M2Metric_ThresholdCycleForm(forms.ModelForm):
    class Meta:
        model = models.TemporaryMajoraArtifactMetric_ThresholdCycle
        exclude = []

class M2MetricRecord_ThresholdCycleForm(forms.Form): # should probably be a modelform, but w/e
    artifact_metric = forms.ModelChoiceField(queryset=models.TemporaryMajoraArtifactMetric_ThresholdCycle.objects.all(), required=True)
    ct_value = forms.FloatField(required=True, min_value=0.0)
    test_kit = forms.ChoiceField(
            choices=[
                (None, ""),
                ("ALTONA", "ALTONA"),
                ("ABBOTT", "ABBOTT"),
                ("ROCHE", "ROCHE"),
                ("AUSDIAGNOSTICS", "AUSDIAGNOSTICS"),
                ("BOSPHORE", "BOSPHORE"),
                ("INHOUSE", "INHOUSE"),
                ("SEEGENE", "SEEGENE"),
            ],
            required=False,
    )
    test_platform = forms.ChoiceField(
            choices=[
                (None, ""),
                ("ALTOSTAR_AM16", "ALTOSTAR_AM16"),
                ("ABBOTT_M2000", "ABBOTT_M2000"),
                ("ROCHE_FLOW", "ROCHE_FLOW"),
                ("ROCHE_COBAS", "ROCHE_COBAS"),
                ("ELITE_INGENIUS", "ELITE_INGENIUS"),
                ("CEPHEID_XPERT", "CEPHEID_XPERT"),
                ("QIASTAT_DX", "QIASTAT_DX"),
                ("AUSDIAGNOSTICS", "AUSDIAGNOSTICS"),
                ("ROCHE_LIGHTCYCLER", "ROCHE_LIGHTCYCLER"),
                ("INHOUSE", "INHOUSE"),
                ("ALTONA", "ALTONA"),
                ("PANTHER", "PANTHER"),
                ("SEEGENE_NIMBUS", "SEEGENE_NIMBUS"),
                ("QIAGEN_ROTORGENE", "QIAGEN_ROTORGENE"),
            ],
            required=False,
    )
    test_target = forms.ChoiceField(
            choices=[
                (None, ""),
                ("S", "S"),
                ("E", "E"),
                ("N", "N"),
                ("RDRP","RDRP"),
                ("ORF1AB", "ORF1AB"),
                ("ORF8", "ORF8"),
                ("RDRP+N", "RDRP+N"),
            ],
            required=False,
    )

class TestMetadataForm(forms.Form):
    artifact = forms.ModelChoiceField(queryset=models.MajoraArtifact.objects.all(), required=False, to_field_name="dice_name")
    group = forms.ModelChoiceField(queryset=models.MajoraArtifactGroup.objects.all(), required=False, to_field_name="dice_name")
    process = forms.ModelChoiceField(queryset=models.MajoraArtifactProcess.objects.all(), required=False)
    #pgroup

    tag = forms.CharField(max_length=64)
    name = forms.CharField(max_length=64)
    value = forms.CharField(max_length=128)

    timestamp = forms.DateTimeField()

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get("artifact") or cleaned_data.get("group") or cleaned_data.get("process")):
            msg = "You must provide one 'artifact', 'group' or 'process' to attach metadata to"
            self.add_error("artifact", msg)
            self.add_error("group", msg)
            self.add_error("process", msg)



class TestLibraryForm(forms.Form):
    library_name = forms.CharField(max_length=48, min_length=5)
    library_layout_config = forms.ChoiceField(
            choices=[
                (None, ""),
                ("SINGLE", "SINGLE"),
                ("PAIRED", "PAIRED"),
            ],
    )
    library_layout_read_length = forms.IntegerField(min_value=0, required=False)
    library_layout_insert_length = forms.IntegerField(min_value=0, required=False)

    library_seq_kit = forms.CharField(max_length=48)
    library_seq_protocol = forms.CharField(max_length=48)


class TestLibraryBiosampleForm(forms.Form):
    central_sample_id = forms.ModelChoiceField(queryset=models.BiosampleArtifact.objects.all(), required=True, to_field_name="dice_name")
    library_name = forms.ModelChoiceField(queryset=models.LibraryArtifact.objects.all(), required=True, to_field_name="dice_name")
    barcode = forms.CharField(max_length=24, required=False)
    library_strategy = forms.ChoiceField(
            choices=[
                (None, ""),
                ("WGS", "WGS: Whole Genome Sequencing"),
                ("WGA", "WGA: Whole Genome Amplification"),
                ("AMPLICON", "AMPLICON: Sequencing of overlapping or distinct PCR or RT-PCR products"),
                ("TARGETED_CAPTURE", "TARGETED_CAPTURE: Enrichment of a targeted subset of loci"),
                ("OTHER", "?: Library strategy not listed"),
            ],
    )
    library_source = forms.ChoiceField(
            choices=[
                (None, ""),
                ("GENOMIC", "GENOMIC"),
                ("TRANSCRIPTOMIC", "TRANSCRIPTOMIC"),
                ("METAGENOMIC", "METAGENOMIC"),
                ("METATRANSCRIPTOMIC", "METATRANSCRIPTOMIC"),
                ("VIRAL_RNA", "VIRAL RNA"),
                ("OTHER", "?: Other, unspecified, or unknown library source material"),
            ],
    )
    library_selection = forms.ChoiceField(
            choices=[
                (None, ""),
                ("RANDOM", "RANDOM: No Selection or Random selection"),
                ("PCR", "PCR: Enrichment via PCR"),
                ("RANDOM_PCR", "RANDOM-PCR: Source material was selected by randomly generated primers"),
                ("OTHER", "?: Other library enrichment, screening, or selection process"),
            ],
    )
    library_primers = forms.CharField(max_length=48, required=False)
    library_protocol = forms.CharField(max_length=48, required=False)


class TestSequencingForm(forms.Form):
    library_name = forms.ModelChoiceField(queryset=models.LibraryArtifact.objects.all(), required=True, to_field_name="dice_name")

    sequencing_id = forms.UUIDField(required=False)
    run_name = forms.CharField(max_length=128, required=False, min_length=5)
    run_group = forms.CharField(max_length=128, required=False)

    instrument_make = forms.ChoiceField(
            label="Instrument Make",
            choices=[
                (None, ""),
                ("ILLUMINA", "Illumina"),
                ("OXFORD_NANOPORE", "Oxford Nanopore"),
                ("PACIFIC_BIOSCIENCES", "Pacific Biosciences"),
            ],
    )
    instrument_model = forms.CharField(
            label="Instrument Model",
    )
    flowcell_type = forms.CharField(max_length=48, required=False)
    #flowcell_version = forms.CharField(max_length=48)
    flowcell_id = forms.CharField(max_length=48, required=False)

    start_time = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"], required=False)
    end_time = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"], required=False)

    @staticmethod
    def modify_preform(data):
        UPPERCASE_FIELDS = [
            "instrument_make",
        ]
        for field in UPPERCASE_FIELDS:
            if data.get(field):
                data[field] = data[field].upper().strip().replace(' ', '_')
        return data

    def clean(self):
        run_name = self.cleaned_data.get("run_name")
        if not self.cleaned_data.get("sequencing_id"):
            if not run_name:
                self.add_error("run_name", "If you don't provide a sequencing_id, you must provide a run_name")
        reserved_ch = [".", "/", "\\"]
        for ch in reserved_ch:
            if ch in run_name:
                self.add_error("run_name", "run_name cannot contain a reserved character: %s" % str(reserved_ch))
                break


class TestSampleForm(forms.Form):

    biosample_source_id = forms.CharField(
            label="Pseudonymous patient identifier", max_length=56,
            help_text="Leave blank if not available. <b>DO NOT enter an NHS number here</b>", required=False)
    root_sample_id = forms.CharField(
            label="Health Agency sample identifier", max_length=56, required=False,
            help_text="Leave blank if not applicable or available. It will not be possible to collect private metadata for this sample without this"
    )
    sender_sample_id = forms.CharField(
            label="Local sample identifier", max_length=56, required=False,
            help_text="Leave blank if not applicable or available. It will not be possible to collect private metadata for this sample without this"
    )
    central_sample_id = forms.CharField(
            label="New sample identifier", max_length=56, min_length=5,
            help_text="Heron barcode assigned by WSI"
    )
    collection_date = forms.DateField(
            label="Collection date",
            help_text="YYYY-MM-DD",
            required=False,
    )
    received_date = forms.DateField(
            label="Received date",
            help_text="YYYY-MM-DD",
            required=False,
    )
    country = forms.CharField(disabled=True)
    adm1 = forms.ChoiceField(
            label="Region",
            choices=[
                (None, ""),
                ("UK-ENG", "England"),
                ("UK-SCT", "Scotland"),
                ("UK-WLS", "Wales"),
                ("UK-NIR", "Northern Ireland"),
            ],
    )
    source_age = forms.IntegerField(min_value=0, required=False, help_text="Age in years")
    source_sex = forms.ChoiceField(choices=[
            (None, ""),
            ("F", "F"),
            ("M", "M"),
            ("Other", "Other"),
        ], required=False, help_text="Reported sex")

    adm2 = forms.CharField(
            label="County",
            max_length=100,
            required=False,
            help_text="Enter the COUNTY from the patient's address. Leave blank if this was not available."
    )
    #adm2 = forms.ModelChoiceField(
    #        queryset=models.County.objects.all(),
    #        to_field_name="name",
    #        label="County",
    #        required=False,
    #        help_text="Enter the COUNTY from the patient's address. Leave blank if this was not available."
    #)
    adm2_private = forms.CharField(
            label="Outward postcode",
            max_length=10,
            required=False,
            disabled=True,
            help_text="Enter the <b>first part</b> of the patients home postcode. Leave blank if this was not available."
    )
    submitting_user = forms.CharField(disabled=True, required=False)
    submitting_org = forms.ModelChoiceField(queryset=models.Institute.objects.exclude(code__startswith="?").order_by("name"), disabled=True, required=False)
    collecting_org = forms.CharField(max_length=100, required=False, help_text="The site that this sample was collected by. Use the first line of the 'sender' from the corresponding E28")

    source_type = forms.ChoiceField(
        choices = [
            ("human", "human"),
        ],
        disabled = True,
    )
    source_taxon = forms.CharField(
            max_length=24,
            disabled=True,
    )
    sample_type_collected = forms.ChoiceField(
        choices= [
            (None, "Unknown"),
            ("dry swab", "dry swab"),
            ("swab", "swab"),
            ("aspirate", "aspirate"),
            ("sputum", "sputum"),
            ("BAL", "BAL"),
        ],
        required=False,
    )
    sample_type_received = forms.ChoiceField(
        choices= [
            (None, "Unknown"),
            ("primary", "primary"),
            ("extract", "extract"),
            ("lysate", "lysate"),
            ("culture", "culture"),
        ],
        required=False,
    )
    swab_site = forms.ChoiceField(
        choices= [
            (None, None),
            ("nose", "nose"),
            ("throat", "throat"),
            ("nose-throat", "nose and throat"),
            ("endotracheal", "endotracheal"),
            ("rectal", "rectal"),
        ],
        help_text="Provide only if sample_type_collected is swab",
        required=False,
    )

    #override_heron = forms.BooleanField(
    #        label="Override Heron validator",
    #        help_text="Enable this checkbox if your sample has not been assigned a Heron identifier. <i>e.g.</i> The sample has already been submitted to GISAID",
    #        required=False)
    #secondary_identifier = forms.CharField(
    #        max_length=256,
    #        label="GISAID identifier string",
    #        help_text="New COG-UK samples will have GISAID strings automatically composed. If this sample has already been submitted to GISAID, provide the identifier here.",
    #        required=False)
    #secondary_accession = forms.CharField(
    #        max_length=256,
    #        label="GISAID accession",
    #        help_text="If this sample has already been submitted to GISAID, provide the accession here.",
    #        required=False)


    #tube_dice = forms.CharField()
    #box_dice = forms.CharField()
    #tube_x = forms.IntegerField()
    #tube_y = forms.IntegerField()
    #current_sample_type = forms.ChoiceField()
    #accepted = forms.BooleanField()
    #quarantine_reason = forms.ChoiceField()
    #received_date =

    #TODO Extra COGUK supplemental fields
    # In an ideal world where we have more time, we'd pin a bunch of supplemental modelforms but we need this asappppp
    is_surveillance = forms.NullBooleanField()
    is_hcw = forms.NullBooleanField()
    employing_hospital_name = forms.CharField(max_length=100, required=False)
    employing_hospital_trust_or_board = forms.CharField(max_length=100, required=False)
    is_hospital_patient = forms.NullBooleanField()
    is_icu_patient = forms.NullBooleanField()
    admission_date = forms.DateField(
            label="Received date",
            help_text="YYYY-MM-DD",
            required=False,
    )
    admitted_hospital_name = forms.CharField(max_length=100, required=False)
    admitted_hospital_trust_or_board = forms.CharField(max_length=100, required=False)
    is_care_home_worker = forms.NullBooleanField()
    is_care_home_resident = forms.NullBooleanField()
    anonymised_care_home_code = forms.CharField(max_length=10, required=False)
    admitted_with_covid_diagnosis = forms.NullBooleanField()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Identifiers",
                Row(
                    Column('biosample_source_id', css_class="form-group col-md-3 mb-0"),
                    Column('root_sample_id', css_class="form-group col-md-3 mb-0"),
                    Column('sender_sample_id', css_class="form-group col-md-3 mb-0"),
                    Column('central_sample_id', css_class="form-group col-md-3 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Form",
                Row(
                    Column('source_type', css_class="form-group col-md-3 mb-0"),
                    Column('source_taxon', css_class="form-group col-md-3 mb-0"),
                    Column('sample_type_collected', css_class="form-group col-md-2 mb-0"),
                    Column('swab_site', css_class="form-group col-md-2 mb-0"),
                    Column('sample_type_received', css_class="form-group col-md-2 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Locality",
                Row(
                    Column('country', css_class="form-group col-md-3 mb-0"),
                    Column('adm1', css_class="form-group col-md-2 mb-0"),
                    Column('adm2', css_class="form-group col-md-4 mb-0"),
                    Column('adm2_private', css_class="form-group col-md-3 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Key information",
                Row(
                    Column('collection_date', css_class="form-group col-md-3 mb-0"),
                    Column('received_date', css_class="form-group col-md-3 mb-0"),
                    Column('age', css_class="form-group col-md-2 mb-0"),
                    Column('sex', css_class="form-group col-md-2 mb-0"),
                    css_class="form-row",
                ),
            ),
            Fieldset("Collecting and sequencing",
                Row(
                    Column('collecting_org', css_class="form-group col-md-5 mb-0"),
                    Column('submitting_user', css_class="form-group col-md-3 mb-0"),
                    Column('submitting_org', css_class="form-group col-md-4 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Advanced Options",
                Row(
                    Column('secondary_identifier', css_class="form-group col-md-6 mb-0"),
                    Column('secondary_accession', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
                #Row(
                #    Column('override_heron', css_class="form-group col-md-6 mb-0"),
                #    css_class="form-row",
                #)
            ),
            FormActions(
                    Submit('save', 'Submit sample'),
                    css_class="text-right",
            )
        )

    @staticmethod
    def modify_preform(data):
        LOWERCASE_FIELDS = [
            "swab_site",
            "sample_type_collected",
            "sample_type_received",
        ]
        UPPERCASE_FIELDS = [
        ]
        COERCE_BOOLEAN = [
            "is_surveillance",
            "is_hcw",
            "is_hospital_patient",
            "is_care_home_worker",
            "is_care_home_resident",
            "admitted_with_covid_diagnosis",
            "is_icu_patient",
        ]
        for field in LOWERCASE_FIELDS:
            if data.get(field):
                data[field] = data[field].strip()
                if data[field] != "BAL":
                    data[field] = data[field].strip().lower()
        for field in UPPERCASE_FIELDS:
            if data.get(field):
                data[field] = data[field].strip().upper()
        for field in COERCE_BOOLEAN:
            if data.get(field):
                b = data[field].strip().upper()
                if b == "Y" or b == "YES":
                    data[field] = True
                elif b == "N" or b == "NO":
                    data[field] = False
                else:
                    data[field] = None

        #if data.get("swab_site", "").upper() == "NSTS" or data.get("swab_site", "").lower() == "nose and throat":
        #    data["swab_site"] = "nose-throat"
        return data

    def clean(self):
        cleaned_data = super().clean()

        # Check barcode starts with a Heron prefix, unless this has been overridden
        #sample_id = cleaned_data.get("central_sample_id")
        #if sample_id:
        #    if cleaned_data["override_heron"] is False:
        #        valid_sites = [x.code for x in models.Institute.objects.exclude(code__startswith="?")]
        #        if sum([sample_id.startswith(x) for x in valid_sites]) == 0:
        #            self.add_error("central_sample_id", "Sample identifier does not match the WSI manifest.")

        # Check a received_date was provided for samples without a collection date
        if not cleaned_data.get("collection_date") and not cleaned_data.get("received_date"):
            self.add_error("received_date", "You must provide a received date for samples without a collection date")

        # Check sample date is not in the future
        if cleaned_data.get("collection_date"):
            if cleaned_data["collection_date"] > timezone.now().date():
                self.add_error("collection_date", "Sample cannot be collected in the future")
            if cleaned_data["collection_date"] < (timezone.now().date() - datetime.timedelta(days=365)):
                self.add_error("collection_date", "Sample cannot be collected more than a year ago...")
        if cleaned_data.get("received_date"):
            if cleaned_data["received_date"] > timezone.now().date():
                self.add_error("received_date", "Sample cannot be received in the future")
            if cleaned_data["received_date"] < (timezone.now().date() - datetime.timedelta(days=365)):
                self.add_error("received_date", "Sample cannot be received more than a year ago...")

        # Check if the adm2 looks like a postcode
        adm2 = cleaned_data.get("adm2", "")
        if len(adm2) > 0 and re.search('\d', adm2):
            self.add_error("adm2", "adm2 cannot contain numbers. Use adm2_private if you are trying to provide an outer postcode")

        # Check for full postcode mistake
        adm2_private = cleaned_data.get("adm2_private")
        if " " in adm2_private:
            self.add_error("adm2_private", "Enter the first part of the postcode only")

        # Validate swab site
        swab_site = cleaned_data.get("swab_site")
        sample_type = cleaned_data.get("sample_type_collected")
        if sample_type and ("swab" not in sample_type and sample_type != "aspirate") and swab_site:
            self.add_error("sample_type_collected", "Swab site specified but the sample type is not 'swab'")
        #if sample_type == "swab" and not swab_site:
        #    self.add_error("sample_type_collected", "Sample was a swab but you did not specify the swab site")

        # Force is_surveillance
        if cleaned_data.get("is_surveillance") is None:
            self.add_error("is_surveillance", "You must set is_surveillance to Y or N")
        if cleaned_data.get("admission_date") and not cleaned_data.get("is_hospital_patient"):
            self.add_error("is_hospital_patient", "Admission date implies patient was admitted to hospital but you've not set is_hospital_patient to Y")


class TestFileForm(forms.Form):

    bridge_artifact = forms.ModelChoiceField(queryset=models.MajoraArtifact.objects.all(), required=False, to_field_name="dice_name")
    source_artifact = forms.ModelMultipleChoiceField(queryset=models.MajoraArtifact.objects.all(), required=False, to_field_name="dice_name")
    source_group = forms.ModelMultipleChoiceField(queryset=models.MajoraArtifactGroup.objects.all(), required=False, to_field_name="dice_name")
    publish_group = forms.CharField(max_length=128, required=False)

    #pipe_id = forms.UUIDField()
    pipe_hook = forms.CharField(max_length=256)
    artifact_uuid = forms.UUIDField(required=False)
    pipe_kind = forms.CharField(max_length=64)
    pipe_name = forms.CharField(max_length=96)
    pipe_version = forms.CharField(max_length=48)

    #node_uuid = forms.ModelChoiceField(queryset=models.DigitalResourceNode.objects.all())
    node_name = forms.ModelChoiceField(queryset=models.DigitalResourceNode.objects.all(), to_field_name="unique_name", required=False)
    path = forms.CharField(max_length=1024)
    sep = forms.CharField(max_length=2)
    current_name = forms.CharField(max_length=512)
    current_fext = forms.CharField(max_length=48)

    current_hash = forms.CharField(max_length=64)
    current_size = forms.IntegerField(min_value=0)

    resource_type = forms.ChoiceField(
        choices= [
            ("file", "file"),
            ("reads", "reads"),
            ("alignment", "alignment"),
            ("consensus", "consensus"),
        ],
    )

