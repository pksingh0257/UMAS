"""
Small helper bridging procurement -> finance. Kept as its own module
(not stuffed into models.py/views.py) so the Fund-Head/Sub-Head balance
calculation lives in exactly one place.
"""
from decimal import Decimal


def get_fund_balance(sub_head):
    """
    Returns (allotted, released) for a given masterdata.SubHead:
      allotted = total ever credited (Opening + Additional Credit +
                 reversal/adjustment credits), gross.
      released = allotted minus all debits so far (Expenditure +
                 reversal/adjustment debits) = current available balance.

    Returns (Decimal('0'), Decimal('0')) if sub_head is None — callers
    don't need to special-case a Requirement with no Fund/Sub Head set.
    """
    if sub_head is None:
        return Decimal("0"), Decimal("0")

    from finance.models import FundTransaction

    transactions = FundTransaction.objects.filter(sub_head=sub_head, is_reversed=False)

    allotted = sum((t.credit_amount for t in transactions), Decimal("0"))
    debited = sum((t.debit_amount for t in transactions), Decimal("0"))
    released = allotted - debited

    return allotted, released