from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column
from crispy_forms.bootstrap import FormActions

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
