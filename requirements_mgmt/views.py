from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Requirement
from .forms import RequirementForm, AODecisionForm, CFADecisionForm


@login_required
def requirement_list(request):
    """
    Everyone sees the same table (per your spec: 'display both approvals'),
    scoped a little by role so people aren't drowning in irrelevant rows.
    """
    role = request.user.role
    if role in ("HEAD_CLERK", "ACCOUNTS_CLERK"):
        requirements = Requirement.objects.filter(raised_by=request.user)
    else:
        requirements = Requirement.objects.all()

    return render(request, "requirements_mgmt/requirement_list.html", {
        "requirements": requirements,
        "role": role,
        "active_nav": "requirements",
    })


@login_required
def requirement_create(request):
    if request.method == "POST":
        form = RequirementForm(request.POST, request.FILES)
        if form.is_valid():
            requirement = form.save(commit=False)
            requirement.raised_by = request.user
            requirement.save()
            messages.success(request, f"{requirement.requirement_id} saved as draft.")
            return redirect("requirement_list")
    else:
        form = RequirementForm()

    return render(request, "requirements_mgmt/requirement_form.html", {
        "form": form,
        "role": request.user.role,
        "active_nav": "requirements",
        "is_edit": False,
    })


@login_required
def requirement_edit(request, pk):
    requirement = get_object_or_404(Requirement, pk=pk)

    if requirement.raised_by != request.user:
        messages.error(request, "You can only edit requirements you raised.")
        return redirect("requirement_list")

    if not requirement.is_editable:
        messages.error(request, "This requirement can't be edited in its current status.")
        return redirect("requirement_detail", pk=pk)

    if request.method == "POST":
        form = RequirementForm(request.POST, request.FILES, instance=requirement)
        if form.is_valid():
            form.save()
            messages.success(request, f"{requirement.requirement_id} updated.")
            return redirect("requirement_list")
    else:
        form = RequirementForm(instance=requirement)

    return render(request, "requirements_mgmt/requirement_form.html", {
        "form": form,
        "role": request.user.role,
        "active_nav": "requirements",
        "is_edit": True,
        "requirement": requirement,
    })


@login_required
def requirement_submit_to_ao(request, pk):
    """Clerk clicks 'Send for AO Approval' from the list or detail page."""
    requirement = get_object_or_404(Requirement, pk=pk)

    if requirement.raised_by != request.user:
        messages.error(request, "You can only submit requirements you raised.")
        return redirect("requirement_list")

    if request.method == "POST":
        try:
            requirement.submit_to_ao()
            messages.success(request, f"{requirement.requirement_id} sent for Account Officer approval.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect("requirement_list")


@login_required
def requirement_detail(request, pk):
    """
    Read-only view of everything, PLUS the AO decision form if this user
    is the Account Officer and it's awaiting AO review, or the CFA
    decision form if this user is CFA and it's awaiting CFA review.
    """
    requirement = get_object_or_404(Requirement, pk=pk)
    role = request.user.role

    ao_form = None
    cfa_form = None

    can_act_as_ao = role == "ACCOUNTS_OFFICER" and requirement.workflow_status == "PENDING_AO"
    can_act_as_cfa = role == "CFA" and requirement.workflow_status == "PENDING_CFA"

    if request.method == "POST":
        if can_act_as_ao and "ao_submit" in request.POST:
            ao_form = AODecisionForm(request.POST)
            if ao_form.is_valid():
                requirement.ao_decide(
                    user=request.user,
                    decision=ao_form.cleaned_data["ao_status"],
                    remarks=ao_form.cleaned_data["ao_remarks"],
                )
                messages.success(request, "Account Officer decision recorded.")
                return redirect("requirement_detail", pk=pk)

        elif can_act_as_cfa and "cfa_submit" in request.POST:
            cfa_form = CFADecisionForm(request.POST)
            if cfa_form.is_valid():
                requirement.cfa_decide(
                    user=request.user,
                    decision=cfa_form.cleaned_data["cfa_status"],
                    remarks=cfa_form.cleaned_data["cfa_remarks"],
                )
                messages.success(request, "CFA decision recorded.")
                return redirect("requirement_detail", pk=pk)

    if ao_form is None and can_act_as_ao:
        ao_form = AODecisionForm(initial={"ao_status": "PENDING"})
    if cfa_form is None and can_act_as_cfa:
        cfa_form = CFADecisionForm(initial={"cfa_status": "PENDING"})

    return render(request, "requirements_mgmt/requirement_detail.html", {
        "requirement": requirement,
        "role": role,
        "active_nav": "requirements",
        "ao_form": ao_form,
        "cfa_form": cfa_form,
        "can_edit": requirement.is_editable and requirement.raised_by == request.user,
        "can_submit": requirement.is_editable and requirement.raised_by == request.user,
    })