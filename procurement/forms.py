from django import forms
from .models import ProcurementCase


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