from django import forms
from django.core.validators import FileExtensionValidator
from .models import ProcurementCase, NotingSheet, EAS


class CaseStageDataForm(forms.ModelForm):
    """
    Shows only the fields relevant to the case's CURRENT stage, so the
    user isn't asked to fill in fields that belong to stages they haven't
    reached yet. The set of fields shown is driven by
    ProcurementCase.STAGE_REQUIRED_FIELDS.
    """
    class Meta:
        model = ProcurementCase
        fields = [
            'survey_notes', 'bid_boq_details', 'comparative_statement',
            'noting_text', 'approval_decision', 'eas_reference',
            'sanction_order_number', 'fund_head', 'sanctioned_amount',
            'gem_order_reference', 'inspection_notes', 'crac_reference',
            'crv_reference',
        ]
        widgets = {
            'survey_notes': forms.Textarea(attrs={'rows': 3}),
            'bid_boq_details': forms.Textarea(attrs={'rows': 3}),
            'comparative_statement': forms.Textarea(attrs={'rows': 3}),
            'noting_text': forms.Textarea(attrs={'rows': 3}),
            'approval_decision': forms.Textarea(attrs={'rows': 3}),
            'inspection_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_stage = self.instance.current_stage
        relevant_fields = set(ProcurementCase.STAGE_REQUIRED_FIELDS.get(current_stage, []))
        # Keep only the current stage's fields visible on the form.
        for name in list(self.fields):
            if name not in relevant_fields:
                del self.fields[name]


class ReturnCaseForm(forms.Form):
    target_stage = forms.ChoiceField(choices=ProcurementCase.STAGE_CHOICES)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))


# ============================================================
# NEW — Noting Sheet forms (merged in from noting_forms.py)
# ============================================================

class NotingSheetForm(forms.ModelForm):
    """
    Only asks for what's genuinely new: A/U and the fund ledger figures.
    Item Name / Qty / Unit Price / Approx Amount are auto-fetched from the
    linked Requirement and shown read-only in the template — they aren't
    form fields at all.
    """

    class Meta:
        model = NotingSheet
        fields = ["au", "amount_allotted", "amount_released", "amount_expended"]
        widgets = {
            "au": forms.TextInput(attrs={"placeholder": "e.g. Nos, Set, Kg"}),
            "amount_allotted": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "amount_released": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "amount_expended": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }


class NotingAODecisionForm(forms.Form):
    # LEGACY — Account Officer review was removed from the Noting Sheet
    # flow (now CFA-only, see NotingSheet.submit_for_approval). Kept only
    # in case any pre-existing PENDING_AO records need manual handling.
    ao_status = forms.ChoiceField(choices=NotingSheet.DECISION_CHOICES, widget=forms.Select(), label="Status")
    ao_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False, label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("ao_status") == "DENIED" and not cleaned.get("ao_remarks"):
            self.add_error("ao_remarks", "Remarks are required when returning a noting sheet.")
        return cleaned


class NotingCFADecisionForm(forms.Form):
    cfa_status = forms.ChoiceField(choices=NotingSheet.DECISION_CHOICES, widget=forms.Select(), label="Status")
    cfa_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False, label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("cfa_status") == "DENIED" and not cleaned.get("cfa_remarks"):
            self.add_error("cfa_remarks", "Remarks are required when returning a noting sheet.")
        return cleaned

# ============================================================
# NEW — EAS forms
# ============================================================

class EASForm(forms.ModelForm):
    """
    Tabular create/edit form for the EAS sheet (Field Name / Value
    layout). file_no and eas_id are plain editable text for now — switch
    to auto-generated later once the numbering scheme is confirmed.
    case_file_no, type_id, and status_id are deliberately NOT on this
    form: case_file_no always mirrors file_no (see EAS.case_file_no
    property), and type_id/status_id are system defaults set at creation.
    """

    class Meta:
        model = EAS
        fields = [
            "file_no", "eas_id", "dsc_goods", "name_supplier",
            "purpose_broad", "designation_cfa", "qty_sanctioned",
            "amount_sanction", "cost_per_unit", "other_charges",
            "total_amount_words", "availability_fund", "sub_details_heads",
            "reference_no", "name_paying_agent", "date_time", "station",
            "unit",
        ]
        widgets = {
            "date_time": forms.DateInput(attrs={"type": "date"}),
            "qty_sanctioned": forms.NumberInput(attrs={"min": 0}),
            "amount_sanction": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "cost_per_unit": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }


class EASAODecisionForm(forms.Form):
    # LEGACY — same reason as NotingAODecisionForm above; EAS approval
    # is now CFA-only (see EAS.submit_for_approval).
    ao_status = forms.ChoiceField(choices=EAS.DECISION_CHOICES, widget=forms.Select(), label="Status")
    ao_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False, label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("ao_status") == "DENIED" and not cleaned.get("ao_remarks"):
            self.add_error("ao_remarks", "Remarks are required when returning an EAS.")
        return cleaned


class EASCFADecisionForm(forms.Form):
    cfa_status = forms.ChoiceField(choices=EAS.DECISION_CHOICES, widget=forms.Select(), label="Status")
    cfa_remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Remarks (required if returning)"}),
        required=False, label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("cfa_status") == "DENIED" and not cleaned.get("cfa_remarks"):
            self.add_error("cfa_remarks", "Remarks are required when returning an EAS.")
        return cleaned


class EASDocumentUploadForm(forms.Form):
    """
    One shared form for all three post-approval uploads (Sanction /
    Contract / Invoice) — the view decides which EAS field to save it to
    based on the doc_type in the URL, so this form only needs to know
    it's a PDF.
    """
    document = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )