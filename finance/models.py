from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from core_base.models import CoreModel
from masterdata.models import SubHead



class FinancialYear(CoreModel):
    """
    Defines the accounting period used by the Fund Module.

    Example:
        2026-27: 01 April 2026 to 31 March 2027

    Only one financial year can remain active at a time.
    A closed financial year cannot accept new fund transactions.
    """

    name = models.CharField(
        max_length=9,
        unique=True,
        verbose_name="Financial Year",
        help_text="Example: 2026-27",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    is_active = models.BooleanField(
        default=False,
        help_text="Only one financial year can remain active.",
    )

    is_closed = models.BooleanField(
        default=False,
        help_text="Closed financial years cannot accept new transactions.",
    )

    class Meta:
        db_table = "fin_financial_years"
        ordering = ["-start_date"]
        verbose_name = "Financial Year"
        verbose_name_plural = "Financial Years"

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}

        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                errors["end_date"] = (
                    "End date must be later than the start date."
                )

        if self.is_active and self.is_closed:
            errors["is_active"] = (
                "A closed financial year cannot remain active."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.is_active:
            FinancialYear.objects.exclude(pk=self.pk).filter(
                is_active=True
            ).update(is_active=False)

        super().save(*args, **kwargs)


class FundEntry(CoreModel):
    """
    Request for adding money to a Sub Head.

    CFA entry:
        Approved immediately.

    Account Officer entry:
        Remains pending until CFA approval.

    Only approved entries create a FundTransaction and affect balance.
    """

    ENTRY_TYPE_CHOICES = [
        ("OPENING", "Opening Balance"),
        ("ADDITIONAL_CREDIT", "Additional Credit"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING_CFA", "Pending CFA Approval"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned for Correction"),
        ("REJECTED", "Rejected"),
        ("REVERSED", "Reversed"),
    ]

    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name="fund_entries",
    )

    sub_head = models.ForeignKey(
        SubHead,
        on_delete=models.PROTECT,
        related_name="fund_entries",
    )

    entry_type = models.CharField(
        max_length=25,
        choices=ENTRY_TYPE_CHOICES,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    entry_date = models.DateField(
        default=timezone.localdate,
    )

    source = models.CharField(
        max_length=250,
        help_text=(
            "Example: Government grant, higher formation allocation, "
            "CSD profit or monthly cutting."
        ),
    )

    authority_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    authority_date = models.DateField(
        blank=True,
        null=True,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    cfa_remarks = models.TextField(
        blank=True,
        null=True,
    )

    cfa_acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fund_entries_cfa_acted",
        blank=True,
        null=True,
    )

    cfa_acted_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "fin_fund_entries"
        ordering = ["-entry_date", "-created_at"]
        verbose_name = "Fund Entry"
        verbose_name_plural = "Fund Entries"

    def __str__(self):
        return (
            f"{self.financial_year} | "
            f"{self.sub_head.code} | "
            f"{self.get_entry_type_display()} | "
            f"₹{self.amount}"
        )

    def clean(self):
        errors = {}

        if self.financial_year_id:
            if self.financial_year.is_closed:
                errors["financial_year"] = (
                    "Fund entries cannot be added to a closed financial year."
                )

        if self.sub_head_id:
            if not self.sub_head.is_active:
                errors["sub_head"] = (
                    "The selected Sub Head is inactive."
                )

            if not self.sub_head.fund_head.is_active:
                errors["sub_head"] = (
                    "The Fund Head of the selected Sub Head is inactive."
                )

        if self.entry_type == "OPENING":
            duplicate_opening = FundEntry.objects.filter(
                financial_year=self.financial_year,
                sub_head=self.sub_head,
                entry_type="OPENING",
            ).exclude(
                status__in=["REJECTED", "REVERSED"]
            )

            if self.pk:
                duplicate_opening = duplicate_opening.exclude(pk=self.pk)

            if duplicate_opening.exists():
                errors["entry_type"] = (
                    "An Opening Balance already exists or is pending "
                    "for this Sub Head and financial year."
                )

        if self.authority_date and self.entry_date:
            if self.authority_date > self.entry_date:
                errors["authority_date"] = (
                    "Authority date cannot be later than the fund entry date."
                )

        if errors:
            raise ValidationError(errors)

    def submit(self, user):
        """
        Submit a Fund Entry.

        CFA:
            Entry is approved immediately and posted to the ledger.

        Account Officer:
            Entry goes to CFA for approval.
        """

        if self.status not in ["DRAFT", "RETURNED"]:
            raise ValidationError(
                "Only Draft or Returned fund entries can be submitted."
            )

        role = getattr(user, "role", None)

        if role == "CFA":
            self.status = "APPROVED"
            self.cfa_acted_by = user
            self.cfa_acted_at = timezone.now()
            self.modified_by = user
            self.full_clean()
            self.save()

            self.create_ledger_transaction(user)

        elif role == "ACCOUNTS_OFFICER":
            self.status = "PENDING_CFA"
            self.modified_by = user
            self.full_clean()
            self.save()

        else:
            raise ValidationError(
                "Only CFA or Account Officer can submit a Fund Entry."
            )

    @transaction.atomic
    def cfa_decide(self, user, decision, remarks=""):
        """
        CFA action on an Account Officer Fund Entry.

        
        decision:
            APPROVED
            RETURNED
            REJECTED
        """

        if getattr(user, "role", None) != "CFA":
            raise ValidationError(
                "Only CFA can approve, return or reject a Fund Entry."
            )

        if self.status != "PENDING_CFA":
            raise ValidationError(
                "This Fund Entry is not pending CFA approval."
            )

        allowed_decisions = ["APPROVED", "RETURNED", "REJECTED"]

        if decision not in allowed_decisions:
            raise ValidationError(
                "Invalid CFA decision."
            )

        if decision in ["RETURNED", "REJECTED"] and not remarks.strip():
            raise ValidationError(
                "Remarks are mandatory when returning or rejecting an entry."
            )

        self.status = decision
        self.cfa_remarks = remarks
        self.cfa_acted_by = user
        self.cfa_acted_at = timezone.now()
        self.modified_by = user

        self.full_clean()
        self.save()

        if decision == "APPROVED":
            self.create_ledger_transaction(user)

    @transaction.atomic
    def create_ledger_transaction(self, user):
        """
        Create one permanent transaction for an approved Fund Entry.

        get_or_create prevents duplicate balance posting.
        """

        if self.status != "APPROVED":
            raise ValidationError(
                "Only an approved Fund Entry can be posted to the ledger."
            )

        transaction_type = (
            "OPENING"
            if self.entry_type == "OPENING"
            else "CREDIT"
        )

        fund_transaction, created = FundTransaction.objects.get_or_create(
            fund_entry=self,
            defaults={
                "financial_year": self.financial_year,
                "sub_head": self.sub_head,
                "transaction_type": transaction_type,
                "amount": self.amount,
                "transaction_date": self.entry_date,
                "reference_number": self.authority_number or "",
                "remarks": self.remarks or self.source,
                "created_by": user,
                "modified_by": user,
            },
        )

        return fund_transaction, created


class FundTransaction(CoreModel):
    """
    Permanent Fund Ledger.

    Balance is calculated from these transactions. It is never manually
    stored or edited as a current balance.
    """

    TRANSACTION_TYPE_CHOICES = [
        ("OPENING", "Opening Balance"),
        ("CREDIT", "Additional Credit"),
        ("EXPENDITURE", "Actual Expenditure"),
        ("CREDIT_REVERSAL", "Credit Reversal"),
        ("EXPENDITURE_REVERSAL", "Expenditure Reversal"),
        ("ADJUSTMENT_CREDIT", "Credit Adjustment"),
        ("ADJUSTMENT_DEBIT", "Debit Adjustment"),
    ]

    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name="fund_transactions",
    )

    sub_head = models.ForeignKey(
        SubHead,
        on_delete=models.PROTECT,
        related_name="fund_transactions",
    )

    transaction_type = models.CharField(
        max_length=30,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    transaction_date = models.DateField(
        default=timezone.localdate,
    )

    fund_entry = models.OneToOneField(
        FundEntry,
        on_delete=models.PROTECT,
        related_name="ledger_transaction",
        blank=True,
        null=True,
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    reference_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Example: FUND_ENTRY, PAYMENT or REVERSAL.",
    )

    reference_id = models.PositiveBigIntegerField(
        blank=True,
        null=True,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    is_reversed = models.BooleanField(
        default=False,
    )

    class Meta:
        db_table = "fin_fund_transactions"
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Fund Transaction"
        verbose_name_plural = "Fund Transactions"

    def __str__(self):
        return (
            f"{self.transaction_date} | "
            f"{self.sub_head.code} | "
            f"{self.get_transaction_type_display()} | "
            f"₹{self.amount}"
        )

    def clean(self):
        errors = {}

        if self.financial_year_id and self.financial_year.is_closed:
            errors["financial_year"] = (
                "Transactions cannot be posted in a closed financial year."
            )

        if self.sub_head_id and not self.sub_head.is_active:
            errors["sub_head"] = (
                "Transactions cannot be posted to an inactive Sub Head."
            )

        if self.fund_entry_id:
            if self.fund_entry.status != "APPROVED":
                errors["fund_entry"] = (
                    "The linked Fund Entry must be approved."
                )

            if (
                self.financial_year_id
                and self.fund_entry.financial_year_id
                != self.financial_year_id
            ):
                errors["financial_year"] = (
                    "Financial Year must match the linked Fund Entry."
                )

            if (
                self.sub_head_id
                and self.fund_entry.sub_head_id != self.sub_head_id
            ):
                errors["sub_head"] = (
                    "Sub Head must match the linked Fund Entry."
                )

        if errors:
            raise ValidationError(errors)

    @property
    def credit_amount(self):
        credit_types = {
            "OPENING",
            "CREDIT",
            "EXPENDITURE_REVERSAL",
            "ADJUSTMENT_CREDIT",
        }

        if self.transaction_type in credit_types:
            return self.amount

        return Decimal("0.00")

    @property
    def debit_amount(self):
        debit_types = {
            "EXPENDITURE",
            "CREDIT_REVERSAL",
            "ADJUSTMENT_DEBIT",
        }

        if self.transaction_type in debit_types:
            return self.amount

        return Decimal("0.00")

