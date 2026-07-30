from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FundEntryForm
from .models import FundEntry
from .services import (
    create_fund_entry,
    decide_fund_entry,
    submit_fund_entry,
)

@login_required
def fund_entry_list(request):
    """
    Account Officer sees their own entries.
    CFA sees entries requiring CFA action.
    """

    role = getattr(request.user, "role", None)

    if role == "ACCOUNTS_OFFICER":
        entries = FundEntry.objects.filter(
            created_by=request.user
        ).select_related(
            "financial_year",
            "sub_head",
            "sub_head__fund_head",
            "cfa_acted_by",
        )

    elif role == "CFA":
        entries = FundEntry.objects.filter(
            status="PENDING_CFA"
        ).select_related(
            "financial_year",
            "sub_head",
            "sub_head__fund_head",
            "created_by",
        )

    else:
        raise PermissionDenied(
            "You are not authorised to access Fund Entries."
        )

    context = {
        "entries": entries,
        "role": role,
    }

    return render(
        request,
        "finance/fund_entry_list.html",
        context,
    )
@login_required
def fund_entry_create(request):
    """
    Allow only Account Officer to create a Draft Fund Entry.
    """

    if getattr(request.user, "role", None) != "ACCOUNTS_OFFICER":
        raise PermissionDenied(
            "Only the Account Officer can create Fund Entries."
        )

    if request.method == "POST":
        form = FundEntryForm(request.POST)

        if form.is_valid():
            try:
                entry = create_fund_entry(
                    created_by=request.user,
                    **form.cleaned_data,
                )

                messages.success(
                    request,
                    "Fund Entry created successfully as Draft.",
                )

                return redirect(
                    "finance:fund-entry-detail",
                    pk=entry.pk,
                )

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = FundEntryForm()

    return render(
        request,
        "finance/fund_entry_form.html",
        {"form": form},
    )

@login_required
def fund_entry_detail(request, pk):
    """
    Display one Fund Entry according to the logged-in user's role.
    """

    role = getattr(request.user, "role", None)

    queryset = FundEntry.objects.select_related(
        "financial_year",
        "sub_head",
        "sub_head__fund_head",
        "created_by",
        "modified_by",
        "cfa_acted_by",
    )

    if role == "ACCOUNTS_OFFICER":
        entry = get_object_or_404(
            queryset,
            pk=pk,
            created_by=request.user,
        )

    elif role == "CFA":
        entry = get_object_or_404(
            queryset,
            pk=pk,
        )

    else:
        raise PermissionDenied(
            "You are not authorised to view this Fund Entry."
        )

    return render(
        request,
        "finance/fund_entry_detail.html",
        {
            "entry": entry,
            "role": role,
        },
    )

@login_required
def fund_entry_detail(request, pk):
    """
    Display one Fund Entry according to the logged-in user's role.
    """

    role = getattr(request.user, "role", None)

    queryset = FundEntry.objects.select_related(
        "financial_year",
        "sub_head",
        "sub_head__fund_head",
        "created_by",
        "modified_by",
        "cfa_acted_by",
    )

    if role == "ACCOUNTS_OFFICER":
        entry = get_object_or_404(
            queryset,
            pk=pk,
            created_by=request.user,
        )

    elif role == "CFA":
        entry = get_object_or_404(
            queryset,
            pk=pk,
        )

    else:
        raise PermissionDenied(
            "You are not authorised to view this Fund Entry."
        )

    return render(
        request,
        "finance/fund_entry_detail.html",
        {
            "entry": entry,
            "role": role,
        },
    )

@login_required
@require_POST
def fund_entry_submit(request, pk):
    """
    Account Officer submits a Draft or Returned entry to CFA.
    """

    if getattr(request.user, "role", None) != "ACCOUNTS_OFFICER":
        raise PermissionDenied(
            "Only the Account Officer can submit Fund Entries."
        )

    entry = get_object_or_404(
        FundEntry,
        pk=pk,
        created_by=request.user,
    )

    try:
        submit_fund_entry(
            entry_id=entry.pk,
            submitted_by=request.user,
        )

        messages.success(
            request,
            "Fund Entry submitted to CFA successfully.",
        )

    except ValidationError as error:
        messages.error(
            request,
            "; ".join(error.messages),
        )

    return redirect(
        "finance:fund-entry-detail",
        pk=entry.pk,
    )

@login_required
@require_POST
def fund_entry_cfa_decision(request, pk):
    """
    CFA approves, returns or rejects a pending Fund Entry.
    """

    if getattr(request.user, "role", None) != "CFA":
        raise PermissionDenied(
            "Only CFA can decide a Fund Entry."
        )

    entry = get_object_or_404(
        FundEntry,
        pk=pk,
        status="PENDING_CFA",
    )

    decision = request.POST.get(
        "decision",
        "",
    ).strip().upper()

    remarks = request.POST.get(
        "remarks",
        "",
    ).strip()

    try:
        decide_fund_entry(
            entry_id=entry.pk,
            decided_by=request.user,
            decision=decision,
            remarks=remarks,
        )

        if decision == "APPROVED":
            messages.success(
                request,
                "Fund Entry approved and posted to the ledger.",
            )

        elif decision == "RETURNED":
            messages.warning(
                request,
                "Fund Entry returned to the Account Officer.",
            )

        elif decision == "REJECTED":
            messages.error(
                request,
                "Fund Entry rejected.",
            )

    except ValidationError as error:
        messages.error(
            request,
            "; ".join(error.messages),
        )

    return redirect(
        "finance:fund-entry-list",
    )