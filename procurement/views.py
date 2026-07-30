from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from requirements_mgmt.models import Requirement
from .models import ProcurementCase, NotingSheet, EAS
from .forms import (
    CaseStageDataForm, ReturnCaseForm, NotingSheetForm,
    NotingCFADecisionForm, EASForm, EASCFADecisionForm,
)


def render_pdf(template_name, context, filename):
    """
    Renders a Django template to a downloadable PDF using xhtml2pdf.
    Kept deliberately simple (no external CSS files, no flex/grid) since
    xhtml2pdf's CSS support is limited to CSS 2.1 — the PDF templates use
    plain tables/inline styles rather than reusing style.css.
    """
    html = render_to_string(template_name, context)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("There was an error generating the PDF.", status=500)
    return response


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
def noting_sheet_submit_for_approval(request, pk):
    noting_sheet = get_object_or_404(NotingSheet, pk=pk)
    if noting_sheet.created_by != request.user:
        messages.error(request, "You can only submit noting sheets you created.")
        return redirect("procurement_dashboard")

    if request.method == "POST":
        try:
            noting_sheet.submit_for_approval()
            messages.success(request, f"{noting_sheet.noting_id} sent for CFA approval.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect("noting_sheet_detail", pk=pk)


@login_required
def noting_sheet_detail(request, pk):
    """CFA-only approval — Account Officer review has been removed from
    this flow (see NotingSheet.submit_for_approval in models.py)."""
    noting_sheet = get_object_or_404(NotingSheet, pk=pk)
    role = request.user.role

    cfa_form = None
    can_act_as_cfa = role == "CFA" and noting_sheet.workflow_status == "PENDING_CFA"

    if request.method == "POST":
        if can_act_as_cfa and "cfa_submit" in request.POST:
            cfa_form = NotingCFADecisionForm(request.POST)
            if cfa_form.is_valid():
                noting_sheet.cfa_decide(
                    user=request.user,
                    decision=cfa_form.cleaned_data["cfa_status"],
                    remarks=cfa_form.cleaned_data["cfa_remarks"],
                )
                messages.success(request, "CFA decision recorded.")
                return redirect("noting_sheet_detail", pk=pk)

    if cfa_form is None and can_act_as_cfa:
        cfa_form = NotingCFADecisionForm(initial={"cfa_status": "PENDING"})

    return render(request, "procurement/noting_sheet_detail.html", {
        "noting_sheet": noting_sheet,
        "role": role,
        "active_nav": "procurement",
        "cfa_form": cfa_form,
        "can_submit": noting_sheet.is_editable and noting_sheet.created_by == request.user,
    })

# ============================================================
# NEW VIEWS — EAS workflow
# ============================================================

@login_required
def eas_create(request, noting_sheet_pk):
    """
    "Create EAS" — only reachable once the linked Noting Sheet is fully
    CFA-approved (workflow_status == "APPROVED"), matching the mockup
    where the button only appears at that point.

    Submitting the form both saves the EAS AND sends it straight to AO
    review in one step — the mockup shows a single "Send For Approval"
    button, not a separate save-then-submit flow.
    """
    noting_sheet = get_object_or_404(NotingSheet, pk=noting_sheet_pk, workflow_status="APPROVED")

    if hasattr(noting_sheet, "eas"):
        messages.info(request, "An EAS already exists for this noting sheet.")
        return redirect("eas_detail", pk=noting_sheet.eas.pk)

    if request.method == "POST":
        form = EASForm(request.POST)
        if form.is_valid():
            eas = form.save(commit=False)
            eas.noting_sheet = noting_sheet
            eas.created_by = request.user
            eas.save()
            eas.submit_for_approval()
            messages.success(request, "EAS created and sent for CFA approval.")
            return redirect("eas_detail", pk=eas.pk)
    else:
        form = EASForm()

    return render(request, "procurement/eas_form.html", {
        "form": form,
        "noting_sheet": noting_sheet,
        "role": request.user.role,
        "active_nav": "procurement",
    })


@login_required
def eas_edit(request, pk):
    """
    Only reachable while editable (DRAFT / CFA_DENIED), and only by the
    person who created it — same convention used for Requirement and
    NotingSheet. Resubmitting goes straight back to CFA (CFA-only flow).
    """
    eas = get_object_or_404(EAS, pk=pk)
    if not eas.is_editable or eas.created_by != request.user:
        messages.error(request, "This EAS can't be edited right now.")
        return redirect("eas_detail", pk=pk)

    if request.method == "POST":
        form = EASForm(request.POST, instance=eas)
        if form.is_valid():
            form.save()
            eas.submit_for_approval()
            messages.success(request, "EAS updated and re-sent for CFA approval.")
            return redirect("eas_detail", pk=pk)
    else:
        form = EASForm(instance=eas)

    return render(request, "procurement/eas_form.html", {
        "form": form,
        "noting_sheet": eas.noting_sheet,
        "eas": eas,
        "role": request.user.role,
        "active_nav": "procurement",
    })


@login_required
def eas_detail(request, pk):
    """CFA-only approval — Account Officer review has been removed from
    this flow (see EAS.submit_for_approval in models.py)."""
    eas = get_object_or_404(EAS, pk=pk)
    role = request.user.role

    cfa_form = None
    can_act_as_cfa = role == "CFA" and eas.workflow_status == "PENDING_CFA"

    if request.method == "POST":
        if can_act_as_cfa and "cfa_submit" in request.POST:
            cfa_form = EASCFADecisionForm(request.POST)
            if cfa_form.is_valid():
                eas.cfa_decide(
                    user=request.user,
                    decision=cfa_form.cleaned_data["cfa_status"],
                    remarks=cfa_form.cleaned_data["cfa_remarks"],
                )
                messages.success(request, "CFA decision recorded.")
                return redirect("eas_detail", pk=pk)

    if cfa_form is None and can_act_as_cfa:
        cfa_form = EASCFADecisionForm(initial={"cfa_status": "PENDING"})

    return render(request, "procurement/eas_detail.html", {
        "eas": eas,
        "noting_sheet": eas.noting_sheet,
        "role": role,
        "active_nav": "procurement",
        "cfa_form": cfa_form,
        "can_edit": eas.is_editable and eas.created_by == request.user,
    })


# ============================================================
# NEW VIEWS — PDF downloads
# ============================================================

@login_required
def noting_sheet_download_pdf(request, pk):
    noting_sheet = get_object_or_404(NotingSheet, pk=pk)
    if noting_sheet.workflow_status != "APPROVED":
        messages.error(request, "This Noting Sheet can only be downloaded once it's fully approved.")
        return redirect("noting_sheet_detail", pk=pk)
    return render_pdf(
        "procurement/pdf/noting_sheet_pdf.html",
        {"noting_sheet": noting_sheet},
        f"{noting_sheet.noting_id}.pdf",
    )


@login_required
def eas_download_pdf(request, pk):
    eas = get_object_or_404(EAS, pk=pk)
    if eas.workflow_status != "APPROVED":
        messages.error(request, "This EAS can only be downloaded once it's fully approved.")
        return redirect("eas_detail", pk=pk)
    return render_pdf(
        "procurement/pdf/eas_pdf.html",
        {"eas": eas, "noting_sheet": eas.noting_sheet},
        f"{eas.eas_id or eas.pk}.pdf",
    )