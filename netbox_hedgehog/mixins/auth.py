"""
Authentication mixins for handling session timeouts in AJAX requests
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


class AjaxAuthenticationMixin:
    """
    Mixin to handle session timeout gracefully for AJAX sync requests.
    
    When a user's session expires, instead of returning HTML login page,
    this mixin returns a proper JSON error response that JavaScript can handle.
    """
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to handle AJAX authentication errors gracefully"""
        if not request.user.is_authenticated:
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Your session has expired. Please login again.',
                    'requires_login': True,
                    'action': 'redirect_to_login',
                    'login_url': '/login/'
                }, status=401)
                
        return super().dispatch(request, *args, **kwargs)


class LoginRequiredAjaxMixin(AjaxAuthenticationMixin):
    """
    Combination mixin that applies login_required decorator and AJAX auth handling
    """
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)