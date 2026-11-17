"""
Context Processors for the core app.

Provides access to feature toggles in templates via the config context variable.
"""
from constance import config


def app_feature_toggles(request):
    """
    Make feature toggle configuration available in all templates.
    
    Usage in templates:
    {% if config.APP_ENABLE_SOS %}
        <!-- SOS app content -->
    {% endif %}
    """
    return {
        'config': config,
    }


def csp_nonce(request):
    """Expose the per-request CSP nonce so inline scripts can use it.

    ``ContentSecurityPolicyMiddleware`` sets ``request.csp_nonce`` before the
    view runs; admin responses get an empty string because the admin policy
    still allows inline script.
    """
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def dashboard_sidebar(request):
    """Render the global sidebar navigation on every authenticated page.

    The sidebar used to be built only by the dashboard view. It now lives in
    ``base.html`` so the same navigation is available everywhere; building it
    here keeps views from having to pass ``sidebar_sections`` themselves.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    from .dashboard import build_sidebar

    return {'sidebar_sections': build_sidebar(user, request.path)}


