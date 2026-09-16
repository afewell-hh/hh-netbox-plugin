"""Portable, draft-only text-interchange persistence (#675)."""

from django.db import models


class InterchangeCatalogVersion(models.Model):
    namespace = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    version = models.CharField(max_length=100)
    content = models.JSONField()
    content_algorithm = models.CharField(max_length=100)
    content_digest = models.CharField(max_length=64)
    published = models.BooleanField(default=False)
    artifact_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("namespace", "slug", "version"), name="interchange_catalog_identity_version")]
        permissions = (
            ("publish_interchangecatalogversion", "Can publish interchange catalog version"),
            ("deprecate_interchangecatalogversion", "Can deprecate interchange catalog version"),
            ("withdraw_interchangecatalogversion", "Can withdraw interchange catalog version"),
        )

    def __str__(self):
        return f"{self.namespace}:{self.slug}@{self.version}"


class InterchangeDesignRevision(models.Model):
    namespace = models.CharField(max_length=255)
    slug = models.CharField(max_length=100)
    revision = models.CharField(max_length=100)
    document = models.JSONField()
    approved = models.BooleanField(default=False)
    artifact_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("namespace", "slug", "revision"), name="interchange_design_identity_revision")]
        permissions = (("approve_interchangedesignrevision", "Can approve interchange design revision"),)

    def __str__(self):
        return f"{self.namespace}:{self.slug}#{self.revision}"


class InterchangeProvenance(models.Model):
    design_revision = models.ForeignKey(InterchangeDesignRevision, null=True, blank=True,
                                        on_delete=models.CASCADE, related_name="provenance_records")
    payload = models.JSONField()


class InterchangeAudit(models.Model):
    outcome = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
