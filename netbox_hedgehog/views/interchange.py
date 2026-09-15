"""Paste-only interchange UI (#684). No upload or public API surface."""
import time
import json

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
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


def error(request, message, location=None, status=200):
    context = {'error': message, 'location': location}
    return render(request, 'netbox_hedgehog/interchange/import.html', context, status=status)


class ImportView(View):
    template_name = 'netbox_hedgehog/interchange/import.html'
    def get(self, request):
        return render(request, self.template_name)
    def post(self, request):
        if not (request.user.has_perm('netbox_hedgehog.add_interchangedesignrevision') and
                request.user.has_perm('netbox_hedgehog.add_interchangecatalogversion')):
            return HttpResponseForbidden('catalog contributor permission is required')
        raw = request.META.get('CONTENT_LENGTH')
        if not raw or not raw.isdigit() or int(raw) != len(request.body) or int(raw) > limits()['max_encoded_body_bytes']:
            return error(request, 'Content-Length bounded-preflight rejection', None, 400)
        started = time.monotonic()
        try:
            document = interchange.decode_document(request.POST.get('paste', ''), limits=limits())
            if time.monotonic() - started >= limits()['max_operation_seconds']:
                return error(request, 'operation bounded-preflight rejection', None)
            result = interchange.import_bundle(document, user=request.user)
        except interchange.InterchangeError as exc:
            location = getattr(exc, 'source_location', None)
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
    obj = get_object_or_404(InterchangeDesignRevision, pk=pk)
    if not request.user.has_perm('netbox_hedgehog.view_interchangedesignrevision', obj):
        raise PermissionDenied
    return obj


class DesignDetailView(View):
    def get(self, request, pk):
        obj = visible_design(request, pk)
        return render(request, 'netbox_hedgehog/interchange/detail.html', {'object': obj})


class DesignEditView(View):
    def post(self, request, pk):
        obj = visible_design(request, pk)
        if obj.approved or not request.user.has_perm('netbox_hedgehog.change_interchangedesignrevision', obj):
            raise PermissionDenied
        obj.revision = request.POST.get('revision', obj.revision); obj.save()
        audit('ui-edit', request, design=obj.pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision', pk=obj.pk)


class DesignDeleteView(View):
    def post(self, request, pk):
        obj = visible_design(request, pk)
        if obj.approved or not request.user.has_perm('netbox_hedgehog.delete_interchangedesignrevision', obj): raise PermissionDenied
        obj.delete(); audit('ui-delete', request, design=pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision_list')


class DesignExportView(View):
    def get(self, request, pk):
        obj = visible_design(request, pk)
        audit('download', request, design=obj.pk)
        if not obj.document.get('identity'):
            payload = json.dumps({'artifact': 'draft', 'provenance': 'unavailable'})
        else:
            payload = interchange.export_revision(obj, fmt='json')
        return HttpResponse(payload, content_type='application/json')


class DesignApproveView(View):
    def post(self, request, pk):
        obj = visible_design(request, pk)
        if obj.approved or not request.user.has_perm('netbox_hedgehog.approve_interchangedesignrevision', obj): raise PermissionDenied
        obj.approved = True; obj.save(); audit('approve', request, design=obj.pk)
        return redirect('plugins:netbox_hedgehog:interchangedesignrevision', pk=obj.pk)
