from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce

from .models import FundTransaction


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


def get_sub_head_balance(financial_year, sub_head):
    """
    Return financial totals for one Sub Head in one Financial Year.
    """

    transactions = FundTransaction.objects.filter(
        financial_year=financial_year,
        sub_head=sub_head,
        is_reversed=False,
    )

    totals = transactions.aggregate(
        opening_balance=Coalesce(
            Sum(
                Case(
                    When(
                        transaction_type="OPENING",
                        then=F("amount"),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2,
                    ),
                )
            ),
            Value(Decimal("0.00")),
        ),
        additional_credits=Coalesce(
            Sum(
                Case(
                    When(
                        transaction_type__in=[
                            "CREDIT",
                            "EXPENDITURE_REVERSAL",
                            "ADJUSTMENT_CREDIT",
                        ],
                        then=F("amount"),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2,
                    ),
                )
            ),
            Value(Decimal("0.00")),
        ),
        expenditure=Coalesce(
            Sum(
                Case(
                    When(
                        transaction_type__in=[
                            "EXPENDITURE",
                            "CREDIT_REVERSAL",
                            "ADJUSTMENT_DEBIT",
                        ],
                        then=F("amount"),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2,
                    ),
                )
            ),
            Value(Decimal("0.00")),
        ),
    )

    available_balance = (
        totals["opening_balance"]
        + totals["additional_credits"]
        - totals["expenditure"]
    )

    return {
        "opening_balance": totals["opening_balance"],
        "additional_credits": totals["additional_credits"],
        "expenditure": totals["expenditure"],
        "available_balance": available_balance,
    }


def get_fund_head_balance(financial_year, fund_head):
    """
    Return combined totals of all Sub Heads under one Fund Head.
    """

    transactions = FundTransaction.objects.filter(
        financial_year=financial_year,
        sub_head__fund_head=fund_head,
        is_reversed=False,
    )

    credit_total = transactions.filter(
        transaction_type__in=CREDIT_TYPES
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
        )
    )["total"]

    debit_total = transactions.filter(
        transaction_type__in=DEBIT_TYPES
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
        )
    )["total"]

    return {
        "total_credit": credit_total,
        "total_debit": debit_total,
        "available_balance": credit_total - debit_total,
    }


def get_transaction_ledger(financial_year, sub_head):
    """
    Return chronological ledger transactions.
    """

    return FundTransaction.objects.filter(
        financial_year=financial_year,
        sub_head=sub_head,
    ).order_by(
        "transaction_date",
        "created_at",
    )