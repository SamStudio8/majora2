from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column
from crispy_forms.bootstrap import FormActions

class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, disabled=True)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirm password")

    organisation = forms.CharField(max_length=100)
    ssh_key = forms.CharField(widget=forms.Textarea, label="SSH Key")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("User",
                Row(
                    Column('username', css_class="form-group col-md-6 mb-0"),
                    Column('email', css_class="form-group col-md-6 mb-0"),
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

class TestSampleForm(forms.Form):

    host_id = forms.CharField(
            label="Pseudonymised patient identifier", max_length=56)
    sample_id = forms.CharField(
            label="Sample identifier as assigned by WTSI", max_length=56)
    collection_date = forms.DateField(
            label="Collection date (YYYY-MM-DD)")
    country = forms.CharField(initial="United Kingdom", disabled=True)
    adm0 = forms.ChoiceField(
            label="Region",
            initial="",
            choices=[
                ("UK-ENG", "England"),
                ("UK-SCT", "Scotland"),
                ("UK-WLS", "Wales"),
                ("UK-NIR", "Northern Ireland"),
            ],
    )
    adm1 = forms.CharField(
            label="Outward postcode",
            max_length=10,
    )
    submitting_username = forms.CharField(disabled=True)
    submitting_organisation = forms.CharField(disabled=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Identifiers",
                Row(
                    Column('host_id', css_class="form-group col-md-6 mb-0"),
                    Column('sample_id', css_class="form-group col-md-6 mb-0"),
                    css_class="form-row",
                )
            ),
            Fieldset("Locality",
                Row(
                    Column('country', css_class="form-group col-md-6 mb-0"),
                    Column('adm0', css_class="form-group col-md-3 mb-0"),
                    Column('adm1', css_class="form-group col-md-3 mb-0"),
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
