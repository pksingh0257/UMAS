from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_attachment_size(file):
    """Reject attachments over 2MB."""
    max_bytes = 2 * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError("Attachment must be 2MB or smaller.")


class Requirement(models.Model):
    """
    One Requirement = one item (per your latest spec — this replaces the
    old RequirementRequest + RequirementItem header/items split).

    Workflow:
      DRAFT
        -> clerk clicks "Send for AO Approval" -> PENDING_AO
      PENDING_AO
        -> AO approves -> PENDING_CFA
        -> AO denies    -> AO_DENIED   (clerk edits, resends -> PENDING_AO)
      PENDING_CFA
        -> CFA approves -> APPROVED   (hook into Procurement goes here)
        -> CFA denies   -> CFA_DENIED (clerk edits, resends -> PENDING_AO)

    NOTE: on resubmission after a CFA denial, this sends it back through
    AO review again (safest default, since the item was edited). Change
    submit_to_ao() below if you'd rather skip straight back to CFA.
    """

    WORKFLOW_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING_AO", "Pending Account Officer"),
        ("AO_DENIED", "Returned by Account Officer"),
        ("PENDING_CFA", "Pending CFA"),
        ("CFA_DENIED", "Returned by CFA"),
        ("APPROVED", "Approved"),
    ]

    DECISION_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("DENIED", "Denied"),
    ]

    PURCHASE_MODE_CHOICES = [
        ("GEM", "GeM"),
        ("LOCAL", "Local"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]

    # ---- Identity ----
    requirement_id = models.CharField(max_length=30, unique=True, editable=False)

    # ---- Clerk-filled fields ----
    # Per your mockup: item_name / category / purpose / estimated_cost /
    # demanded_by are ALL plain text, varchar(250). estimated_cost is
    # deliberately a CharField (not Decimal) to match your spec exactly —
    # switch it to DecimalField later if you want numeric validation/sums.
    item_name = models.CharField(max_length=250)
    category = models.CharField(max_length=250)
    quantity = models.PositiveIntegerField()
    purpose = models.CharField(max_length=250)
    estimated_cost = models.CharField(max_length=250)
    demanded_by = models.CharField(max_length=250, help_text="Who this item is being demanded for")

    # "Select Fund" — excluded from the form for now per your note
    # ("escape this field"). Field kept on the model, optional, so it's
    # easy to wire back in later without another migration.
    fund_head = models.CharField(max_length=150, blank=True, null=True)

    purchase_mode = models.CharField(max_length=10, choices=PURCHASE_MODE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="MEDIUM")
    attachment = models.FileField(
        upload_to="requirement_attachments/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_attachment_size],
    )

    # ---- System-tracked ----
    raised_by = models.ForeignKey(
        "authentication.User", on_delete=models.PROTECT, related_name="requirements_raised"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    workflow_status = models.CharField(max_length=20, choices=WORKFLOW_CHOICES, default="DRAFT")

    # ---- Account Officer decision ----
    ao_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    ao_remarks = models.TextField(blank=True, null=True)
    ao_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requirements_ao_reviewed",
    )
    ao_acted_at = models.DateTimeField(null=True, blank=True)

    # ---- CFA decision ----
    cfa_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    cfa_remarks = models.TextField(blank=True, null=True)
    cfa_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requirements_cfa_reviewed",
    )
    cfa_acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "req_requirements"
        ordering = ["-created_at"]
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"

    def __str__(self):
        return f"{self.requirement_id} - {self.item_name}"

    @property
    def is_editable(self):
        """Clerk can only edit while in Draft or after being sent back."""
        return self.workflow_status in ("DRAFT", "AO_DENIED", "CFA_DENIED")

    @property
    def simple_approval_status(self):
        """
        Collapses the detailed workflow_status into the 3-value vocabulary
        from your mockup: Pending / Approved / Declined. This is what the
        form's read-only "Approval Status" field displays.
        """
        if self.workflow_status == "APPROVED":
            return "Approved"
        if self.workflow_status in ("AO_DENIED", "CFA_DENIED"):
            return "Declined"
        return "Pending"

    def save(self, *args, **kwargs):
        if not self.requirement_id:
            yr = timezone.now().year
            last = (
                Requirement.objects.filter(requirement_id__startswith=f"REQ-{yr}-")
                .order_by("-requirement_id")
                .first()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.requirement_id.split("-")[-1]) + 1
                except ValueError:
                    seq = 1
            self.requirement_id = f"REQ-{yr}-{seq:05d}"
        super().save(*args, **kwargs)

    # ---- Workflow transitions ----

    def submit_to_ao(self):
        """Clerk action: send (or resend) this requirement for AO review."""
        if not self.is_editable:
            raise ValidationError("This requirement is not currently editable/submittable.")
        self.workflow_status = "PENDING_AO"
        self.ao_status = "PENDING"
        self.ao_remarks = None
        self.ao_acted_by = None
        self.ao_acted_at = None
        self.save()

    def ao_decide(self, user, decision, remarks=""):
        """decision must be 'APPROVED' or 'DENIED'."""
        if self.workflow_status != "PENDING_AO":
            raise ValidationError("This requirement is not awaiting Account Officer review.")
        self.ao_status = decision
        self.ao_remarks = remarks
        self.ao_acted_by = user
        self.ao_acted_at = timezone.now()
        if decision == "APPROVED":
            self.workflow_status = "PENDING_CFA"
        elif decision == "DENIED":
            self.workflow_status = "AO_DENIED"
        self.save()

    def cfa_decide(self, user, decision, remarks=""):
        """decision must be 'APPROVED' or 'DENIED'."""
        if self.workflow_status != "PENDING_CFA":
            raise ValidationError("This requirement is not awaiting CFA review.")
        self.cfa_status = decision
        self.cfa_remarks = remarks
        self.cfa_acted_by = user
        self.cfa_acted_at = timezone.now()
        if decision == "APPROVED":
            self.workflow_status = "APPROVED"
        elif decision == "DENIED":
            self.workflow_status = "CFA_DENIED"
        self.save()

        if decision == "APPROVED":
            # Fully approved -> spawn its Procurement Case (Section 16).
            # get_or_create guards against ever double-creating a case if
            # this method somehow ran twice.
            from procurement.models import ProcurementCase
            ProcurementCase.objects.get_or_create(
                requirement_item=self,
                defaults={"created_by": user, "modified_by": user},
            )