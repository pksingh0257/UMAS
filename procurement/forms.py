from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.forms import inlineformset_factory

from .models import (
    ProcurementCase,
    NotingSheet,
    NotingSheetItem,
    EAS,
    ConveningOrder,
)

User = get_user_model()


class CaseStageDataForm(forms.ModelForm):
    """
    Shows only the fields relevant to the case's CURRENT stage, so the
    user isn't asked to fill in fields that belong to stages they haven't
    reached yet.
    """

    class Meta:
        model = ProcurementCase
        fields = [
            "survey_notes",
            "bid_boq_details",
            "comparative_statement",
            "noting_text",
            "approval_decision",
            "eas_reference",
            "sanction_order_number",
            "fund_head",
            "sanctioned_amount",
            "gem_order_reference",
            "inspection_notes",
            "crac_reference",
            "crv_reference",
        ]
        widgets = {
            "survey_notes": forms.Textarea(attrs={"rows": 3}),
            "bid_boq_details": forms.Textarea(attrs={"rows": 3}),
            "comparative_statement": forms.Textarea(attrs={"rows": 3}),
            "noting_text": forms.Textarea(attrs={"rows": 3}),
            "approval_decision": forms.Textarea(attrs={"rows": 3}),
            "inspection_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_stage = self.instance.current_stage

        relevant_fields = set(
            ProcurementCase.STAGE_REQUIRED_FIELDS.get(
                current_stage,
                []
            )
        )

        for name in list(self.fields):
            if name not in relevant_fields:
                del self.fields[name]


class ReturnCaseForm(forms.Form):
    target_stage = forms.ChoiceField(
        choices=ProcurementCase.STAGE_CHOICES
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2})
    )


# ============================================================
# Noting Sheet forms
# ============================================================

class NotingSheetForm(forms.ModelForm):

    class Meta:
        model = NotingSheet

        fields = [
            "file_no",
            "branch",
            "sheet_no",
            "dated",
            "financial_year",
            "paragraph_1",
            "paragraph_2",
            "amount_allotted",
            "amount_released",
            "amount_expended",
            "remarks",
            "approval_recipient",
        ]

        widgets = {
            "file_no": forms.TextInput(
                attrs={
                    "placeholder": "314404/ACG/ /A"
                }
            ),

            "branch": forms.TextInput(
                attrs={
                    "placeholder": "Acct Branch"
                }
            ),

            "sheet_no": forms.TextInput(
                attrs={
                    "placeholder": "One of One"
                }
            ),

            "dated": forms.DateInput(
                attrs={
                    "type": "date"
                }
            ),

            "financial_year": forms.TextInput(
                attrs={
                    "placeholder": "2026-27"
                }
            ),

            "paragraph_1": forms.TextInput(
                attrs={
                    "maxlength": 200,
                    "placeholder": "Enter Purport / Subject"
                }
            ),

            "paragraph_2": forms.Textarea(
                attrs={
                    "rows": 6,
                    "maxlength": 500,
                    "placeholder": "Enter Requirement / Justification"
                }
            ),

            "amount_allotted": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.01"
                }
            ),

            "amount_released": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.01"
                }
            ),

            "amount_expended": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.01"
                }
            ),

            "remarks": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 200
                }
            ),

            "approval_recipient": forms.TextInput(
                attrs={
                    "placeholder": "e.g. CFA (CO)"
                }
            ),
        }


class NotingSheetItemForm(forms.ModelForm):

    class Meta:
        model = NotingSheetItem
        fields = [
            "description",
            "au",
            "quantity",
            "unit_price",
        ]

        widgets = {
            "description": forms.TextInput(
                attrs={
                    "class": "ns-input",
                    "placeholder": "Item description"
                }
            ),

            "au": forms.TextInput(
                attrs={
                    "class": "ns-input ns-au",
                    "placeholder": "Nos"
                }
            ),

            "quantity": forms.NumberInput(
                attrs={
                    "class": "ns-input ns-qty",
                    "min": 1
                }
            ),

            "unit_price": forms.NumberInput(
                attrs={
                    "class": "ns-input ns-price",
                    "min": 0,
                    "step": "0.01"
                }
            ),
        }


NotingSheetItemFormSet = inlineformset_factory(
    NotingSheet,
    NotingSheetItem,
    form=NotingSheetItemForm,
    extra=1,
    can_delete=True,
)


class NotingCFADecisionForm(forms.Form):
    """
    CFA-only decision — matches the real NotingSheet workflow.
    """

    cfa_status = forms.ChoiceField(
        choices=NotingSheet.DECISION_CHOICES,
        widget=forms.Select(),
        label="Status",
    )

    cfa_remarks = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Remarks (required if returning)"
            }
        ),
        required=False,
        label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()

        if (
            cleaned.get("cfa_status") == "DENIED"
            and not cleaned.get("cfa_remarks")
        ):
            self.add_error(
                "cfa_remarks",
                "Remarks are required when returning a noting sheet."
            )

        return cleaned


# ============================================================
# EAS forms
# ============================================================

class EASForm(forms.ModelForm):
    """
    EAS fields such as file_no, eas_id, dsc_goods, purpose_broad,
    qty_sanctioned, amount_sanction and cost_per_unit are populated
    automatically from the linked NotingSheet.

    The remaining fields are editable by the clerk.
    """

    class Meta:
        model = EAS

        fields = [
            "name_supplier",
            "designation_cfa",
            "other_charges",
            "total_amount_words",
            "availability_fund",
            "major",
            "minor",
            "reference_no",
            "name_paying_agent",
            "date_time",
            "station",
            "unit",
        ]

        widgets = {
            "name_supplier": forms.TextInput(),
            "designation_cfa": forms.TextInput(),
            "other_charges": forms.TextInput(),
            "total_amount_words": forms.TextInput(),
            "availability_fund": forms.TextInput(),
            "major": forms.TextInput(),
            "minor": forms.TextInput(),
            "reference_no": forms.TextInput(),
            "name_paying_agent": forms.TextInput(),
            "date_time": forms.DateInput(
                attrs={"type": "date"}
            ),
            "station": forms.TextInput(),
            "unit": forms.TextInput(),
        }


class EASCFADecisionForm(forms.Form):
    """
    CFA-only decision — mirrors NotingCFADecisionForm.
    """

    cfa_status = forms.ChoiceField(
        choices=EAS.DECISION_CHOICES,
        widget=forms.Select(),
        label="Status",
    )

    cfa_remarks = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Remarks (required if returning)"
            }
        ),
        required=False,
        label="Remarks",
    )

    def clean(self):
        cleaned = super().clean()

        if (
            cleaned.get("cfa_status") == "DENIED"
            and not cleaned.get("cfa_remarks")
        ):
            self.add_error(
                "cfa_remarks",
                "Remarks are required when returning an EAS."
            )

        return cleaned


class EASDocumentUploadForm(forms.Form):
    """
    Single-file upload used for Sanction / Contract / Invoice.
    """

    document = forms.FileField(
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf"]
            )
        ]
    )


# ============================================================
# Convening Order form
# ============================================================

class ConveningOrderForm(forms.ModelForm):

    class Meta:
        model = ConveningOrder

        fields = [
            "description",
            "presiding_officer",
            "member_1",
            "member_2",
            "completion_date",
            "two_ic_name",
            "two_ic_rank",
            "two_ic_appointment",
            "order_date",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": (
                        "Enter Para 1 exactly as it should "
                        "appear in the Convening Order."
                    ),
                }
            ),

            "presiding_officer": forms.TextInput(
                attrs={
                    "placeholder": "e.g. SS-52548A Lt Nitin Bhandari"
                }
            ),

            "member_1": forms.TextInput(
                attrs={
                    "placeholder": "e.g. JC-288757M Sub Shiv Singh"
                }
            ),

            "member_2": forms.TextInput(
                attrs={
                    "placeholder": "e.g. JC-294912Y Sub Madan Lal"
                }
            ),

            "completion_date": forms.DateInput(
                attrs={
                    "type": "date"
                }
            ),

            "two_ic_name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Rathan Kumar HS"
                }
            ),

            "two_ic_rank": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Lt Col"
                }
            ),

            "two_ic_appointment": forms.TextInput(
                attrs={
                    "placeholder": "2IC"
                }
            ),

            "order_date": forms.DateInput(
                attrs={
                    "type": "date"
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()

        completion_date = cleaned.get("completion_date")
        order_date = cleaned.get("order_date")

        if (
            completion_date
            and order_date
            and completion_date < order_date
        ):
            self.add_error(
                "completion_date",
                "Date of Completion cannot be before the Convening Order date."
            )

        people = [
            cleaned.get("presiding_officer"),
            cleaned.get("member_1"),
            cleaned.get("member_2"),
        ]

        people = [
            str(person).strip().lower()
            for person in people
            if person
        ]

        if len(people) != len(set(people)):
            raise forms.ValidationError(
                "Presiding Officer, Member 1 and Member 2 must be different."
            )

        return cleaned