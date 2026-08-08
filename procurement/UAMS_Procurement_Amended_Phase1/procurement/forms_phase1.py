"""
Merge these forms into procurement/forms.py after applying the Phase 1
model changes.
"""

from django import forms
from django.forms import inlineformset_factory

from .models import EAS, EASItem, GeMSurvey, GeMSurveyItem, NotingSheet


class GeMSurveyForm(forms.ModelForm):
    class Meta:
        model = GeMSurvey
        fields = [
            "survey_date",
            "search_keywords",
            "survey_notes",
        ]
        widgets = {
            "survey_date": forms.DateInput(attrs={"type": "date"}),
            "survey_notes": forms.Textarea(attrs={"rows": 4}),
        }


class GeMSurveyItemForm(forms.ModelForm):
    class Meta:
        model = GeMSurveyItem
        fields = [
            "serial_number",
            "product_name",
            "gem_product_id",
            "seller_name",
            "make",
            "model",
            "technical_specifications",
            "unit_of_measure",
            "quantity",
            "unit_price",
            "warranty",
            "guarantee",
            "delivery_period",
            "seller_rating",
            "product_image",
            "gem_screenshot",
            "remarks",
            "selected_for_procurement",
        ]
        widgets = {
            "technical_specifications": forms.Textarea(attrs={"rows": 4}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }


GeMSurveyItemFormSet = inlineformset_factory(
    GeMSurvey,
    GeMSurveyItem,
    form=GeMSurveyItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class NotingSheetPhase1Form(forms.ModelForm):
    class Meta:
        model = NotingSheet
        fields = [
            "file_number",
            "sheet_number",
            "branch",
            "noting_date",
            "financial_year",
            "unit_name",
            "station",
            "subject",
            "requirement_summary",
            "detailed_justification",
            "urgency_reason",
            "proposal_text",
            "recommendation_text",
            "selected_survey_item",
            "fund_head_snapshot",
            "sub_head_snapshot",
            "fund_allotted",
            "fund_released",
            "previous_expenditure",
            "current_case_amount",
            "expenditure_including_case",
            "projected_balance",
            "fund_position_as_on",
        ]
        widgets = {
            "noting_date": forms.DateInput(attrs={"type": "date"}),
            "fund_position_as_on": forms.DateInput(attrs={"type": "date"}),
            "requirement_summary": forms.Textarea(attrs={"rows": 4}),
            "detailed_justification": forms.Textarea(attrs={"rows": 5}),
            "urgency_reason": forms.Textarea(attrs={"rows": 3}),
            "proposal_text": forms.Textarea(attrs={"rows": 5}),
            "recommendation_text": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, procurement_case=None, **kwargs):
        super().__init__(*args, **kwargs)

        if procurement_case is not None:
            self.fields["selected_survey_item"].queryset = (
                GeMSurveyItem.objects.filter(
                    survey__case=procurement_case,
                    selected_for_procurement=True,
                )
            )

    def clean(self):
        cleaned = super().clean()

        allotted = cleaned.get("fund_allotted")
        released = cleaned.get("fund_released")
        previous = cleaned.get("previous_expenditure")
        current = cleaned.get("current_case_amount")
        including = cleaned.get("expenditure_including_case")
        balance = cleaned.get("projected_balance")

        if previous is not None and current is not None and including is not None:
            expected = previous + current
            if including != expected:
                self.add_error(
                    "expenditure_including_case",
                    f"Expected previous expenditure + current case = {expected}.",
                )

        if released is not None and including is not None and balance is not None:
            expected = released - including
            if balance != expected:
                self.add_error(
                    "projected_balance",
                    f"Expected released amount - expenditure = {expected}.",
                )

        if allotted is not None and released is not None and released > allotted:
            self.add_error(
                "fund_released",
                "Released amount cannot exceed allotted amount.",
            )

        return cleaned


class EASPhase1Form(forms.ModelForm):
    class Meta:
        model = EAS
        fields = [
            "file_no",
            "eas_id",
            "financial_year",
            "sanction_date",
            "unit",
            "station",
            "dsc_goods",
            "name_supplier",
            "supplier_address",
            "purpose_broad",
            "dfpds_authority_reference",
            "schedule_reference",
            "sub_schedule_reference",
            "designation_cfa",
            "quantity_in_words",
            "subtotal",
            "freight_charges",
            "other_charges_amount",
            "total_sanction_amount",
            "total_amount_words",
            "availability_fund",
            "major_head",
            "minor_head",
            "sub_head_account",
            "detailed_head",
            "cgda_code_head",
            "ifa_applicable",
            "ifa_concurrence_reference",
            "ifa_not_applicable_reason",
            "name_paying_agent",
        ]
        widgets = {
            "sanction_date": forms.DateInput(attrs={"type": "date"}),
            "supplier_address": forms.Textarea(attrs={"rows": 3}),
            "ifa_not_applicable_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()

        subtotal = cleaned.get("subtotal") or 0
        freight = cleaned.get("freight_charges") or 0
        other = cleaned.get("other_charges_amount") or 0
        total = cleaned.get("total_sanction_amount")

        expected = subtotal + freight + other

        if total is not None and total != expected:
            self.add_error(
                "total_sanction_amount",
                f"Expected subtotal + freight + other charges = {expected}.",
            )

        if cleaned.get("ifa_applicable"):
            if not cleaned.get("ifa_concurrence_reference"):
                self.add_error(
                    "ifa_concurrence_reference",
                    "IFA concurrence reference is required.",
                )
        else:
            if not cleaned.get("ifa_not_applicable_reason"):
                self.add_error(
                    "ifa_not_applicable_reason",
                    "Reason for non-applicability is required.",
                )

        return cleaned


class EASItemForm(forms.ModelForm):
    class Meta:
        model = EASItem
        fields = [
            "serial_number",
            "item_description",
            "unit_of_measure",
            "quantity",
            "unit_price",
        ]
        widgets = {
            "item_description": forms.Textarea(attrs={"rows": 3}),
        }


EASItemFormSet = inlineformset_factory(
    EAS,
    EASItem,
    form=EASItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
