from django import forms

from django.contrib.auth.models import User
from django.db.models import Q

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column
from crispy_forms.bootstrap import FormActions

from .account_views import generate_username
from . import models

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True, required=False)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirm password")

    organisation = forms.ModelChoiceField(queryset=models.Institute.objects.filter(~Q(code="?")).order_by("name"))
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
            help_text="Sample ID as assigned by WSI COG-UK labelling scheme"
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
    adm2 = forms.CharField(
            label="Outward postcode",
            max_length=10,
            required=False,
    )
    submitting_username = forms.CharField(disabled=True, required=False)
    submitting_organisation = forms.ModelChoiceField(queryset=models.Institute.objects.filter(~Q(code="?")).order_by("name"), disabled=True, required=False)

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
                    Column('country', css_class="form-group col-md-6 mb-0"),
                    Column('adm1', css_class="form-group col-md-3 mb-0"),
                    Column('adm2', css_class="form-group col-md-3 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Key dates",
                Row(
                    Column('collection_date', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Submitting site",
                Row(
                    Column('submitting_username', css_class="form-group col-md-6 mb-0"),
                    Column('submitting_organisation', css_class="form-group col-md-6 mb-0"),
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
        if not sample_id.startswith("WTSI"):
            raise forms.ValidationError("Sample identifier does not match the WTSI manifest.")
        return sample_id
