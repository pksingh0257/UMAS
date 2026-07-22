from django.db import models
from django.core.exceptions import ValidationError
from core_base.models import CoreModel
from masterdata.models import Unit, FundHead, ItemCategory


class RequirementRequest(CoreModel):
    """
    The entry point of the Nexus workflow (Blueprint Section 15).
    Raised by a Head Clerk; becomes read-only once submitted, since
    each Requirement Item spawns its own independent Procurement Case.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
    ]

    request_number = models.CharField(max_length=30, unique=True, editable=False)
    unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT, related_name="requirement_requests"
    )
    raised_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="requirement_requests_raised",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    remarks = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "req_requirement_requests"
        ordering = ["-created_at"]
        verbose_name = "Requirement Request"
        verbose_name_plural = "Requirement Requests"

    def __str__(self):
        return self.request_number

    def save(self, *args, **kwargs):
        if not self.request_number:
            # Sequential system-generated number, per Section 15.
            year = models.functions.Now()
            from django.utils import timezone

            yr = timezone.now().year
            last = (
                RequirementRequest.all_objects.filter(
                    request_number__startswith=f"RR-{yr}-"
                )
                .order_by("-request_number")
                .first()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.request_number.split("-")[-1]) + 1
                except ValueError:
                    seq = 1
            self.request_number = f"RR-{yr}-{seq:05d}"
        super().save(*args, **kwargs)

    def submit(self, user=None):
        """A Requirement Request must contain at least one Item before submission (Section 15)."""
        if not self.items.exists():
            raise ValidationError(
                "A Requirement Request must contain at least one Requirement Item before it can be submitted."
            )
        from django.utils import timezone

        self.status = "SUBMITTED"
        self.submitted_at = timezone.now()
        if user is not None:
            self.modified_by = user
        self.save()

        # Every Requirement Item independently spawns its own Procurement Case (Section 16).
        from procurement.models import ProcurementCase

        for item in self.items.filter(case_generated=False):
            ProcurementCase.objects.create(
                requirement_item=item,
                created_by=user,
                modified_by=user,
            )
            item.case_generated = True
            item.save(update_fields=["case_generated"])


class RequirementItem(CoreModel):
    """
    An individual item within a Requirement Request. Each item independently
    spawns its own Procurement Case once the parent Request is submitted
    (Section 15). Cannot be edited/deleted once its Procurement Case exists.
    """

    PRIORITY_CHOICES = [
        ("ROUTINE", "Routine"),
        ("URGENT", "Urgent"),
    ]

    requirement_request = models.ForeignKey(
        RequirementRequest, on_delete=models.PROTECT, related_name="items"
    )
    item_number = models.CharField(max_length=40, editable=False)
    description = models.TextField()
    quantity = models.PositiveIntegerField()
    fund_head = models.ForeignKey(
        FundHead, on_delete=models.PROTECT, related_name="requirement_items"
    )
    item_category = models.ForeignKey(
        ItemCategory,
        on_delete=models.PROTECT,
        related_name="requirement_items",
        null=True,
        blank=True,
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="ROUTINE"
    )

    # Set once this item spawns its Procurement Case; locks the item from further edits.
    case_generated = models.BooleanField(default=False)

    class Meta:
        db_table = "req_requirement_items"
        ordering = ["requirement_request", "item_number"]
        unique_together = ("requirement_request", "item_number")
        verbose_name = "Requirement Item"
        verbose_name_plural = "Requirement Items"

    def __str__(self):
        return self.item_number

    def clean(self):
        # Once a Procurement Case has been generated, this item becomes locked (Section 15).
        if self.pk and self.case_generated:
            original = RequirementItem.all_objects.get(pk=self.pk)
            if original.case_generated:
                raise ValidationError(
                    "This Requirement Item has already generated a Procurement Case and can no longer be edited here."
                )

    def save(self, *args, **kwargs):
        if not self.item_number:
            # Sub-reference numbering under the parent request, per Section 15.
            existing_count = RequirementItem.all_objects.filter(
                requirement_request=self.requirement_request
            ).count()
            self.item_number = (
                f"{self.requirement_request.request_number}-I{existing_count + 1:02d}"
            )
        super().save(*args, **kwargs)
