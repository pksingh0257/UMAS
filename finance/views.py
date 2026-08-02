from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from masterdata.models import FundHead, SubHead

from .forms import FundEntryForm
from .models import FundEntry, FundTransaction
from .services import (
    create_fund_entry,
    decide_fund_entry,
    submit_fund_entry,
)

# ---------------------------------------------------------------------
# Ledger aggregation helpers
#
# FundTransaction.credit_amount / debit_amount are Python @property
# methods (see finance/models.py) — they cannot be aggregated directly
# in the DB. These helpers replicate the exact same classification at
# the query level so balances are computed straight from the ledger,
# never from a stored/mock balance field.
# ---------------------------------------------------------------------

DEC_FIELD = DecimalField(max_digits=15, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=DEC_FIELD)

CREDIT_TYPES = [
    "OPENING",
    "CREDIT",
    "EXPENDITURE_REVERSAL",
    "ADJUSTMENT_CREDIT",
]

DEBIT_TYPES = [
    "EXPENDITURE",
    "CREDIT_REVERSAL",
    "ADJUSTMENT_DEBIT",
]


def _balance_summary(transaction_qs):
    """
    Given any FundTransaction queryset, returns a dict with:
        total_credit        - sum of all credit-classified transactions
        total_expenditure   - sum of actual EXPENDITURE transactions only
        total_debit         - sum of all debit-classified transactions
        available_balance   - total_credit - total_debit
    """

    totals = transaction_qs.aggregate(
        total_credit=Coalesce(
            Sum("amount", filter=Q(transaction_type__in=CREDIT_TYPES)),
            ZERO,
        ),
        total_expenditure=Coalesce(
            Sum("amount", filter=Q(transaction_type="EXPENDITURE")),
            ZERO,
        ),
        total_debit=Coalesce(
            Sum("amount", filter=Q(transaction_type__in=DEBIT_TYPES)),
            ZERO,
        ),
    )

    totals["available_balance"] = (
        totals["total_credit"] - totals["total_debit"]
    )

    return totals


FUND_ROLES = {
    "ACCOUNTS_OFFICER",
    "ADMINISTRATOR",
    "ACCOUNTS_CLERK",
    "HEAD_CLERK",
    "CFA",
}


# ---------------------------------------------------------------------
# Page 1 — Funds Dashboard  ( /finance/funds/ )
# ---------------------------------------------------------------------

@login_required
def fund_dashboard(request):
    role = getattr(request.user, "role", None)

    if role not in FUND_ROLES:
        raise PermissionDenied(
            "You are not authorised to access Funds."
        )

    fund_heads = []

    for fh in FundHead.objects.filter(is_active=True).order_by("name"):
        txns = FundTransaction.objects.filter(sub_head__fund_head=fh)
        summary = _balance_summary(txns)
        fund_heads.append({"fund_head": fh, **summary})

    # Reuse the same entry-visibility rules as the existing
    # fund_entry_list view for the "Fund Entries" table on this page.
    if role == "ACCOUNTS_OFFICER":
        entries = FundEntry.objects.filter(
            created_by=request.user
        ).select_related(
            "financial_year", "sub_head", "sub_head__fund_head", "cfa_acted_by",
        )

    elif role == "CFA":
        entries = FundEntry.objects.filter(
            status="PENDING_CFA"
        ).select_related(
            "financial_year", "sub_head", "sub_head__fund_head", "created_by",
        )

    else:
        entries = FundEntry.objects.select_related(
            "financial_year", "sub_head", "sub_head__fund_head",
            "created_by", "cfa_acted_by",
        )

    context = {
        "fund_heads": fund_heads,
        "entries": entries[:10],
        "role": role,
    }

    return render(request, "finance/fund_dashboard.html", context)


# ---------------------------------------------------------------------
# Page 2 — Fund Head Detail  ( /finance/funds/<uuid:pk>/ )
# Works for both Public Fund and Regimental Fund - same template,
# driven entirely by which FundHead pk is in the URL.
# ---------------------------------------------------------------------

@login_required
def fund_head_detail(request, pk):
    role = getattr(request.user, "role", None)

    if role not in FUND_ROLES:
        raise PermissionDenied(
            "You are not authorised to access Funds."
        )

    fund_head = get_object_or_404(FundHead, pk=pk)

    fund_txns = FundTransaction.objects.filter(sub_head__fund_head=fund_head)
    summary = _balance_summary(fund_txns)

    sub_heads = []

    for sh in fund_head.sub_heads.filter(is_active=True).order_by("name"):
        sh_txns = FundTransaction.objects.filter(sub_head=sh)
        sh_summary = _balance_summary(sh_txns)
        sub_heads.append({"sub_head": sh, **sh_summary})

    recent_transactions = fund_txns.select_related("sub_head").order_by(
        "-transaction_date", "-created_at"
    )[:10]

    context = {
        "fund_head": fund_head,
        "summary": summary,
        "sub_heads": sub_heads,
        "recent_transactions": recent_transactions,
        "role": role,
    }

    return render(request, "finance/fund_head_detail.html", context)


# ---------------------------------------------------------------------
# Page 3 — Sub Head Detail  ( /finance/funds/sub-head/<uuid:pk>/ )
# ---------------------------------------------------------------------

@login_required
def sub_head_detail(request, pk):
    role = getattr(request.user, "role", None)

    if role not in FUND_ROLES:
        raise PermissionDenied(
            "You are not authorised to access Funds."
        )

    sub_head = get_object_or_404(
        SubHead.objects.select_related("fund_head"), pk=pk
    )

    txns = FundTransaction.objects.filter(sub_head=sub_head)
    summary = _balance_summary(txns)
    transactions = txns.order_by("-transaction_date", "-created_at")

    context = {
        "sub_head": sub_head,
        "summary": summary,
        "transactions": transactions,
        "role": role,
    }

    return render(request, "finance/sub_head_detail.html", context)


# ---------------------------------------------------------------------
# Existing Fund Entry views (unchanged)
# ---------------------------------------------------------------------

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
                entry = create_fund_entry(created_by=request.user, **form.cleaned_data)

                messages.success(request, "Fund Entry created successfully as Draft.")

                return redirect("finance:fund-entry-detail", pk=entry.pk)

            except ValidationError as error:
                form.add_error(None, error)

    else:
        form = FundEntryForm()

    return render(
        request,
        "finance/fund_entry_form.html",
        {
            "form": form,
            "role": request.user.role,
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