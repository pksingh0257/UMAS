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


@login_required
def dashboard_view(request):
    from procurement.models import ProcurementCase, CaseStageHistory
    from requirements_mgmt.models import Requirement   # CHANGED: was RequirementRequest
    from masterdata.models import Unit, FundHead, ItemCategory
    from authentication.models import User

    role = request.user.role
    context = {'role': role}

    if role == 'ADMINISTRATOR':
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(status='ACTIVE').count()
        context['unit_count'] = Unit.objects.filter(is_active=True).count()
        context['fund_head_count'] = FundHead.objects.filter(is_active=True).count()
        context['item_category_count'] = ItemCategory.objects.filter(is_active=True).count()
        context['recent_activity'] = CaseStageHistory.objects.select_related(
            'case', 'performed_by'
        ).order_by('-created_at')[:10]

    elif role == 'HEAD_CLERK':
        # CHANGED: RequirementRequest -> Requirement. That model has no
        # `unit` field anymore (flattened model dropped it), so the
        # dashboard template needs a small update too — see below.
        context['my_requests'] = Requirement.objects.filter(
            raised_by=request.user
        ).order_by('-created_at')[:10]

    elif role == 'ACCOUNTS_CLERK':
        context['pending_cases'] = ProcurementCase.objects.filter(
            current_stage__in=CLERK_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['recent_activity'] = CaseStageHistory.objects.filter(
            performed_by=request.user
        ).order_by('-created_at')[:10]

    elif role == 'ACCOUNTS_JCO':
        context['pending_cases'] = ProcurementCase.objects.filter(
            current_stage__in=JCO_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['recent_activity'] = CaseStageHistory.objects.order_by('-created_at')[:10]

    elif role == 'ACCOUNTS_OFFICER':
        context['pending_cases'] = ProcurementCase.objects.filter(
            current_stage__in=OFFICER_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['fund_heads'] = FundHead.objects.filter(is_active=True)

    elif role == 'CFA':
        context['pending_cases'] = ProcurementCase.objects.filter(
            current_stage__in=CFA_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['recent_activity'] = CaseStageHistory.objects.filter(
            performed_by=request.user
        ).order_by('-created_at')[:10]

    return render(request, 'authentication/dashboard.html', context)