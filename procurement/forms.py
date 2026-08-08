from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.forms import inlineformset_factory
from .models import ProcurementCase, NotingSheet, NotingSheetItem, EAS, ConveningOrder

User = get_user_model()


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
        for name in list(self.fields):
            if name not in relevant_fields:
                del self.fields[name]


class ReturnCaseForm(forms.Form):
    target_stage = forms.ChoiceField(choices=ProcurementCase.STAGE_CHOICES)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))


# ============================================================
# Noting Sheet forms
# ============================================================

class NotingSheetForm(forms.ModelForm):
    """
    CHANGED: amount_allotted / amount_released / amount_expended are NOT
    form fields anymore — they're computed server-side in the view
    (Allotted/Released from the Requirement's Fund+Sub Head ledger,
    Expended from this sheet's own item total) and set directly on the
    model instance before save(), not typed by the clerk.
    """
    class Meta:
        model = NotingSheet
        fields = [
            "file_no", "branch", "sheet_no", "dated", "financial_year",
            "paragraph_1", "paragraph_2", "remarks",
            "approval_recipient",
        ]
        widgets = {
            "file_no": forms.TextInput(attrs={"placeholder": "314404/ACG/ /A"}),
            "branch": forms.TextInput(),
            "sheet_no": forms.TextInput(attrs={"placeholder": "One of One"}),
            "dated": forms.DateInput(attrs={"type": "date"}),
            "financial_year": forms.TextInput(attrs={"placeholder": "2026-27"}),
            "paragraph_1": forms.TextInput(attrs={"maxlength": 200, "placeholder": "Subject / purport of this noting sheet"}),
            "paragraph_2": forms.Textarea(attrs={"rows": 5, "maxlength": 500, "placeholder": "1. ...\n2. ..."}),
            "remarks": forms.Textarea(attrs={"rows": 2, "maxlength": 200}),
            "approval_recipient": forms.TextInput(attrs={"placeholder": "e.g. CFA (CO)"}),
        }


class NotingSheetItemForm(forms.ModelForm):
    class Meta:
        model = NotingSheetItem
        fields = ["description", "au", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "ns-input", "placeholder": "Item description"}),
            "au": forms.TextInput(attrs={"class": "ns-input ns-au", "placeholder": "Nos"}),
            "quantity": forms.NumberInput(attrs={"class": "ns-input ns-qty", "min": 1}),
            "unit_price": forms.NumberInput(attrs={"class": "ns-input ns-price", "min": 0, "step": "0.01"}),
        }


NotingSheetItemFormSet = inlineformset_factory(
    NotingSheet, NotingSheetItem, form=NotingSheetItemForm,
    extra=1, can_delete=True,
)


class NotingCFADecisionForm(forms.Form):
    """CFA-only decision — matches your real NotingSheet workflow (no AO step)."""
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
# EAS forms — RECONSTRUCTED from eas_form.html's field layout,
# eas_detail.html's cfa_form usage, and eas_upload_document's
# form.cleaned_data["document"] call in views.py. Please verify
# carefully — the real byte-for-byte original wasn't recoverable.
# ============================================================

class EASForm(forms.ModelForm):
    class Meta:
        model = EAS
        fields = [
            "file_no", "eas_id", "dsc_goods", "name_supplier", "purpose_broad",
            "designation_cfa", "qty_sanctioned", "amount_sanction", "cost_per_unit",
            "other_charges", "total_amount_words", "availability_fund",
            "sub_details_heads", "reference_no", "name_paying_agent",
            "date_time", "station", "unit",
        ]
        # NOTE: case_file_no is NOT a field — it's a read-only property on
        # the model that always mirrors file_no (see eas_form.html's
        # disabled "(same as File No)" placeholder).
        widgets = {
            "file_no": forms.TextInput(),
            "eas_id": forms.TextInput(),
            "dsc_goods": forms.TextInput(),
            "name_supplier": forms.TextInput(),
            "purpose_broad": forms.TextInput(),
            "designation_cfa": forms.TextInput(),
            "qty_sanctioned": forms.NumberInput(attrs={"min": 1}),
            "amount_sanction": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "cost_per_unit": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "other_charges": forms.TextInput(),
            "total_amount_words": forms.TextInput(),
            "availability_fund": forms.TextInput(),
            "sub_details_heads": forms.TextInput(),
            "reference_no": forms.TextInput(),
            "name_paying_agent": forms.TextInput(),
            "date_time": forms.DateInput(attrs={"type": "date"}),
            "station": forms.TextInput(),
            "unit": forms.TextInput(),
        }


class EASCFADecisionForm(forms.Form):
    """CFA-only decision — mirrors NotingCFADecisionForm exactly."""
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
    """Single-file upload used for Sanction / Contract / Invoice — the
    doc_type (which model field it writes to) is chosen in the view, not
    here (see eas_upload_document / EAS_DOCUMENT_FIELDS)."""
    document = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )

# ============================================================
# Convening Order form — RECONSTRUCTED. views.py already imported this
# and convening_order_form.html already rendered its fields, but this
# class itself was missing from forms.py entirely (that's the
# ImportError you hit). Built directly from what those two files already
# expect:
#
#   - additional_members must yield iterable User objects in
#     cleaned_data — convening_order_create does
#     `[user.pk for user in additional_members]`. Declared explicitly as
#     ModelMultipleChoiceField rather than left to ModelForm's default
#     mapping (which would treat the model's JSONField as raw JSON text
#     in a Textarea — wrong shape entirely for what the view expects).
#   - Personnel dropdowns are restricted to active users only, per the
#     "Only active personnel are available in the personnel dropdowns"
#     rule already listed in convening_order_form.html's validation box.
#   - clean() enforces two more of those already-listed rules:
#     completion date >= start date, and no person holding more than one
#     committee role. Also checks order date against the EAS's date, if
#     an `eas` instance is passed in (see __init__) — pass it from the
#     view so this can run; without it, that one check is silently
#     skipped rather than raising.
#
# NOT implemented (need data/views this form doesn't have visibility
# into — flagging rather than guessing):
#   - "Procurement case must be approved and active" — no explicit
#     approved/active status exists on ProcurementCase itself; queryset
#     is narrowed to is_closed=False as the closest sane default. Note
#     also that convening_order_create currently sets
#     order.procurement_case from its own local `procurement_case`
#     variable (derived from the EAS), not from this field's cleaned
#     value — so this field is effectively informational display only
#     right now, not what actually determines the saved case.
#   - "Presiding Officer seniority should be checked when rank
#     information is available" — no rank field visible on User here.
#   - "Approved orders must not be overwritten; amendments use a new
#     version" — an edit-view concern; no convening_order_edit view
#     exists yet to enforce this against.
# ============================================================

class ConveningOrderForm(forms.ModelForm):
    additional_members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        required=False,
        widget=forms.SelectMultiple(),
    )

    class Meta:
        model = ConveningOrder
        fields = [
            "procurement_case", "order_number", "order_date",
            "subject_title", "committee_purpose", "place_of_proceedings",
            "start_date", "completion_due_date", "applicable_authority_rule",
            "presiding_officer", "member_1", "member_2", "additional_members",
            "technical_representative", "member_secretary", "convening_authority",
            "report_submission_to", "terms_of_reference", "special_instructions",
            "remarks",
        ]
        widgets = {
            "order_number": forms.TextInput(attrs={"maxlength": 50}),
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "subject_title": forms.TextInput(attrs={"maxlength": 500}),
            "committee_purpose": forms.Select(),
            "place_of_proceedings": forms.TextInput(),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "completion_due_date": forms.DateInput(attrs={"type": "date"}),
            "applicable_authority_rule": forms.TextInput(),
            "terms_of_reference": forms.Textarea(attrs={"rows": 3}),
            "special_instructions": forms.Textarea(attrs={"rows": 2}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, eas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._eas = eas

        active_users = User.objects.filter(is_active=True).order_by("username")
        for field_name in (
            "presiding_officer", "member_1", "member_2",
            "technical_representative", "member_secretary", "convening_authority",
            "report_submission_to",
        ):
            self.fields[field_name].queryset = active_users

        self.fields["procurement_case"].queryset = ProcurementCase.objects.filter(is_closed=False)

    def clean(self):
        cleaned = super().clean()

        start_date = cleaned.get("start_date")
        completion_due_date = cleaned.get("completion_due_date")
        if start_date and completion_due_date and completion_due_date < start_date:
            self.add_error("completion_due_date", "Completion due date must be on or after the start date.")

        order_date = cleaned.get("order_date")
        if order_date and self._eas is not None and getattr(self._eas, "date_time", None):
            if order_date < self._eas.date_time:
                self.add_error("order_date", "Order date cannot precede the EAS/sanction date.")

        role_fields = [
            "presiding_officer", "member_1", "member_2",
            "technical_representative", "member_secretary",
            "convening_authority", "report_submission_to",
        ]
        seen = {}
        for field_name in role_fields:
            person = cleaned.get(field_name)
            if person is None:
                continue
            if person in seen:
                self.add_error(
                    field_name,
                    f"{person} is already assigned as {seen[person]} — "
                    "the same person can't hold multiple committee roles.",
                )
            else:
                seen[person] = field_name

        return cleaned