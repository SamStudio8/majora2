import datetime

from django import forms

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property

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

class CreditForm(forms.Form):
    #TODO samstudio8: There is a condition where the max_length can be overrun as we append the site name, reduce this field maxlen by 4+1 to account for the general case of a 4 letter side code and :
    credit_code = forms.CharField(max_length=19, required=True, help_text="A short string to refer to this credit list when uploading metadata. This need not match an existing site name, or barcode. Note that this will automatically be prefixed by your site identifier.")

    lab_name = forms.CharField(max_length=512, required=True, label="Originating lab name(s)", help_text="The name or names of originating labs you would like to credit")
    lab_addr = forms.CharField(max_length=512, required=True, label="Originating lab address(es)", help_text="Use the broadest address that encompasses all the originating labs")
    lab_list = forms.CharField(max_length=2048, required=False, widget=forms.Textarea(attrs={"rows": 5}), label="Author list")

    delete = forms.BooleanField(required=False, label="Delete", help_text="Tick this to remove this Credit from your Institute")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Credit",
                Row(
                    Column('credit_code', css_class="form-group col-md-4 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('lab_name', css_class="form-group col-md-6 mb-0"),
                    Column('lab_addr', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('lab_list', css_class="form-group col-md-12 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('delete', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
            ),
            FormActions(
                    Submit('save', 'Save'),
                    css_class="text-right",
            )
        )

class InstituteForm(forms.Form):
    name = forms.CharField(max_length=100, disabled=True, required=False)
    code = forms.CharField(max_length=10, disabled=True, required=False)

    gisaid_opted = forms.BooleanField(required=False, label="GISAID Opt-in", help_text="Check this box to opt-in to COG-UK automated submissions to GISAID")
    gisaid_user = forms.CharField(max_length=100, required=False, label="GISAID username", help_text="Submissions will be sent on behalf of this user")
    gisaid_mail = forms.EmailField(required=False, label="E-mail address", help_text="E-mail address to share with GISAID curators")
    gisaid_lab_name = forms.CharField(max_length=512, required=False, label="Originating lab name(s)", help_text="The name or names of originating labs you would like to credit")
    gisaid_lab_addr = forms.CharField(max_length=512, required=False, label="Originating lab address(es)", help_text="Use the broadest address that encompasses all the originating labs")
    gisaid_list = forms.CharField(max_length=2048, required=False, widget=forms.Textarea(attrs={"rows": 5}), label="Author list")

    ena_assembly_opted = forms.BooleanField(required=False, label="ENA assembly Opt-in", help_text="Check this box to opt-in to COG-UK automated submissions of consensus sequences to ENA and INSDC")

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
            ),
            Fieldset("Outbound Opt-ins",
                Row(
                    Column('gisaid_opted', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
                Row(
                    Column('ena_assembly_opted', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                ),
            ),
            Fieldset("GISAID: User",
                Row(
                    Column('gisaid_user', css_class="form-group col-md-6 mb-0"),
                    Column('gisaid_mail', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("GISAID and ENA: Originating Lab",
                Row(
                    Column('gisaid_lab_name', css_class="form-group col-md-6 mb-0"),
                    Column('gisaid_lab_addr', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("GISAID and ENA: Authors",
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

        if cleaned_data.get("ena_assembly_opted", False):
            for field in ["gisaid_lab_name", "gisaid_lab_addr", "gisaid_list"]:
                if not cleaned_data.get(field):
                    self.add_error(field, "Required if opting-in to ENA consensus submissions")

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
                ("VIASURE", "VIASURE"),
                ("BD", "BD"),
                ("XPERT", "XPERT"),
                ("QIASTAT", "QIASTAT"),
                ("ALINITY", "ALINITY"),
                ("AMPLIDIAG", "AMPLIDIAG"),
                ("TAQPATH_HT", "TAQPATH_HT"),
                ("INVITROGEN", "INVITROGEN"),
            ],
            required=False,
    )
    test_platform = forms.ChoiceField(
            choices=[
                (None, ""),
                ("ALTOSTAR_AM16", "ALTOSTAR_AM16"),
                ("ABBOTT_M2000", "ABBOTT_M2000"),
                ("ABBOTT_ALINITY", "ABBOTT_ALINITY"),
                ("APPLIED_BIO_7500", "APPLIED_BIO_7500"),
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
                ("BD_MAX", "BD_MAX"),
                ("AMPLIDIAG_EASY", "AMPLIDIAG_EASY"),
                ("THERMO_AMPLITUDE", "THERMO_AMPLITUDE"),
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
    value = forms.CharField(max_length=128, required=False)

    timestamp = forms.DateTimeField()

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get("artifact") or cleaned_data.get("group") or cleaned_data.get("process")):
            msg = "You must provide one 'artifact', 'group' or 'process' to attach metadata to"
            self.add_error("artifact", msg)
            self.add_error("group", msg)
            self.add_error("process", msg)



class TestLibraryForm(forms.Form):
    library_name = forms.CharField(max_length=96, min_length=5)
    library_layout_config = forms.ChoiceField(
            choices=[
                (None, ""),
                ("SINGLE", "SINGLE"),
                ("PAIRED", "PAIRED"),
            ],
    )
    library_layout_read_length = forms.IntegerField(min_value=0, required=False)
    library_layout_insert_length = forms.IntegerField(min_value=0, required=False)

    library_seq_kit = forms.CharField(max_length=96)
    library_seq_protocol = forms.CharField(max_length=96)


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

    sequencing_org_received_date = forms.DateField(
            label="Date sample was eligible for processing at sequencing lab",
            help_text="YYYY-MM-DD",
            required=False,
    )

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
                ("ION_TORRENT", "Ion Torrent"),
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

    bioinfo_pipe_name = forms.CharField(max_length=96, required=False)
    bioinfo_pipe_version = forms.CharField(max_length=48, required=False)

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


class MajoraPossiblePartialModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.partial = kwargs.pop('partial', False)

        # Map initial data if needed
        kwargs["initial"] = self.map_request_fields(kwargs["initial"])

        super().__init__(*args, **kwargs)

        self.data = self.map_request_fields(self.data)
        self.data = self.modify_preform(self.data)

        # Fix data fields
        # Add the initial keys here too, to allow initial fields to be updated when
        # working with partial forms (e.g. filling in submission_org automatically)
        # Initial data is only used for disabled form fields so this shoudn't cause accidental stomps
        self.partial_request_keys = set(self.data.keys()) | set(kwargs["initial"].keys())

        # Drop any fields that are not specified in the request
        if self.partial:
            allowed = self.partial_request_keys
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


    # Shim function that allows form interfaces to present a different name for
    # a field from the one it represents in the model. This will return the payload
    # dict with keys renamed to the one on the model as appropriate for validation
    @classmethod
    def map_request_fields(cls, data):
        for k, v in cls.Meta.field_map.items():
            if k in data:
                data[v] = data[k]
                del data[k]
        return data

    def _post_clean(self):
        super()._post_clean()

        # Fix the error struct such that the hacked field names match those the
        # user expects to know about
        for k, v in self.Meta.field_map.items():
            if v in self._errors:
                self._errors[k] = self._errors[v]
                del self._errors[v]

    def modify_preform(self, data):
        for field in getattr(self.Meta, "LOWERCASE_FIELDS", []):
            if data.get(field):
                data[field] = data[field].strip()
        for field in getattr(self.Meta, "UPPERCASE_FIELDS", []):
            if data.get(field):
                data[field] = data[field].strip().upper()
        for field in getattr(self.Meta, "COERCE_BOOLEAN", []):
            if data.get(field):
                if type(data.get(field)) is str:
                    b = data[field].strip().upper()
                    if b == "Y" or b == "YES":
                        data[field] = True
                    elif b == "N" or b == "NO":
                        data[field] = False
                    else:
                        data[field] = None
        return data

    def add_error(self, field, error):
        if field not in self.fields:
            # Move errors targeted for missing fields to NON_FIELD_ERRORS and send them to the client
            # Unless we're in partial mode, then just ignore them
            #if not self.partial:
            #    super().add_error(None, error)
            super().add_error(None, error)
        else:
            super().add_error(field, error)

    @staticmethod
    def merge_changed_data(*args):

        changed_fields = []
        nulled_fields = []

        for form in args:
            changed_fields.extend( form.changed_data["changed_fields"] )
            nulled_fields.extend( form.changed_data["nulled_fields"] )

        return {
            "changed_fields": changed_fields,
            "nulled_fields": nulled_fields,
        }

    # Override changed_data property to divide props into changed and nulled
    @cached_property
    def changed_data(self):
        changed_data = super().changed_data

        changed_fields = []
        nulled_fields = []

        for f in changed_data:
            prefixed_name = self.add_prefix(f)
            data_value = self.fields[f].widget.value_from_datadict(self.data, self.files, prefixed_name)
            if data_value is None:
                nulled_fields.append(f)
            else:
                changed_fields.append(f)

        return {
            "changed_fields": changed_fields,
            "nulled_fields": nulled_fields,
        }



class BiosampleArtifactModelForm(MajoraPossiblePartialModelForm):

    taxonomy_identifier = forms.CharField(
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

    class Meta:
        model = models.BiosampleArtifact
        fields = [
            "root_sample_id",
            "sender_sample_id",
            "central_sample_id",
            "sample_type_collected",
            "sample_type_current",
            "sample_site",
            "taxonomy_identifier", # injected
            "root_biosample_source_id",
        ]
        exclude = [ # It is redundant to list these as they are excluded by virtue of being missing from fields, but nice to explain why
            "sample_longitude", # not currently used
            "sample_batch", # not currently used
            "sample_batch_longitude", # not currently used
            "sample_orig_id", # deprecated
            "secondary_identifier", # deprecated
            "secondary_accession", # deprecated
        ]
        field_map = {
            # FROM FORM             TO MODEL
            "swab_site":            "sample_site",
            "sample_type_received": "sample_type_current",
            "source_taxon":         "taxonomy_identifier",
        }
        LOWERCASE_FIELDS = [
            "swab_site",
            "sample_type_collected",
            "sample_type_received",
        ]

    def modify_preform(self, data):
        for field in getattr(self.Meta, "LOWERCASE_FIELDS", []):
            if data.get(field):
                data[field] = data[field].strip()
                if data[field] != "BAL":
                    data[field] = data[field].strip().lower()
        return data

    def clean(self):
        cleaned_data = super().clean()

        # Validate sample name for bar characters
        central_sample_id = cleaned_data.get("central_sample_id")
        if central_sample_id:
            reserved_ch = [".", "/", "\\"]
            for ch in reserved_ch:
                if ch in central_sample_id:
                    self.add_error("central_sample_id", "central_sample_id cannot contain a reserved character: %s" % str(reserved_ch))
                    break

        # Validate swab site
        swab_site = cleaned_data.get("sample_site")
        sample_type = cleaned_data.get("sample_type_collected")
        if sample_type and ("swab" not in sample_type and sample_type != "aspirate") and swab_site:
            self.add_error("sample_type_collected", "Swab site specified but the sample type is not 'swab'")
        #if sample_type == "swab" and not swab_site:
        #    self.add_error("sample_type_collected", "Sample was a swab but you did not specify the swab site")


class BiosampleSourceModelForm(MajoraPossiblePartialModelForm):

    source_type = forms.ChoiceField(
        choices = [
            ("human", "human"),
        ],
        disabled = True,
    )

    class Meta:
        model = models.BiosampleSource
        fields = [
            "secondary_id",
        ]
        exclude = [ # It is redundant to list these as they are excluded by virtue of being missing from fields, but nice to explain why
            "source_type", # injected automatically by initial
        ]
        field_map = {
            # FROM FORM             TO MODEL
            "biosample_source_id":  "secondary_id",
            #"biosample_source_id":  "dice_name",
        }
        UPPERCASE_FIELDS = [
        ]


class BiosourceSamplingProcessModelForm(MajoraPossiblePartialModelForm):

    collection_location_country = forms.CharField(disabled=True)
    collection_location_adm1 = forms.ChoiceField(
            label="Region",
            choices=[
                (None, ""),
                ("UK-ENG", "England"),
                ("UK-SCT", "Scotland"),
                ("UK-WLS", "Wales"),
                ("UK-NIR", "Northern Ireland"),
            ],
    )
    #collection_location_adm2 = forms.ModelChoiceField(
    #        queryset=models.County.objects.all(),
    #        to_field_name="name",
    #        label="County",
    #        required=False,
    #        help_text="Enter the COUNTY from the patient's address. Leave blank if this was not available."
    #)
    source_age = forms.IntegerField(min_value=0, required=False, help_text="Age in years")
    source_sex = forms.ChoiceField(choices=[
            (None, ""),
            ("F", "F"),
            ("M", "M"),
            ("Other", "Other"),
        ], required=False, help_text="Reported sex"
    )

    class Meta:
        model = models.BiosourceSamplingProcess
        fields = [
            "collection_date",
            "received_date",
            "source_age",
            "source_sex",
            "collected_by",
            "collection_location_adm1",
            "collection_location_adm2",
            "private_collection_location_adm2",
            "collection_location_country", # injected as initial
        ]
        exclude = [ # It is redundant to list these as they are excluded by virtue of being missing from fields, but nice to explain why
            "submitted_by", # submission fields are set by Majora, not the user
            "submission_user",
            "submission_org",
            "collection_org", # field is no longer used
            "who",
            "when", # majora fields
        ]
        field_map = {
            # FROM FORM         TO MODEL
            "collecting_org":   "collected_by",
            "country":          "collection_location_country",
            "adm1":             "collection_location_adm1",
            "adm2":             "collection_location_adm2",
            "adm2_private":     "private_collection_location_adm2",
        }
        UPPERCASE_FIELDS = [
            "collection_location_adm2",
        ]

    def clean(self):
        cleaned_data = super().clean()

        # Check a received_date was provided for samples without a collection date
        if not cleaned_data.get("collection_date") and not cleaned_data.get("received_date"):
            if not self.partial:
               self.add_error("received_date", "You must provide a received date for samples without a collection date")

        # Check sample date is not too old, if it is a NEW sample
        if self.instance._state.adding: # apparently this is better than checking instance.pk https://stackoverflow.com/a/907703/2576437
            if cleaned_data.get("collection_date"):
                if cleaned_data["collection_date"] < (timezone.now().date() - datetime.timedelta(days=365)):
                    self.add_error("collection_date", "Sample cannot be collected more than a year ago...")
            if cleaned_data.get("received_date"):
                if cleaned_data["received_date"] < (timezone.now().date() - datetime.timedelta(days=365)):
                    self.add_error("received_date", "Sample cannot be received more than a year ago...")

        # Check received is not before collection
        if cleaned_data.get("collection_date") and cleaned_data.get("received_date"):
            if cleaned_data.get("received_date") < cleaned_data.get("collection_date"):
                self.add_error("collection_date", "Sample cannot be collected after it was received. Perhaps they have been swapped?")

        # Check sample date is not in the future, always
        if cleaned_data.get("collection_date"):
            if cleaned_data["collection_date"] > timezone.now().date():
                self.add_error("collection_date", "Sample cannot be collected in the future")
        if cleaned_data.get("received_date"):
            if cleaned_data["received_date"] > timezone.now().date():
                self.add_error("received_date", "Sample cannot be received in the future")

        # Check sample date is not from before 2020, always
        # thanks for ruining my bbq time MATT
        if cleaned_data.get("collection_date"):
            if cleaned_data["collection_date"].year < 2020:
                self.add_error("collection_date", "Sample cannot be collected before 2020")
        if cleaned_data.get("received_date"):
            if cleaned_data["received_date"].year < 2020:
                self.add_error("received_date", "Sample cannot be received before 2020")

        # Check if the adm2 looks like a postcode
        adm2 = cleaned_data.get("collection_location_adm2", "")
        if adm2:
            if len(adm2) > 0 and re.search('\d', adm2):
                self.add_error("collection_location_adm2", "adm2 cannot contain numbers. Use adm2_private if you are trying to provide an outer postcode")

        # Check for full postcode mistake
        adm2_private = cleaned_data.get("private_collection_location_adm2")
        if adm2_private:
            if " " in adm2_private:
                self.add_error("private_collection_location_adm2", "Enter the first part of the postcode only")


class COGUK_BiosourceSamplingProcessSupplement_ModelForm(MajoraPossiblePartialModelForm):

    # Override collection_pillar from model to specify options
    collection_pillar = forms.TypedChoiceField(choices=[
            (None, None),
            ("1", 1),
            ("2", 2),
            ("103", 103),
            ("34613", 34613),
        ], coerce=int, empty_value=None, required=False)

    class Meta:
        model = models.COGUK_BiosourceSamplingProcessSupplement
        fields = [
            "is_surveillance",
            "is_hcw",
            "employing_hospital_name",
            "employing_hospital_trust_or_board",
            "is_hospital_patient",
            "is_icu_patient",
            "admission_date",
            "admitted_hospital_name",
            "admitted_hospital_trust_or_board",
            "is_care_home_worker",
            "is_care_home_resident",
            "anonymised_care_home_code",
            "admitted_with_covid_diagnosis",
            "collection_pillar",
        ]
        exclude = [ # It is redundant to list these as they are excluded by virtue of being missing from fields, but nice to explain why
            "sampling" # Although this FK needs linking, we'll link this ourselves rather than with the form
        ]
        field_map = {}
        COERCE_BOOLEAN = [
            "is_surveillance",
            "is_hcw",
            "is_hospital_patient",
            "is_care_home_worker",
            "is_care_home_resident",
            "admitted_with_covid_diagnosis",
            "is_icu_patient",
        ]

    def clean(self):
        cleaned_data = super().clean()
        # Force is_surveillance
        if cleaned_data.get("is_surveillance") is None:
            if not self.partial:
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
    pipe_kind = forms.CharField(max_length=64, required=False)
    pipe_name = forms.CharField(max_length=96, required=False)
    pipe_version = forms.CharField(max_length=48, required=False)

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

