from django import forms
from django.core.validators import FileExtensionValidator
from django.forms import inlineformset_factory
from .models import ProcurementCase, NotingSheet, NotingSheetItem, EAS
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import ConveningOrder


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
    class Meta:
        model = NotingSheet
        fields = [
            "file_no", "branch", "sheet_no", "dated", "financial_year",
            "paragraph_1", "paragraph_2",
            "amount_allotted", "amount_released", "amount_expended", "remarks",
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
            "amount_allotted": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "amount_released": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "amount_expended": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
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

User = get_user_model()


class ConveningOrderForm(forms.ModelForm):
    additional_members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 5}),
        label="Additional Members",
    )

    class Meta:
        model = ConveningOrder
        fields = [
            "procurement_case",
            "order_number",
            "order_date",
            "subject_title",
            "committee_purpose",
            "place_of_proceedings",
            "start_date",
            "completion_due_date",
            "applicable_authority_rule",
            "presiding_officer",
            "member_1",
            "member_2",
            "additional_members",
            "technical_representative",
            "member_secretary",
            "convening_authority",
            "report_submission_to",
            "terms_of_reference",
            "special_instructions",
            "remarks",
        ]

        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "completion_due_date": forms.DateInput(attrs={"type": "date"}),
            "subject_title": forms.TextInput(attrs={"maxlength": 500}),
            "place_of_proceedings": forms.TextInput(attrs={"maxlength": 250}),
            "applicable_authority_rule": forms.TextInput(attrs={"maxlength": 250}),
            "terms_of_reference": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Enter at least one Terms of Reference."}
            ),
            "special_instructions": forms.Textarea(attrs={"rows": 4}),
            "remarks": forms.Textarea(attrs={"rows": 4, "maxlength": 1000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        active_users = User.objects.filter(is_active=True).order_by("username")

        self.fields["presiding_officer"].queryset = active_users
        self.fields["member_1"].queryset = active_users
        self.fields["member_2"].queryset = active_users
        self.fields["technical_representative"].queryset = active_users
        self.fields["member_secretary"].queryset = active_users
        self.fields["convening_authority"].queryset = active_users
        self.fields["report_submission_to"].queryset = active_users

        self.fields["procurement_case"].queryset = (
            ProcurementCase.objects
            .filter(is_closed=False, approval_decision__isnull=False)
            .exclude(approval_decision="")
            .order_by("-created_at")
        )

    def clean(self):
        cleaned = super().clean()

        procurement_case = cleaned.get("procurement_case")
        order_date = cleaned.get("order_date")
        start_date = cleaned.get("start_date")
        completion_due_date = cleaned.get("completion_due_date")

        presiding = cleaned.get("presiding_officer")
        member_1 = cleaned.get("member_1")
        member_2 = cleaned.get("member_2")
        technical = cleaned.get("technical_representative")
        secretary = cleaned.get("member_secretary")
        authority = cleaned.get("convening_authority")
        report_to = cleaned.get("report_submission_to")

        if procurement_case:
            approval_value = (procurement_case.approval_decision or "").strip().upper()

            if approval_value != "APPROVED":
                self.add_error(
                    "procurement_case",
                    "Procurement case must be approved before creating a Convening Order.",
                )

            if procurement_case.is_closed:
                self.add_error(
                    "procurement_case",
                    "Only an active procurement case can be selected.",
                )

        if procurement_case and order_date:
            try:
                sanction_date = procurement_case.requirement_item.noting_sheet.eas.date_time
                if sanction_date and order_date < sanction_date.date():
                    self.add_error(
                        "order_date",
                        "Order Date cannot be before the sanction/EAS date.",
                    )
            except (AttributeError, TypeError):
                pass

        if start_date and completion_due_date and completion_due_date < start_date:
            self.add_error(
                "completion_due_date",
                "Completion Due Date must be on or after Start Date.",
            )

        if presiding and member_1 and presiding.pk == member_1.pk:
            self.add_error("member_1", "The same person cannot occupy multiple committee roles.")

        if presiding and member_2 and presiding.pk == member_2.pk:
            self.add_error("member_2", "The same person cannot occupy multiple committee roles.")

        if member_1 and member_2 and member_1.pk == member_2.pk:
            self.add_error("member_2", "Member 1 and Member 2 must be different persons.")

        selected_people = [
            ("Presiding Officer", presiding),
            ("Member 1", member_1),
            ("Member 2", member_2),
            ("Technical Representative", technical),
            ("Member Secretary", secretary),
            ("Convening Authority", authority),
            ("Report Submission To", report_to),
        ]

        seen = {}

        for role_name, person in selected_people:
            if not person:
                continue

            if person.pk in seen:
                self.add_error(
                    "convening_authority",
                    f"{role_name} and {seen[person.pk]} cannot be the same person.",
                )
            else:
                seen[person.pk] = role_name

        tor = cleaned.get("terms_of_reference")

        if not tor or not tor.strip():
            self.add_error(
                "terms_of_reference",
                "At least one Terms of Reference is required.",
            )

        return cleaned
