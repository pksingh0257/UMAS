"""
Review this migration against your local database before running it.

It:
- Creates GeMSurvey, GeMSurveyItem and EASItem.
- Adds structured Noting Sheet and EAS fields as nullable first.
- Links existing Noting Sheets/EAS records to Procurement Cases where possible.

After existing rows are corrected, a later data-hardening migration should
change mandatory nullable fields to null=False.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


def link_existing_records(apps, schema_editor):
    ProcurementCase = apps.get_model("procurement", "ProcurementCase")
    NotingSheet = apps.get_model("procurement", "NotingSheet")
    EAS = apps.get_model("procurement", "EAS")

    for noting in NotingSheet.objects.all():
        case = ProcurementCase.objects.filter(
            requirement_item_id=noting.requirement_id
        ).first()

        if case:
            noting.procurement_case_id = case.pk
            noting.save(update_fields=["procurement_case"])

    for eas in EAS.objects.select_related("noting_sheet"):
        case_id = getattr(eas.noting_sheet, "procurement_case_id", None)
        if case_id:
            eas.procurement_case_id = case_id
            eas.save(update_fields=["procurement_case"])


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0005_eas_contract_document_eas_invoice_document_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GeMSurvey",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "survey_date",
                    models.DateField(default=django.utils.timezone.localdate),
                ),
                ("search_keywords", models.CharField(blank=True, max_length=500)),
                ("survey_notes", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("COMPLETED", "Completed"),
                        ],
                        default="DRAFT",
                        max_length=15,
                    ),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "case",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gem_survey",
                        to="procurement.procurementcase",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_modified",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proc_gem_surveys",
                "ordering": ["-survey_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="GeMSurveyItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("serial_number", models.PositiveIntegerField(default=1)),
                ("product_name", models.CharField(max_length=250)),
                ("gem_product_id", models.CharField(blank=True, max_length=100)),
                ("seller_name", models.CharField(max_length=250)),
                ("make", models.CharField(blank=True, max_length=150)),
                ("model", models.CharField(blank=True, max_length=150)),
                ("technical_specifications", models.TextField()),
                ("unit_of_measure", models.CharField(max_length=50)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=12,
                    ),
                ),
                (
                    "unit_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=15,
                    ),
                ),
                ("warranty", models.CharField(blank=True, max_length=250)),
                ("guarantee", models.CharField(blank=True, max_length=250)),
                ("delivery_period", models.CharField(blank=True, max_length=150)),
                (
                    "seller_rating",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=3,
                        null=True,
                    ),
                ),
                (
                    "product_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="procurement/survey/product_images/%Y/%m/",
                    ),
                ),
                (
                    "gem_screenshot",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="procurement/survey/screenshots/%Y/%m/",
                    ),
                ),
                ("remarks", models.TextField(blank=True, null=True)),
                ("selected_for_procurement", models.BooleanField(default=False)),
                (
                    "survey",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="procurement.gemsurvey",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_modified",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proc_gem_survey_items",
                "ordering": ["serial_number", "created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="gemsurveyitem",
            constraint=models.UniqueConstraint(
                fields=("survey", "serial_number"),
                name="unique_survey_serial_number",
            ),
        ),

        # Existing rows require nullable compatibility fields.
        migrations.AddField(
            model_name="notingsheet",
            name="procurement_case",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="noting_sheet",
                to="procurement.procurementcase",
            ),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="file_number",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="sheet_number",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="branch",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="noting_date",
            field=models.DateField(
                default=django.utils.timezone.localdate
            ),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="financial_year",
            field=models.CharField(blank=True, max_length=9),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="unit_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="station",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="subject",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="requirement_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="detailed_justification",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="urgency_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="proposal_text",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="recommendation_text",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="selected_survey_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="noting_sheets",
                to="procurement.gemsurveyitem",
            ),
        ),

        *[
            migrations.AddField(
                model_name="notingsheet",
                name=name,
                field=models.DecimalField(
                    decimal_places=2,
                    default=0,
                    max_digits=15,
                ),
            )
            for name in [
                "fund_allotted",
                "fund_released",
                "previous_expenditure",
                "current_case_amount",
                "expenditure_including_case",
                "projected_balance",
            ]
        ],

        migrations.AddField(
            model_name="notingsheet",
            name="fund_head_snapshot",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="sub_head_snapshot",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="fund_position_as_on",
            field=models.DateField(
                default=django.utils.timezone.localdate
            ),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="generated_docx",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="procurement/generated/noting/docx/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="generated_pdf",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="procurement/generated/noting/pdf/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="notingsheet",
            name="document_version",
            field=models.PositiveIntegerField(default=1),
        ),

        migrations.AddField(
            model_name="eas",
            name="procurement_case",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="eas",
                to="procurement.procurementcase",
            ),
        ),
        migrations.AddField(
            model_name="eas",
            name="financial_year",
            field=models.CharField(blank=True, max_length=9),
        ),
        migrations.AddField(
            model_name="eas",
            name="sanction_date",
            field=models.DateField(
                default=django.utils.timezone.localdate
            ),
        ),
        migrations.AddField(
            model_name="eas",
            name="dfpds_authority_reference",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="eas",
            name="schedule_reference",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="eas",
            name="sub_schedule_reference",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="eas",
            name="supplier_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="eas",
            name="quantity_in_words",
            field=models.CharField(blank=True, max_length=250),
        ),

        *[
            migrations.AddField(
                model_name="eas",
                name=name,
                field=models.DecimalField(
                    decimal_places=2,
                    default=0,
                    max_digits=15,
                ),
            )
            for name in [
                "subtotal",
                "freight_charges",
                "other_charges_amount",
                "total_sanction_amount",
            ]
        ],

        *[
            migrations.AddField(
                model_name="eas",
                name=name,
                field=models.CharField(blank=True, max_length=100),
            )
            for name in [
                "major_head",
                "minor_head",
                "sub_head_account",
                "detailed_head",
                "cgda_code_head",
            ]
        ],

        migrations.AddField(
            model_name="eas",
            name="ifa_applicable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="eas",
            name="ifa_concurrence_reference",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="eas",
            name="ifa_not_applicable_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="eas",
            name="generated_docx",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="procurement/generated/eas/docx/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="eas",
            name="generated_pdf",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="procurement/generated/eas/pdf/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="eas",
            name="document_version",
            field=models.PositiveIntegerField(default=1),
        ),

        migrations.CreateModel(
            name="EASItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("serial_number", models.PositiveIntegerField(default=1)),
                ("item_description", models.TextField()),
                ("unit_of_measure", models.CharField(max_length=50)),
                (
                    "quantity",
                    models.DecimalField(decimal_places=3, max_digits=12),
                ),
                (
                    "unit_price",
                    models.DecimalField(decimal_places=2, max_digits=15),
                ),
                (
                    "eas",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="procurement.eas",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_modified",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proc_eas_items",
                "ordering": ["serial_number", "created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="easitem",
            constraint=models.UniqueConstraint(
                fields=("eas", "serial_number"),
                name="unique_eas_serial_number",
            ),
        ),

        migrations.RunPython(
            link_existing_records,
            migrations.RunPython.noop,
        ),
    ]
