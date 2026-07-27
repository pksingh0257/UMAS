from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from requirements_mgmt.models import Requirement
from .models import ProcurementCase, NotingSheet
from .forms import CaseStageDataForm, ReturnCaseForm, NotingSheetForm, NotingAODecisionForm, NotingCFADecisionForm


# ============================================================
# EXISTING VIEWS — unchanged from what you had
# ============================================================

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


# ============================================================
# NEW VIEWS — Noting Sheet workflow
# ============================================================

@login_required
def procurement_dashboard(request):
    """New landing page for the "Procurement" sidebar link."""
    noting_sheets = NotingSheet.objects.select_related("requirement").order_by("-created_at")

    context = {
        "noting_sheets": noting_sheets,
        "total_count": noting_sheets.count(),
        "pending_count": noting_sheets.exclude(workflow_status="APPROVED").count(),
        "completed_count": noting_sheets.filter(workflow_status="APPROVED").count(),
        "role": request.user.role,
        "active_nav": "procurement",
    }
    return render(request, "procurement/procurement_dashboard.html", context)


@login_required
def procurement_select(request):
    """
    Step 1: dropdown of APPROVED requirements that don't already have a
    Noting Sheet. Selecting one (GET ?requirement=<pk>) shows its details
    below plus a "Create Noting Sheet" button, matching your mockup.
    """
    eligible = Requirement.objects.filter(
        workflow_status="APPROVED", noting_sheet__isnull=True
    ).order_by("-created_at")

    selected = None
    requirement_id = request.GET.get("requirement")
    if requirement_id:
        selected = get_object_or_404(Requirement, pk=requirement_id, workflow_status="APPROVED")

    return render(request, "procurement/procurement_select.html", {
        "eligible": eligible,
        "selected": selected,
        "role": request.user.role,
        "active_nav": "procurement",
    })


@login_required
def noting_sheet_create(request, requirement_pk):
    requirement = get_object_or_404(Requirement, pk=requirement_pk, workflow_status="APPROVED")

    if hasattr(requirement, "noting_sheet"):
        messages.info(request, "A Noting Sheet already exists for this requirement.")
        return redirect("noting_sheet_detail", pk=requirement.noting_sheet.pk)

    if request.method == "POST":
        form = NotingSheetForm(request.POST)
        if form.is_valid():
            noting_sheet = form.save(commit=False)
            noting_sheet.requirement = requirement
            noting_sheet.created_by = request.user
            noting_sheet.save()
            messages.success(request, f"{noting_sheet.noting_id} created.")
            return redirect("noting_sheet_detail", pk=noting_sheet.pk)
    else:
        form = NotingSheetForm()

    return render(request, "procurement/noting_sheet_form.html", {
        "form": form,
        "requirement": requirement,
        "role": request.user.role,
        "active_nav": "procurement",
    })


@login_required
def noting_sheet_submit_to_ao(request, pk):
    noting_sheet = get_object_or_404(NotingSheet, pk=pk)
    if noting_sheet.created_by != request.user:
        messages.error(request, "You can only submit noting sheets you created.")
        return redirect("procurement_dashboard")

    if request.method == "POST":
        try:
            noting_sheet.submit_to_ao()
            messages.success(request, f"{noting_sheet.noting_id} sent for Account Officer approval.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect("noting_sheet_detail", pk=pk)


@login_required
def noting_sheet_detail(request, pk):
    noting_sheet = get_object_or_404(NotingSheet, pk=pk)
    role = request.user.role

    ao_form = None
    cfa_form = None
    can_act_as_ao = role == "ACCOUNTS_OFFICER" and noting_sheet.workflow_status == "PENDING_AO"
    can_act_as_cfa = role == "CFA" and noting_sheet.workflow_status == "PENDING_CFA"

    if request.method == "POST":
        if can_act_as_ao and "ao_submit" in request.POST:
            ao_form = NotingAODecisionForm(request.POST)
            if ao_form.is_valid():
                noting_sheet.ao_decide(
                    user=request.user,
                    decision=ao_form.cleaned_data["ao_status"],
                    remarks=ao_form.cleaned_data["ao_remarks"],
                )
                messages.success(request, "Account Officer decision recorded.")
                return redirect("noting_sheet_detail", pk=pk)

        elif can_act_as_cfa and "cfa_submit" in request.POST:
            cfa_form = NotingCFADecisionForm(request.POST)
            if cfa_form.is_valid():
                noting_sheet.cfa_decide(
                    user=request.user,
                    decision=cfa_form.cleaned_data["cfa_status"],
                    remarks=cfa_form.cleaned_data["cfa_remarks"],
                )
                messages.success(request, "CFA decision recorded.")
                return redirect("noting_sheet_detail", pk=pk)

    if ao_form is None and can_act_as_ao:
        ao_form = NotingAODecisionForm(initial={"ao_status": "PENDING"})
    if cfa_form is None and can_act_as_cfa:
        cfa_form = NotingCFADecisionForm(initial={"cfa_status": "PENDING"})

    return render(request, "procurement/noting_sheet_detail.html", {
        "noting_sheet": noting_sheet,
        "role": role,
        "active_nav": "procurement",
        "ao_form": ao_form,
        "cfa_form": cfa_form,
        "can_submit": noting_sheet.is_editable and noting_sheet.created_by == request.user,
    })