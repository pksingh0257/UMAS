"""
UAMS Procurement — Amended Phase 1 data foundation.

MERGE these classes/fields into procurement/models.py.
Do not register this file as a separate Django app model module.

Scope:
1. One ProcurementCase remains the parent record.
2. Structured GeM survey with repeatable items.
3. Noting Sheet fields required by the official Word format.
4. EAS fields required by the official sanction format.
5. AO review followed by CFA approval.
"""

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from core_base.models import CoreModel


class TwoLevelApprovalMixin(models.Model):
    """Reusable AO review -> CFA final approval workflow."""

    WORKFLOW_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING_AO", "Pending Account Officer"),
        ("AO_RETURNED", "Returned by Account Officer"),
        ("PENDING_CFA", "Pending CFA"),
        ("CFA_RETURNED", "Returned by CFA"),
        ("REJECTED", "Rejected"),
        ("APPROVED", "Approved"),
    ]

    DECISION_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("RETURNED", "Returned"),
        ("REJECTED", "Rejected"),
    ]

    workflow_status = models.CharField(
        max_length=20,
        choices=WORKFLOW_CHOICES,
        default="DRAFT",
    )

    ao_status = models.CharField(
        max_length=10,
        choices=DECISION_CHOICES,
        default="PENDING",
    )
    ao_remarks = models.TextField(blank=True, null=True)
    ao_acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_ao_actions",
        blank=True,
        null=True,
    )
    ao_acted_at = models.DateTimeField(blank=True, null=True)

    cfa_status = models.CharField(
        max_length=10,
        choices=DECISION_CHOICES,
        default="PENDING",
    )
    cfa_remarks = models.TextField(blank=True, null=True)
    cfa_acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_cfa_actions",
        blank=True,
        null=True,
    )
    cfa_acted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    @property
    def is_editable(self):
        return self.workflow_status in {
            "DRAFT",
            "AO_RETURNED",
            "CFA_RETURNED",
        }

    def submit_to_ao(self, user):
        if not self.is_editable:
            raise ValidationError(
                "Only Draft or Returned documents can be submitted."
            )

        self.workflow_status = "PENDING_AO"
        self.ao_status = "PENDING"
        self.ao_remarks = None
        self.ao_acted_by = None
        self.ao_acted_at = None
        self.cfa_status = "PENDING"
        self.cfa_remarks = None
        self.cfa_acted_by = None
        self.cfa_acted_at = None

        if hasattr(self, "modified_by"):
            self.modified_by = user

        self.full_clean()
        self.save()

    def ao_decide(self, user, decision, remarks=""):
        if getattr(user, "role", None) != "ACCOUNTS_OFFICER":
            raise ValidationError(
                "Only the Account Officer can review this document."
            )

        if self.workflow_status != "PENDING_AO":
            raise ValidationError(
                "This document is not pending Account Officer review."
            )

        if decision not in {"APPROVED", "RETURNED"}:
            raise ValidationError(
                "Account Officer decision must be APPROVED or RETURNED."
            )

        if decision == "RETURNED" and not remarks.strip():
            raise ValidationError(
                "Remarks are mandatory when returning a document."
            )

        self.ao_status = decision
        self.ao_remarks = remarks
        self.ao_acted_by = user
        self.ao_acted_at = timezone.now()
        self.workflow_status = (
            "PENDING_CFA"
            if decision == "APPROVED"
            else "AO_RETURNED"
        )

        if hasattr(self, "modified_by"):
            self.modified_by = user

        self.full_clean()
        self.save()

    def cfa_decide(self, user, decision, remarks=""):
        if getattr(user, "role", None) != "CFA":
            raise ValidationError(
                "Only CFA can approve, return or reject this document."
            )

        if self.workflow_status != "PENDING_CFA":
            raise ValidationError(
                "This document is not pending CFA decision."
            )

        if decision not in {"APPROVED", "RETURNED", "REJECTED"}:
            raise ValidationError("Invalid CFA decision.")

        if decision in {"RETURNED", "REJECTED"} and not remarks.strip():
            raise ValidationError(
                "Remarks are mandatory when returning or rejecting."
            )

        self.cfa_status = decision
        self.cfa_remarks = remarks
        self.cfa_acted_by = user
        self.cfa_acted_at = timezone.now()

        status_map = {
            "APPROVED": "APPROVED",
            "RETURNED": "CFA_RETURNED",
            "REJECTED": "REJECTED",
        }
        self.workflow_status = status_map[decision]

        if hasattr(self, "modified_by"):
            self.modified_by = user

        self.full_clean()
        self.save()


class GeMSurvey(CoreModel):
    """One structured market survey per Procurement Case."""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("COMPLETED", "Completed"),
    ]

    case = models.OneToOneField(
        "procurement.ProcurementCase",
        on_delete=models.PROTECT,
        related_name="gem_survey",
    )
    survey_date = models.DateField(default=timezone.localdate)
    search_keywords = models.CharField(max_length=500, blank=True)
    survey_notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "proc_gem_surveys"
        ordering = ["-survey_date", "-created_at"]

    def __str__(self):
        return f"Survey - {self.case.case_number}"

    def clean(self):
        if self.status == "COMPLETED":
            if not self.items.exists():
                raise ValidationError(
                    "At least one GeM survey item is required."
                )
            if not self.items.filter(selected_for_procurement=True).exists():
                raise ValidationError(
                    "Select one survey item for procurement."
                )

    @transaction.atomic
    def mark_completed(self, user):
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.modified_by = user
        self.full_clean()
        self.save()


class GeMSurveyItem(CoreModel):
    """Repeatable GeM products compared during market survey."""

    survey = models.ForeignKey(
        GeMSurvey,
        on_delete=models.CASCADE,
        related_name="items",
    )
    serial_number = models.PositiveIntegerField(default=1)

    product_name = models.CharField(max_length=250)
    gem_product_id = models.CharField(max_length=100, blank=True)
    seller_name = models.CharField(max_length=250)
    make = models.CharField(max_length=150, blank=True)
    model = models.CharField(max_length=150, blank=True)
    technical_specifications = models.TextField()

    unit_of_measure = models.CharField(
        max_length=50,
        verbose_name="A/U",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    warranty = models.CharField(max_length=250, blank=True)
    guarantee = models.CharField(max_length=250, blank=True)
    delivery_period = models.CharField(max_length=150, blank=True)
    seller_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        blank=True,
        null=True,
    )

    product_image = models.ImageField(
        upload_to="procurement/survey/product_images/%Y/%m/",
        blank=True,
        null=True,
    )
    gem_screenshot = models.ImageField(
        upload_to="procurement/survey/screenshots/%Y/%m/",
        blank=True,
        null=True,
    )

    remarks = models.TextField(blank=True, null=True)
    selected_for_procurement = models.BooleanField(default=False)

    class Meta:
        db_table = "proc_gem_survey_items"
        ordering = ["serial_number", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "serial_number"],
                name="unique_survey_serial_number",
            )
        ]

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def clean(self):
        if self.seller_rating is not None:
            if self.seller_rating < 0 or self.seller_rating > 5:
                raise ValidationError(
                    {"seller_rating": "Seller rating must be between 0 and 5."}
                )

        if self.selected_for_procurement and self.survey_id:
            duplicate = GeMSurveyItem.objects.filter(
                survey_id=self.survey_id,
                selected_for_procurement=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError(
                    "Only one survey item may be selected for procurement."
                )


# ----------------------------------------------------------------------
# Add/merge the following fields into the EXISTING NotingSheet model.
# Do not create a second NotingSheet class.
# ----------------------------------------------------------------------

NOTING_SHEET_PHASE1_FIELDS = r"""
procurement_case = models.OneToOneField(
    ProcurementCase,
    on_delete=models.PROTECT,
    related_name="noting_sheet",
)

file_number = models.CharField(max_length=100)
sheet_number = models.CharField(max_length=30, blank=True)
branch = models.CharField(max_length=150)
noting_date = models.DateField(default=timezone.localdate)
financial_year = models.CharField(max_length=9)

unit_name = models.CharField(max_length=200)
station = models.CharField(max_length=150)
subject = models.CharField(max_length=500)

requirement_summary = models.TextField()
detailed_justification = models.TextField()
urgency_reason = models.TextField(blank=True)
proposal_text = models.TextField()
recommendation_text = models.TextField()

selected_survey_item = models.ForeignKey(
    GeMSurveyItem,
    on_delete=models.PROTECT,
    related_name="noting_sheets",
)

fund_head_snapshot = models.CharField(max_length=250)
sub_head_snapshot = models.CharField(max_length=250)
fund_allotted = models.DecimalField(max_digits=15, decimal_places=2)
fund_released = models.DecimalField(max_digits=15, decimal_places=2)
previous_expenditure = models.DecimalField(max_digits=15, decimal_places=2)
current_case_amount = models.DecimalField(max_digits=15, decimal_places=2)
expenditure_including_case = models.DecimalField(max_digits=15, decimal_places=2)
projected_balance = models.DecimalField(max_digits=15, decimal_places=2)
fund_position_as_on = models.DateField(default=timezone.localdate)

generated_docx = models.FileField(
    upload_to="procurement/generated/noting/docx/%Y/%m/",
    blank=True,
    null=True,
)
generated_pdf = models.FileField(
    upload_to="procurement/generated/noting/pdf/%Y/%m/",
    blank=True,
    null=True,
)
document_version = models.PositiveIntegerField(default=1)
"""


# ----------------------------------------------------------------------
# Add/merge the following fields into the EXISTING EAS model.
# Do not create a second EAS class.
# ----------------------------------------------------------------------

EAS_PHASE1_FIELDS = r"""
procurement_case = models.OneToOneField(
    ProcurementCase,
    on_delete=models.PROTECT,
    related_name="eas",
)

financial_year = models.CharField(max_length=9)
sanction_date = models.DateField(default=timezone.localdate)

dfpds_authority_reference = models.CharField(max_length=250)
schedule_reference = models.CharField(max_length=250, blank=True)
sub_schedule_reference = models.CharField(max_length=250, blank=True)

supplier_address = models.TextField(blank=True)
quantity_in_words = models.CharField(max_length=250)

subtotal = models.DecimalField(max_digits=15, decimal_places=2)
freight_charges = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    default=0,
)
other_charges_amount = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    default=0,
)
total_sanction_amount = models.DecimalField(
    max_digits=15,
    decimal_places=2,
)

major_head = models.CharField(max_length=100)
minor_head = models.CharField(max_length=100)
sub_head_account = models.CharField(max_length=100)
detailed_head = models.CharField(max_length=100)
cgda_code_head = models.CharField(max_length=100)

ifa_applicable = models.BooleanField(default=False)
ifa_concurrence_reference = models.CharField(
    max_length=250,
    blank=True,
)
ifa_not_applicable_reason = models.TextField(blank=True)

generated_docx = models.FileField(
    upload_to="procurement/generated/eas/docx/%Y/%m/",
    blank=True,
    null=True,
)
generated_pdf = models.FileField(
    upload_to="procurement/generated/eas/pdf/%Y/%m/",
    blank=True,
    null=True,
)
document_version = models.PositiveIntegerField(default=1)
"""


class EASItem(CoreModel):
    """Repeatable item table corresponding to EAS paragraphs 7.1/7.2."""

    eas = models.ForeignKey(
        "procurement.EAS",
        on_delete=models.CASCADE,
        related_name="items",
    )
    serial_number = models.PositiveIntegerField(default=1)
    item_description = models.TextField()
    unit_of_measure = models.CharField(max_length=50, verbose_name="A/U")
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        db_table = "proc_eas_items"
        ordering = ["serial_number", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["eas", "serial_number"],
                name="unique_eas_serial_number",
            )
        ]

    @property
    def amount(self):
        return self.quantity * self.unit_price
