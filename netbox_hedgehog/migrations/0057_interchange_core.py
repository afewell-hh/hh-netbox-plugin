"""Draft-only portable interchange persistence (#675)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("netbox_hedgehog", "0056_rack_plan_id_custom_field")]

    operations = [
        migrations.CreateModel(
            name="InterchangeCatalogVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("namespace", models.CharField(max_length=255)),
                ("slug", models.CharField(max_length=100)),
                ("version", models.CharField(max_length=100)),
                ("content", models.JSONField()),
                ("content_algorithm", models.CharField(max_length=100)),
                ("content_digest", models.CharField(max_length=64)),
                ("published", models.BooleanField(default=False)),
                ("artifact_digest", models.CharField(max_length=64)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("namespace", "slug", "version"), name="interchange_catalog_identity_version")]},
        ),
        migrations.CreateModel(
            name="InterchangeDesignRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("namespace", models.CharField(max_length=255)),
                ("slug", models.CharField(max_length=100)),
                ("revision", models.CharField(max_length=100)),
                ("document", models.JSONField()),
                ("approved", models.BooleanField(default=False)),
                ("artifact_digest", models.CharField(max_length=64)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("namespace", "slug", "revision"), name="interchange_design_identity_revision")]},
        ),
        migrations.CreateModel(
            name="InterchangeAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("outcome", models.CharField(max_length=64)),
                ("payload", models.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="InterchangeProvenance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("payload", models.JSONField()),
                ("design_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="provenance_records", to="netbox_hedgehog.interchangedesignrevision")),
            ],
        ),
    ]
