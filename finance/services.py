from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import FundEntry

@transaction.atomic
def create_fund_entry(*, created_by, **validated_data):
    """
    Create a Draft Fund Entry.

    Only the Account Officer can create Fund Entries.
    """

    if getattr(created_by, "role", None) != "ACCOUNTS_OFFICER":
        raise PermissionDenied(
            "Only the Account Officer can create a Fund Entry."
        )

    entry = FundEntry(
        **validated_data,
        status="DRAFT",
        created_by=created_by,
        modified_by=created_by,
    )

    entry.full_clean()
    entry.save()

    return entry


@transaction.atomic
def submit_fund_entry(*, entry_id, submitted_by):
    """
    Submit a Draft Fund Entry to CFA for approval.
    """

    entry = FundEntry.objects.select_for_update().get(pk=entry_id)

    entry.submit(submitted_by)

    return entry

@transaction.atomic
def decide_fund_entry(
        *,
        entry_id,
        decided_by,
        decision,
        remarks="",
    ):
        """
        Allow CFA to approve, return or reject a pending Fund Entry.
        """

        entry = FundEntry.objects.select_for_update().get(pk=entry_id)

        entry.cfa_decide(
            user=decided_by,
            decision=decision,
            remarks=remarks,
        )

        return entry    