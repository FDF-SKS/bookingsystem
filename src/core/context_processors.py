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


