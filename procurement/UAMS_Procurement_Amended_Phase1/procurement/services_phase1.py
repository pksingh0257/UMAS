from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import FinancialYear, FundTransaction
from .models import GeMSurveyItem


DECIMAL_FIELD = DecimalField(max_digits=15, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=DECIMAL_FIELD)

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


def get_active_financial_year():
    financial_year = FinancialYear.objects.filter(
        is_active=True,
        is_closed=False,
    ).first()

    if financial_year is None:
        raise ValidationError(
            "No active financial year is configured."
        )

    return financial_year


def get_sub_head_fund_snapshot(sub_head, financial_year=None):
    """Return a ledger-derived snapshot for Noting Sheet creation."""

    financial_year = financial_year or get_active_financial_year()

    qs = FundTransaction.objects.filter(
        sub_head=sub_head,
        financial_year=financial_year,
        is_reversed=False,
    )

    totals = qs.aggregate(
        total_credit=Coalesce(
            Sum("amount", filter=Q(transaction_type__in=CREDIT_TYPES)),
            ZERO,
        ),
        total_debit=Coalesce(
            Sum("amount", filter=Q(transaction_type__in=DEBIT_TYPES)),
            ZERO,
        ),
    )

    return {
        "financial_year": financial_year,
        "fund_allotted": totals["total_credit"],
        "fund_released": totals["total_credit"],
        "previous_expenditure": totals["total_debit"],
        "available_balance": (
            totals["total_credit"] - totals["total_debit"]
        ),
        "as_on": timezone.localdate(),
    }


def get_selected_survey_item(case):
    try:
        survey = case.gem_survey
    except AttributeError as exc:
        raise ValidationError(
            "Complete the GeM survey before creating the Noting Sheet."
        ) from exc

    if survey.status != "COMPLETED":
        raise ValidationError(
            "The GeM survey must be marked Completed."
        )

    selected = survey.items.filter(
        selected_for_procurement=True
    ).first()

    if selected is None:
        raise ValidationError(
            "No survey item has been selected for procurement."
        )

    return selected


@transaction.atomic
def build_noting_initial_data(case):
    requirement = case.requirement_item

    if requirement.sub_head_id is None:
        raise ValidationError(
            "Requirement must have a Sub Head before Noting creation."
        )

    selected = get_selected_survey_item(case)
    snapshot = get_sub_head_fund_snapshot(requirement.sub_head)

    case_amount = selected.total_price
    including = snapshot["previous_expenditure"] + case_amount
    projected = snapshot["fund_released"] - including

    return {
        "financial_year": snapshot["financial_year"].name,
        "subject": (
            f"Procurement of {requirement.item_name} "
            f"for {requirement.purpose}"
        ),
        "requirement_summary": (
            f"{requirement.quantity} {selected.unit_of_measure} of "
            f"{requirement.item_name} is required for "
            f"{requirement.purpose}."
        ),
        "selected_survey_item": selected,
        "fund_head_snapshot": str(requirement.fund_head or ""),
        "sub_head_snapshot": str(requirement.sub_head or ""),
        "fund_allotted": snapshot["fund_allotted"],
        "fund_released": snapshot["fund_released"],
        "previous_expenditure": snapshot["previous_expenditure"],
        "current_case_amount": case_amount,
        "expenditure_including_case": including,
        "projected_balance": projected,
        "fund_position_as_on": snapshot["as_on"],
    }
