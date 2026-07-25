from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import ProcurementCase
from .forms import CaseStageDataForm, ReturnCaseForm


@login_required
def case_detail(request, case_number):
    case = get_object_or_404(ProcurementCase, case_number=case_number)
    history = case.history.select_related('performed_by').order_by('created_at')

    stage_form = CaseStageDataForm(instance=case)
    return_form = ReturnCaseForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_stage':
            stage_form = CaseStageDataForm(request.POST, instance=case)
            if stage_form.is_valid():
                obj = stage_form.save(commit=False)
                obj.modified_by = request.user
                obj.save()
                messages.success(request, 'Stage data saved.')
                return redirect('case_detail', case_number=case.case_number)

        elif action == 'advance':
            try:
                case.advance(user=request.user)
                messages.success(request, f'Case advanced to {case.get_current_stage_display()}.')
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
            return redirect('case_detail', case_number=case.case_number)

        elif action == 'return_case':
            return_form = ReturnCaseForm(request.POST)
            if return_form.is_valid():
                try:
                    case.return_to_stage(
                        user=request.user,
                        target_stage=return_form.cleaned_data['target_stage'],
                        reason=return_form.cleaned_data['reason'],
                    )
                    messages.success(request, f'Case returned to {case.get_current_stage_display()}.')
                except ValidationError as e:
                    messages.error(request, e.message if hasattr(e, 'message') else str(e))
                return redirect('case_detail', case_number=case.case_number)

    context = {
        'case': case,
        'history': history,
        'stage_form': stage_form,
        'return_form': return_form,
        'role': request.user.role,
    }
    return render(request, 'procurement/case_detail.html', context)


@login_required
def case_list(request):
    role = request.user.role
    STAGE_MAP = {
        'ACCOUNTS_CLERK': ['SURVEY', 'BID_BOQ', 'GEM_ORDER', 'CRAC', 'CRV'],
        'ACCOUNTS_JCO': ['INSPECTION'],
        'ACCOUNTS_OFFICER': ['NOTING'],
        'CFA': ['APPROVAL', 'EAS', 'SANCTION'],
    }
    if role in STAGE_MAP:
        cases = ProcurementCase.objects.filter(current_stage__in=STAGE_MAP[role])
    else:
        cases = ProcurementCase.objects.all()

    return render(request, 'procurement/case_list.html', {
        'cases': cases,
        'role': role,
        'active_nav': 'procurement',
    })


@login_required
def audit_trail(request):
    from .models import CaseStageHistory
    history = CaseStageHistory.objects.select_related('case', 'performed_by').order_by('-created_at')[:100]
    return render(request, 'procurement/audit_trail.html', {
        'history': history,
        'role': request.user.role,
        'active_nav': 'audit_trail',
    })