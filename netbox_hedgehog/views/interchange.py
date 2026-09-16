"""Paste-only interchange UI (#684). No upload or public API surface."""
import time
import json
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.http.request import QueryDict
from django.shortcuts import redirect, render
from django.views import View

from netbox_hedgehog import interchange
from netbox_hedgehog.models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
)


DEFAULT_LIMITS = {'max_encoded_body_bytes': 10 * 1024 * 1024, 'max_objects': 5000,
                  'max_nesting_depth': 32, 'max_operation_seconds': 30}


def limits():
    values = dict(DEFAULT_LIMITS)
    values.update(settings.PLUGINS_CONFIG.get('netbox_hedgehog', {}).get('interchange_import_limits', {}))
    return values


def allowed(request, action, obj=None):
    model = obj.__class__ if obj is not None else None
    if model:
        perm = f'netbox_hedgehog.{action}_{model._meta.model_name}'
        return request.user.has_perm(perm, obj)
    return request.user.has_perm(f'netbox_hedgehog.{action}_interchangedesignrevision')


def audit(outcome, request, **scope):
    InterchangeAudit.objects.create(outcome=outcome, payload={
        'actor': request.user.pk, 'time': time.time(), 'scope': scope,
        'provenance': 'interchange-ui',
    })


def audit_failure(request, stage):
    """Persist the minimal, secret-free failure record required for pasted text."""
    audit('ui-import-failed', request, stage=stage)


def error(request, message, location=None, status=200):
    context = {'error': message, 'location': location}
    return render(request, 'netbox_hedgehog/interchange/import.html', context, status=status)


def complete_form_encoding(body):
    """Reject a body truncated in the middle of percent encoding.

    Unit normally enforces Content-Length before Django sees a request.  This
    small application-layer backstop makes the same failure bounded when a
    proxy supplies a truncated urlencoded body.
    """
    return re.search(br'%(?![0-9A-Fa-f]{2})', body) is None


def read_paste_request(request):
    """Read at most the configured application limit, never ``request.body``.

    The declared size is checked before reading.  The extra byte detects a
    stream exceeding that declaration/limit without materialising it all.
    """
    raw = request.META.get('CONTENT_LENGTH')
    cap = limits()['max_encoded_body_bytes']
    if not raw or not raw.isdigit() or int(raw) > cap:
        return None
    body = request.read(int(raw) + 1)
    if len(body) != int(raw) or not complete_form_encoding(body):
        return None
    return body


def pasted_text(request, body):
    if request.content_type == 'application/x-www-form-urlencoded':
        return QueryDict(body, encoding=request.encoding or 'utf-8').get('paste', '')
    return body.decode(request.encoding or 'utf-8')


class ImportView(View):
    template_name = 'netbox_hedgehog/interchange/import.html'
    def get(self, request):
        return render(request, self.template_name)
    def post(self, request):
        if not request.user.has_perm('netbox_hedgehog.add_interchangedesignrevision'):
            audit_failure(request, 'design-permission')
            return HttpResponseForbidden('design author permission is required')
        body = read_paste_request(request)
        if body is None:
            audit_failure(request, 'transport-preflight')
            return error(request, 'Content-Length bounded-preflight rejection', None, 400)
        started = time.monotonic()
        try:
            # A paste is text, not an uploaded file.  Accept a conventional
            # form post as well as a text/plain body; the interchange parser,
            # not the HTTP media type or a filename, selects YAML versus JSON.
            paste = pasted_text(request, body)
            document = interchange.decode_document(paste, limits=limits())
            has_catalog = any(item.get('kind') == 'CatalogVersion'
                              for item in document.get('objects', []))
            if has_catalog and not request.user.has_perm('netbox_hedgehog.add_interchangecatalogversion'):
                audit_failure(request, 'catalog-permission')
                return HttpResponseForbidden('catalog contributor permission is required')
            deadline = started + limits()['max_operation_seconds']
            result = interchange.import_bundle(document, user=request.user, deadline=deadline)
        except interchange.InterchangeError as exc:
            location = getattr(exc, 'source_location', None)
            audit_failure(request, 'validation' if location else 'operation')
            return error(request, str(exc), location)
        audit('ui-import', request, design=getattr(result.design_revision, 'pk', None))
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision', pk=result.design_revision.pk)


class DesignListView(View):
    def get(self, request):
        if not request.user.has_perm('netbox_hedgehog.view_interchangedesignrevision'):
            raise PermissionDenied
        objects = [obj for obj in InterchangeDesignRevision.objects.all()
                   if request.user.has_perm('netbox_hedgehog.view_interchangedesignrevision', obj)]
        return render(request, 'netbox_hedgehog/interchange/list.html', {'objects': objects, 'kind': 'Design revisions'})


class CatalogListView(View):
    def get(self, request):
        if not request.user.has_perm('netbox_hedgehog.view_interchangecatalogversion'):
            raise PermissionDenied
        objects = [obj for obj in InterchangeCatalogVersion.objects.all()
                   if request.user.has_perm('netbox_hedgehog.view_interchangecatalogversion', obj)]
        return render(request, 'netbox_hedgehog/interchange/list.html', {'objects': objects, 'kind': 'Catalog versions'})


def visible_design(request, pk):
    obj = InterchangeDesignRevision.objects.filter(pk=pk).first()
    if obj is None or not request.user.has_perm('netbox_hedgehog.view_interchangedesignrevision', obj):
        # A constrained object permission must not disclose whether the
        # requested revision exists outside the caller's scope.
        return None
    return obj


def not_visible_response():
    """Identical response for absent and out-of-scope revisions."""
    return HttpResponseNotFound('Not found')


def actionable_design(request, pk, action):
    """Resolve a mutation target by its operation permission.

    Transition permissions are intentionally independent of ``view``.  The
    caller still receives a denial when it lacks the requested operation, and
    a locked state is checked only after that operation is authorized.
    """
    obj = InterchangeDesignRevision.objects.filter(pk=pk).first()
    if obj is None:
        return None
    if not request.user.has_perm(f'netbox_hedgehog.{action}_interchangedesignrevision', obj):
        raise PermissionDenied
    return obj


class DesignDetailView(View):
    def get(self, request, pk):
        obj = visible_design(request, pk)
        if obj is None:
            return not_visible_response()
        return render(request, 'netbox_hedgehog/interchange/detail.html', {'object': obj})


class DesignEditView(View):
    def post(self, request, pk):
        obj = actionable_design(request, pk, 'change')
        if obj is None:
            return not_visible_response()
        if obj.approved:
            raise PermissionDenied
        obj.revision = request.POST.get('revision', obj.revision); obj.save()
        audit('ui-edit', request, design=obj.pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision', pk=obj.pk)


class DesignDeleteView(View):
    def post(self, request, pk):
        obj = actionable_design(request, pk, 'delete')
        if obj is None:
            return not_visible_response()
        if obj.approved: raise PermissionDenied
        obj.delete(); audit('ui-delete', request, design=pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision_list')


class DesignExportView(View):
    def get(self, request, pk):
        obj = visible_design(request, pk)
        if obj is None:
            return not_visible_response()
        audit('download', request, design=obj.pk)
        if not obj.document.get('identity'):
            payload = json.dumps({'artifact': 'draft', 'provenance': 'unavailable'})
        else:
            payload = interchange.export_revision(obj, fmt='json')
        return HttpResponse(payload, content_type='application/json')


class DesignApproveView(View):
    def post(self, request, pk):
        obj = actionable_design(request, pk, 'approve')
        if obj is None:
            return not_visible_response()
        if obj.approved: raise PermissionDenied
        obj.approved = True; obj.save(); audit('approve', request, design=obj.pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision', pk=obj.pk)
