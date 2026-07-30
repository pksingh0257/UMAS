from django import forms

from .models import FundEntry


class FundEntryForm(forms.ModelForm):
    """
    Form used by the Account Officer to create or correct a Fund Entry.
    """

    class Meta:
        model = FundEntry

        fields = [
            "financial_year",
            "sub_head",
            "entry_type",
            "amount",
            "entry_date",
            "source",
            "authority_number",
            "authority_date",
            "remarks",
        ]

        widgets = {
            "financial_year": forms.Select(
                attrs={"class": "form-select"}
            ),
            "sub_head": forms.Select(
                attrs={"class": "form-select"}
            ),
            "entry_type": forms.Select(
                attrs={"class": "form-select"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                }
            ),
            "entry_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "source": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "authority_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "authority_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }