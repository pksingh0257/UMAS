from django import forms
from masterdata.models import FundHead, SubHead
from .models import Requirement


class StyledClearableFileInput(forms.ClearableFileInput):
    """
    Same clear/replace behavior as Django's default ClearableFileInput
    (the hidden checkbox is still what actually triggers clearing on
    save), just rendered with a proper red X button instead of the
    default "Currently: ... Clear [checkbox] Change: ..." layout.
    """
    template_name = "requirements_mgmt/widgets/clearable_file_input.html"


class SubHeadSelect(forms.Select):
    """
    Adds data-fund-head="<fund head id>" to every <option>, so the plain
    JS in requirement_form.html can show/hide Sub Head options as the
    Fund selection changes — no AJAX round-trip needed for a table this
    small.
    """

    def __init__(self, *args, fund_head_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fund_head_map = fund_head_map or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        fund_head_id = self.fund_head_map.get(str(value))
        if fund_head_id:
            option["attrs"]["data-fund-head"] = fund_head_id
        return option


class RequirementForm(forms.ModelForm):
    """
    Clerk/head-clerk create & edit form.
    fund_head / sub_head are now wired in as a cascading FK pair — see
    __init__ below and SubHeadSelect above for how the filtering works.
    """

    class Meta:
        model = Requirement
        fields = [
            "item_name", "category", "quantity", "purpose",
            "estimated_cost", "cost_per_unit", "demanded_by",
            "fund_head", "sub_head",
            "purchase_mode", "priority", "attachment",
        ]
        widgets = {
            "item_name": forms.TextInput(attrs={"placeholder": "Item name", "maxlength": 250}),
            "category": forms.TextInput(attrs={"placeholder": "Category", "maxlength": 250}),
            "quantity": forms.NumberInput(attrs={"min": 1}),
            "purpose": forms.TextInput(attrs={"placeholder": "Purpose", "maxlength": 250}),
            "estimated_cost": forms.TextInput(attrs={"placeholder": "Estimated cost", "maxlength": 250}),
            "cost_per_unit": forms.TextInput(attrs={"placeholder": "Cost per unit", "maxlength": 250}),
            "demanded_by": forms.TextInput(attrs={"placeholder": "Name / department", "maxlength": 250}),
            "fund_head": forms.Select(),
            "purchase_mode": forms.Select(),
            "priority": forms.Select(),
            "attachment": StyledClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["fund_head"].queryset = FundHead.objects.filter(is_active=True).order_by("name")
        self.fields["fund_head"].empty_label = "Select Fund"
        self.fields["fund_head"].required = False

        sub_heads = (
            SubHead.objects.filter(is_active=True)
            .select_related("fund_head")
            .order_by("fund_head__name", "name")
        )
        fund_head_map = {str(sh.pk): sh.fund_head_id for sh in sub_heads}

        self.fields["sub_head"].widget = SubHeadSelect(fund_head_map=fund_head_map)
        self.fields["sub_head"].queryset = sub_heads
        self.fields["sub_head"].empty_label = "Select Sub Head"
        self.fields["sub_head"].required = False


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