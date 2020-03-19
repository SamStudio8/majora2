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


class TestSampleForm(forms.Form):

    host_id = forms.CharField(
            label="Pseudonymous patient identifier", max_length=56,
            help_text="Leave blank if not available. <b>DO NOT enter an NHS number here</b>", required=False)
    orig_sample_id = forms.CharField(
            label="Existing sample identifier", max_length=56, required=False,
            help_text="Leave blank if not applicable or available. It will not be possible to collect private metadata for this sample without this"
    )
    sample_id = forms.CharField(
            label="New sample identifier", max_length=56,
            help_text="Heron barcode assigned by WSI"
    )
    collection_date = forms.DateField(
            label="Collection date",
            help_text="YYYY-MM-DD"
    )
    country = forms.CharField(initial="United Kingdom", disabled=True)
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
    age = forms.IntegerField(min_value=0, required=False, help_text="Age in years")
    adm2 = forms.CharField(
            label="Town",
            max_length=10,
            required=False,
            help_text="Enter the town from the patient's address. Leave blank if this was not available."
    )
    adm2_private = forms.CharField(
            label="Outward postcode",
            max_length=10,
            required=False,
            help_text="Enter the <b>first part</b> of the patients home postcode. Leave blank if this was not available."
    )
    submitting_username = forms.CharField(disabled=True, required=False)
    submitting_organisation = forms.ModelChoiceField(queryset=models.Institute.objects.exclude(code__startswith="?").order_by("name"), disabled=True, required=False)
    collecting_organisation = forms.CharField(max_length=100, required=False, help_text="The site that this sample was submitted to. Use the first line of the 'sender' from the corresponding E28")

    source_type = forms.ChoiceField(
        choices = [
            ("human", "human"),
        ],
        initial = "human",
        disabled = True,
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
    sample_site = forms.ChoiceField(
        choices= [
            (None, None),
            ("nose", "nose"),
            ("throat", "throat"),
        ],
        help_text="Provide only if sample_type is swab",
        required=False,
    )


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
                    Column('host_id', css_class="form-group col-md-4 mb-0"),
                    Column('orig_sample_id', css_class="form-group col-md-4 mb-0"),
                    Column('sample_id', css_class="form-group col-md-4 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Form",
                Row(
                    Column('source_type', css_class="form-group col-md-3 mb-0"),
                    Column('sample_type', css_class="form-group col-md-3 mb-0"),
                    Column('sample_site', css_class="form-group col-md-3 mb-0"),
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
            Fieldset("Key dates",
                Row(
                    Column('collection_date', css_class="form-group col-md-6 mb-0"),
                    Column('age', css_class="form-group col-md-2 mb-0"),
                    css_class="form-row",
                ),
            ),
            Fieldset("Collecting and sequencing",
                Row(
                    Column('collecting_organisation', css_class="form-group col-md-5 mb-0"),
                    Column('submitting_username', css_class="form-group col-md-3 mb-0"),
                    Column('submitting_organisation', css_class="form-group col-md-4 mb-0"),
                    css_class="form-row",
                )
            ),
            FormActions(
                    Submit('save', 'Submit sample'),
                    css_class="text-right",
            )
        )

    def clean_sample_id(self):
        sample_id = self.cleaned_data["sample_id"]
        valid_sites = [x.code for x in models.Institute.objects.exclude(code__startswith="?")]
        if sum([sample_id.startswith(x) for x in valid_sites]) == 0:
            raise forms.ValidationError("Sample identifier does not match the WSI manifest.")
        return sample_id

    def clean_adm2_private(self):
        adm2 = self.cleaned_data["adm2_private"]
        if " " in adm2:
            raise forms.ValidationError("Enter the first part of the postcode only")
        return adm2

    def clean_sample_site(self):
        sample_site = self.cleaned_data["sample_site"]
        sample_type = self.cleaned_data["sample_type"]

        if sample_type != "swab" and sample_site:
            raise forms.ValidationError("Swab site specified but the sample type is not 'swab'")
        if sample_type == "swab" and not sample_site:
            raise forms.ValidationError("Sample was a swab but you did not specify the swab site")
        return sample_site

