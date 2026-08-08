from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


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

# "Income" transaction types per Section 6 ("Income increases balance") —
# OPENING and CREDIT are the two entry types that add money in; the
# reversal/adjustment types are corrections, not income, so they're
# deliberately excluded from the dashboard income charts.
FUND_INCOME_TYPES = ['OPENING', 'CREDIT']
FUND_EXPENDITURE_TYPES = ['EXPENDITURE']


def _stage_breakdown(queryset, model_field_name='current_stage'):
    """
    Given a queryset of ProcurementCase (or any model with a choices field),
    returns (labels, data) using the human-readable choice labels, ready
    for json_script + Chart.js.
    """
    counts = (
        queryset
        .values(model_field_name)
        .annotate(c=Count('id'))
        .order_by('-c')
    )
    field = queryset.model._meta.get_field(model_field_name)
    choice_map = dict(field.choices) if field.choices else {}

    labels = [choice_map.get(row[model_field_name], row[model_field_name]) for row in counts]
    data = [row['c'] for row in counts]
    return labels, data


def _avg_turnaround_days(user):
    """
    Rough average turnaround: mean number of days between consecutive
    CaseStageHistory entries performed by this user over the last 30 days.
    Returns a number (0 if there isn't enough data yet).
    """
    from procurement.models import CaseStageHistory

    thirty_days_ago = timezone.now() - timedelta(days=30)
    entries = list(
        CaseStageHistory.objects.filter(
            performed_by=user, created_at__gte=thirty_days_ago
        ).order_by('created_at').values_list('created_at', flat=True)
    )
    if len(entries) < 2:
        return 0

    diffs = [(entries[i] - entries[i - 1]).total_seconds() for i in range(1, len(entries))]
    avg_seconds = sum(diffs) / len(diffs)
    return round(avg_seconds / 86400, 1)


@login_required
def dashboard_view(request):
    from procurement.models import ProcurementCase, CaseStageHistory
    from requirements_mgmt.models import Requirement
    from masterdata.models import FundHead, ItemCategory
    from authentication.models import User
    from finance.models import FundEntry, FundTransaction

    role = request.user.role
    context = {'role': role}

    if role == 'ADMINISTRATOR':
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(status='ACTIVE').count()
        context['fund_head_count'] = FundHead.objects.filter(is_active=True).count()
        context['item_category_count'] = ItemCategory.objects.filter(is_active=True).count()
        context['recent_activity'] = CaseStageHistory.objects.select_related(
            'case', 'performed_by'
        ).order_by('-created_at')[:10]

        # --- KPI / chart data ---

        open_cases = ProcurementCase.objects.filter(is_closed=False)
        context['open_case_count'] = open_cases.count()
        context['closed_case_count'] = ProcurementCase.objects.filter(is_closed=True).count()

        # Core requirement-workflow KPI for the administrator dashboard.
        # Anything not yet approved still requires workflow attention.
        context['pending_requirements'] = Requirement.objects.exclude(
            workflow_status='APPROVED'
        ).count()

        stage_labels, stage_data = _stage_breakdown(open_cases, 'current_stage')
        context['cases_by_stage_labels'] = stage_labels
        context['cases_by_stage_data'] = stage_data

        role_counts = (
            User.objects.values('role')
            .annotate(c=Count('id'))
            .order_by('-c')
        )
        role_field = User._meta.get_field('role')
        role_choice_map = dict(role_field.choices) if role_field.choices else {}
        context['users_by_role_labels'] = [
            role_choice_map.get(r['role'], r['role']) for r in role_counts
        ]
        context['users_by_role_data'] = [r['c'] for r in role_counts]

        # System-wide fund snapshot for the admin summary strip
        context['pending_fund_entries_system'] = FundEntry.objects.filter(
            status='PENDING_CFA'
        ).count()

        # --- Fund income: Fund Head income, Sub Head income, income
        # share pie, and total income / utilization for the progress bar.
        # Only APPROVED entries post a FundTransaction (see
        # FundEntry.create_ledger_transaction), so this only counts money
        # that has actually been approved onto the ledger — not drafts or
        # entries still pending CFA.
        income_qs = FundTransaction.objects.filter(
            transaction_type__in=FUND_INCOME_TYPES, is_reversed=False
        )

        # Overall Fund Head totals are retained for the pie chart and summary data.
        fh_income = (
            income_qs.values('sub_head__fund_head__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        context['fund_head_income_labels'] = [
            row['sub_head__fund_head__name'] for row in fh_income
        ]
        context['fund_head_income_data'] = [
            float(row['total']) for row in fh_income
        ]

        # -------------------------------------------------------------
        # Fund Head -> Sub Head income distribution
        #
        # Each Fund Head gets its own graph. This prevents Sub Heads
        # belonging to different Fund Heads from being mixed together
        # on one x-axis. Only the Sub Head code is displayed (for example
        # BRK-DMG, SPORT, ATG) — no "Sub-Head:" prefix is added.
        # -------------------------------------------------------------
        fund_income_groups = []
        fund_head_color_cycle = [
            '#C62828',  # red
            '#1E88E5',  # blue
            '#4CAF50',  # green
            '#E3A008',  # amber
            '#8E24AA',  # purple
            '#00897B',  # teal
        ]

        for index, fund_head in enumerate(
            FundHead.objects.filter(is_active=True).order_by('name')
        ):
            sub_income = (
                income_qs
                .filter(sub_head__fund_head=fund_head)
                .values('sub_head__code')
                .annotate(total=Sum('amount'))
                .order_by('-total')
            )

            labels = [row['sub_head__code'] for row in sub_income]
            data = [float(row['total']) for row in sub_income]

            # Keep the two standard UAMS Fund Head colours consistent
            # when those names are present; otherwise continue through the
            # neutral colour cycle for any additional Fund Heads.
            fund_name_lower = fund_head.name.lower()
            if 'regimental' in fund_name_lower:
                accent = '#C62828'
            elif 'public' in fund_name_lower:
                accent = '#1E88E5'
            else:
                accent = fund_head_color_cycle[index % len(fund_head_color_cycle)]

            fund_income_groups.append({
                'name': fund_head.name,
                'labels': labels,
                'data': data,
                'accent': accent,
            })

        context['fund_income_groups'] = fund_income_groups

        # Pie uses the same Fund Head totals — income share by Fund Head.
        context['fund_income_pie_labels'] = context['fund_head_income_labels']
        context['fund_income_pie_data'] = context['fund_head_income_data']

        total_income = income_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_expenditure = FundTransaction.objects.filter(
            transaction_type__in=FUND_EXPENDITURE_TYPES, is_reversed=False
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        context['total_fund_income'] = total_income
        context['total_fund_expenditure'] = total_expenditure
        context['available_fund_balance'] = total_income - total_expenditure
        context['fund_utilization_pct'] = (
            round(float(total_expenditure) / float(total_income) * 100, 1)
            if total_income else 0
        )

    elif role == 'HEAD_CLERK':
        my_requests_qs = Requirement.objects.filter(raised_by=request.user)
        context['my_requests'] = my_requests_qs.order_by('-created_at')[:10]

        # --- KPI / chart data ---
        context['total_requests'] = my_requests_qs.count()

        # simple_approval_status is a Python @property, not a DB field —
        # group by the real workflow_status column instead, then collapse
        # the 6 workflow states into the same 3 buckets the property uses.
        workflow_counts = (
            my_requests_qs
            .values('workflow_status')
            .annotate(c=Count('id'))
            .order_by('-c')
        )
        workflow_counts_map = {row['workflow_status']: row['c'] for row in workflow_counts}

        approved_count = workflow_counts_map.get('APPROVED', 0)
        declined_count = (
            workflow_counts_map.get('AO_DENIED', 0)
            + workflow_counts_map.get('CFA_DENIED', 0)
        )
        pending_count = (
            workflow_counts_map.get('DRAFT', 0)
            + workflow_counts_map.get('PENDING_AO', 0)
            + workflow_counts_map.get('PENDING_CFA', 0)
        )

        context['pending_requests'] = pending_count
        context['approved_requests'] = approved_count
        context['rejected_requests'] = declined_count

        context['request_status_labels'] = ['Pending', 'Approved', 'Declined']
        context['request_status_data'] = [pending_count, approved_count, declined_count]

    elif role == 'ACCOUNTS_CLERK':
        pending_qs = ProcurementCase.objects.filter(
            current_stage__in=CLERK_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['pending_cases'] = pending_qs
        context['recent_activity'] = CaseStageHistory.objects.filter(
            performed_by=request.user
        ).order_by('-created_at')[:10]

        stage_labels, stage_data = _stage_breakdown(pending_qs, 'current_stage')
        context['my_cases_by_stage_labels'] = stage_labels
        context['my_cases_by_stage_data'] = stage_data

        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['processed_last_30d'] = CaseStageHistory.objects.filter(
            performed_by=request.user, created_at__gte=thirty_days_ago
        ).count()
        context['avg_turnaround_days'] = _avg_turnaround_days(request.user)

    elif role == 'ACCOUNTS_JCO':
        pending_qs = ProcurementCase.objects.filter(
            current_stage__in=JCO_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['pending_cases'] = pending_qs
        context['recent_activity'] = CaseStageHistory.objects.order_by('-created_at')[:10]

        stage_labels, stage_data = _stage_breakdown(pending_qs, 'current_stage')
        context['my_cases_by_stage_labels'] = stage_labels
        context['my_cases_by_stage_data'] = stage_data

        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['processed_last_30d'] = CaseStageHistory.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        context['avg_turnaround_days'] = _avg_turnaround_days(request.user)

    elif role == 'ACCOUNTS_OFFICER':
        pending_qs = ProcurementCase.objects.filter(
            current_stage__in=OFFICER_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['pending_cases'] = pending_qs
        context['fund_heads'] = FundHead.objects.filter(is_active=True)

        stage_labels, stage_data = _stage_breakdown(pending_qs, 'current_stage')
        context['my_cases_by_stage_labels'] = stage_labels
        context['my_cases_by_stage_data'] = stage_data

        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['processed_last_30d'] = CaseStageHistory.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        context['avg_turnaround_days'] = _avg_turnaround_days(request.user)

        # --- Fund Entries this officer has submitted ---
        my_fund_entries_qs = FundEntry.objects.filter(created_by=request.user)
        context['total_fund_entries'] = my_fund_entries_qs.count()

        fund_status_counts = (
            my_fund_entries_qs
            .values('status')
            .annotate(c=Count('id'))
            .order_by('-c')
        )
        fund_status_field = FundEntry._meta.get_field('status')
        fund_status_choice_map = dict(fund_status_field.choices) if fund_status_field.choices else {}

        context['fund_entry_status_labels'] = [
            fund_status_choice_map.get(row['status'], row['status'])
            for row in fund_status_counts
        ]
        context['fund_entry_status_data'] = [row['c'] for row in fund_status_counts]

    elif role == 'CFA':
        pending_qs = ProcurementCase.objects.filter(
            current_stage__in=CFA_STAGES, is_closed=False
        ).select_related('requirement_item')
        context['pending_cases'] = pending_qs
        context['recent_activity'] = CaseStageHistory.objects.filter(
            performed_by=request.user
        ).order_by('-created_at')[:10]

        stage_labels, stage_data = _stage_breakdown(pending_qs, 'current_stage')
        context['my_cases_by_stage_labels'] = stage_labels
        context['my_cases_by_stage_data'] = stage_data

        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['processed_last_30d'] = CaseStageHistory.objects.filter(
            performed_by=request.user, created_at__gte=thirty_days_ago
        ).count()
        context['avg_turnaround_days'] = _avg_turnaround_days(request.user)

        # --- Fund Entries pending CFA approval ---
        pending_fund_entries_qs = FundEntry.objects.filter(
            status='PENDING_CFA'
        ).select_related('sub_head', 'financial_year')
        context['pending_fund_entries'] = pending_fund_entries_qs[:10]
        context['pending_fund_entries_count'] = pending_fund_entries_qs.count()

    return render(request, 'authentication/dashboard.html', context)