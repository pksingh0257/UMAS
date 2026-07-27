from django import forms
from .models import Requirement


class RequirementForm(forms.ModelForm):
    """
    Clerk/head-clerk create & edit form.
    Matches your mockup exactly: Select Fund is intentionally left out
    (excluded per your note) — add "fund_head" back into `fields` below
    whenever you're ready to wire it up.
    """

    class Meta:
        model = Requirement
        fields = [
            "item_name", "category", "quantity", "purpose",
            "estimated_cost", "demanded_by",
            "purchase_mode", "priority", "attachment",
        ]
        widgets = {
            "item_name": forms.TextInput(attrs={"placeholder": "Item name", "maxlength": 250}),
            "category": forms.TextInput(attrs={"placeholder": "Category", "maxlength": 250}),
            "quantity": forms.NumberInput(attrs={"min": 1}),
            "purpose": forms.TextInput(attrs={"placeholder": "Purpose", "maxlength": 250}),
            "estimated_cost": forms.TextInput(attrs={"placeholder": "Estimated cost", "maxlength": 250}),
            "demanded_by": forms.TextInput(attrs={"placeholder": "Name / department", "maxlength": 250}),
            "purchase_mode": forms.Select(),
            "priority": forms.Select(),
        }


class AODecisionForm(forms.Form):
    """Account Officer's decision on a requirement pending their review."""

    ao_status = forms.ChoiceField(
        choices=Requirement.DECISION_CHOICES,
        widget=forms.Select(),
        label="Status",
    )
    ao_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False,
        label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("ao_status") == "DENIED" and not cleaned.get("ao_remarks"):
            self.add_error("ao_remarks", "Remarks are required when returning a requirement.")
        return cleaned


class CFADecisionForm(forms.Form):
    """CFA's decision on a requirement pending their review."""

    cfa_status = forms.ChoiceField(
        choices=Requirement.DECISION_CHOICES,
        widget=forms.Select(),
        label="Status",
    )
    cfa_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False,
        label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("cfa_status") == "DENIED" and not cleaned.get("cfa_remarks"):
            self.add_error("cfa_remarks", "Remarks are required when returning a requirement.")
        return cleaned