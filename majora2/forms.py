import datetime

from django import forms

from django.contrib.auth.models import User
from django.db.models import Q

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column
from crispy_forms.bootstrap import FormActions

from .account_views import generate_username
from . import models

from sshpubkeys import SSHKey

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True, required=False)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Password", min_length=8)
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirm password", min_length=8)

    organisation = forms.ModelChoiceField(queryset=models.Institute.objects.exclude(code__startswith="?").order_by("name"))
    ssh_key = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), label="SSH Public Key")

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
        ssh_key = "".join(self.cleaned_data["ssh_key"].splitlines())
        #if '\n' in ssh_key or '\r' in ssh_key:
        #    raise forms.ValidationError("Your public key should not contain any new line characters")

        key = SSHKey(ssh_key)
        try:
            key.parse()
        except Exception as e:
            raise forms.ValidationError("Unable to decode your key. Please ensure this is your public key and has been entered correctly.")
        return ssh_key


class TestLibraryForm(forms.Form):
    library_name = forms.CharField()
    biosamples = forms.ModelMultipleChoiceField(queryset=models.BiosampleArtifact.objects.filter(central_sample_id__isnull=False), required=True, to_field_name="central_sample_id")

    #library_strategy = models.CharField(max_length=24, blank=True, null=True)
    #library_source = models.CharField(max_length=24, blank=True, null=True)
    #library_selection = models.CharField(max_length=24, blank=True, null=True)
    #library_layout_config = models.CharField(max_length=24, blank=True, null=True)
    #library_layout_length = models.PositiveIntegerField(blank=True, null=True)
    #design_description = models.CharField(max_length=128, blank=True, null=True)

class TestSequencingForm(forms.Form):
    library_name = forms.ModelChoiceField(queryset=models.LibraryArtifact.objects.all(), required=True, to_field_name="dice_name")
    sequencing_id = forms.UUIDField()
    instrument_make = forms.ChoiceField(
            label="Instrument Make",
            choices=[
                (None, ""),
                ("ILLUMINA", "Illumina"),
                ("OXFORD_NANOPORE", "Oxford Nanopore"),
            ],
    )

    @staticmethod
    def modify_preform(data):
        UPPERCASE_FIELDS = [
            "instrument_make",
        ]
        for field in UPPERCASE_FIELDS:
            if data.get(field):
                data[field] = data[field].upper().replace(' ', '_')
        return data

    #instrument_model = models.CharField(max_length=24)
    #flowcell_type = models.CharField(max_length=48, blank=True, null=True)
    #flowcell_id = models.CharField(max_length=48, blank=True, null=True)



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
            label="New sample identifier", max_length=56,
            help_text="Heron barcode assigned by WSI"
    )
    collection_date = forms.DateField(
            label="Collection date",
            help_text="YYYY-MM-DD"
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
    sample_type = forms.ChoiceField(
        choices= [
            (None, "Unknown"),
            ("swab", "swab"),
            ("sputum", "sputum"),
            ("BAL", "BAL"),
            ("extract", "extract"),
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
        ],
        help_text="Provide only if sample_type is swab",
        required=False,
    )

    override_heron = forms.BooleanField(
            label="Override Heron validator",
            help_text="Enable this checkbox if your sample has not been assigned a Heron identifier. <i>e.g.</i> The sample has already been submitted to GISAID",
            required=False)
    secondary_identifier = forms.CharField(
            max_length=256,
            label="GISAID identifier string",
            help_text="New COG-UK samples will have GISAID strings automatically composed. If this sample has already been submitted to GISAID, provide the identifier here.",
            required=False)
    secondary_accession = forms.CharField(
            max_length=256,
            label="GISAID accession",
            help_text="If this sample has already been submitted to GISAID, provide the accession here.",
            required=False)


    #tube_dice = forms.CharField()
    #box_dice = forms.CharField()
    #tube_x = forms.IntegerField()
    #tube_y = forms.IntegerField()
    #current_sample_type = forms.ChoiceField()
    #accepted = forms.BooleanField()
    #quarantine_reason = forms.ChoiceField()
    #received_date =

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
                    Column('sample_type', css_class="form-group col-md-3 mb-0"),
                    Column('swab_site', css_class="form-group col-md-3 mb-0"),
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
                    Column('collection_date', css_class="form-group col-md-6 mb-0"),
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
                Row(
                    Column('override_heron', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            FormActions(
                    Submit('save', 'Submit sample'),
                    css_class="text-right",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        # Check barcode starts with a Heron prefix, unless this has been overridden
        sample_id = cleaned_data["central_sample_id"]
        if cleaned_data["override_heron"] is False:
            valid_sites = [x.code for x in models.Institute.objects.exclude(code__startswith="?")]
            if sum([sample_id.startswith(x) for x in valid_sites]) == 0:
                self.add_error("central_sample_id", "Sample identifier does not match the WSI manifest.")

        # Check sample date is not in the future
        if cleaned_data["collection_date"] > datetime.date.today():
            self.add_error("collection_date", "Sample cannot be collected in the future")

        # Check for full postcode mistake
        adm2 = cleaned_data["adm2_private"]
        if " " in adm2:
            self.add_error("adm2_private", "Enter the first part of the postcode only")

        # Validate swab site
        swab_site = cleaned_data["swab_site"]
        sample_type = cleaned_data["sample_type"]
        if sample_type != "swab" and swab_site:
            self.add_error("sample_type", "Swab site specified but the sample type is not 'swab'")
        if sample_type == "swab" and not swab_site:
            self.add_error("sample_type", "Sample was a swab but you did not specify the swab site")

        # Validate accession
        secondary_identifier = cleaned_data["secondary_identifier"]
        if secondary_identifier and not cleaned_data["secondary_accession"]:
            self.add_error("secondary_accession", "Accession for secondary identifier not provided")

