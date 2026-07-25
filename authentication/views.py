from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        role = request.POST.get('role')
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if role and user.role != role:
                messages.error(request, 'Selected role does not match this account.')
                return render(request, 'authentication/login.html')
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'authentication/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# Stage ownership per Section 13's stage-responsibility table.
CLERK_STAGES = ['SURVEY', 'BID_BOQ', 'GEM_ORDER', 'CRAC', 'CRV']
JCO_STAGES = ['INSPECTION']
OFFICER_STAGES = ['NOTING']
CFA_STAGES = ['APPROVAL', 'EAS', 'SANCTION']


def _build_workflow_steps(case):
    """
    Maps our 12-stage ProcurementCase workflow onto the 6 macro-phases
    shown on the dashboard's workflow visual. Display-only grouping -
    does not change the underlying model or business rules.
    """
    from procurement.models import ProcurementCase
    seq = ProcurementCase.STAGE_SEQUENCE

    groups = [
        ('Requirement Created', 'Clerk', ['SURVEY']),
        ('Head Clerk Check', 'Cross-check', ['BID_BOQ']),
        ('Account Officer', 'Financial check', ['NOTING']),
        ('CFA Approval', 'Final approval', ['APPROVAL', 'EAS', 'SANCTION']),
        ('Procurement', 'Document processing', ['GEM_ORDER', 'INSPECTION', 'CRAC', 'CRV']),
        ('Payment', 'Final payment', ['PAYMENT_TRACKING', 'CASE_CLOSED']),
    ]

    if not case:
        return [{'label': g[0], 'sub': g[1], 'state': 'pending'} for g in groups]

    current_idx = seq.index(case.current_stage)
    steps = []
    for label, sub, stage_names in groups:
        group_last_idx = max(seq.index(s) for s in stage_names)
        if current_idx > group_last_idx:
            state = 'completed'
        elif case.current_stage in stage_names:
            state = 'current'
        else:
            state = 'pending'
        steps.append({'label': label, 'sub': sub, 'state': state})
    return steps


@login_required
def dashboard_view(request):
    from procurement.models import ProcurementCase, CaseStageHistory
    from requirements_mgmt.models import RequirementRequest

    role = request.user.role

    # Requirement Summary counts (Draft / Submitted / Approved / Rejected).
    # "Approved" = case has moved past the Approval stage or later.
    # "Rejected" = case has at least one RETURN entry in its history.
    draft_count = RequirementRequest.objects.filter(status='DRAFT').count()
    submitted_count = RequirementRequest.objects.filter(status='SUBMITTED').count()

    approved_stage_order = ProcurementCase.STAGE_SEQUENCE.index('APPROVAL')
    all_cases = ProcurementCase.objects.all()
    approved_count = sum(
        1 for c in all_cases
        if c.current_stage in ProcurementCase.STAGE_SEQUENCE
        and ProcurementCase.STAGE_SEQUENCE.index(c.current_stage) > approved_stage_order
    )
    rejected_count = CaseStageHistory.objects.filter(action='RETURN').values('case').distinct().count()

    pending_approvals = ProcurementCase.objects.filter(
        current_stage__in=['APPROVAL', 'EAS', 'SANCTION'], is_closed=False
    ).count()

    # Most recent open case, to drive the workflow-stepper visual.
    latest_case = ProcurementCase.objects.filter(is_closed=False).order_by('-created_at').first()
    workflow_steps = _build_workflow_steps(latest_case)

    recent_activity = CaseStageHistory.objects.select_related(
        'case', 'performed_by'
    ).order_by('-created_at')[:6]

    active_requirements = RequirementRequest.objects.select_related('unit', 'raised_by').order_by('-created_at')[:10]

    context = {
        'role': role,
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'pending_approvals': pending_approvals,
        'latest_case': latest_case,
        'workflow_steps': workflow_steps,
        'recent_activity': recent_activity,
        'active_requirements': active_requirements,
    }
    return render(request, 'authentication/dashboard.html', context)