"""
Security and feature-gate middleware.
"""
import secrets

from constance import config
from django.shortcuts import render


class ContentSecurityPolicyMiddleware:
    """
    Set a Content-Security-Policy header on every response.

    Inline JavaScript is blocked on the public site: ``script-src`` carries a
    fresh per-request nonce instead of ``'unsafe-inline'``, and every inline
    ``<script>`` element in the project templates carries that nonce. Inline
    event-handler attributes (``onclick`` etc.) are not covered by nonces, so
    templates use ``data-*`` attributes wired up by ``static/js/ui-actions.js``.

    ``style-src`` still allows inline styles because Bootstrap and the many
    ``style="..."`` attributes in the templates depend on them; inline CSS is a
    far smaller attack surface than inline script.

    External script/style sources are restricted to the exact hosts below,
    which blocks arbitrary third-party script injection.

    The Django/Unfold admin is a special case: it is staff-only and Unfold's
    Alpine.js both evaluates ``x-*`` expressions via ``new Function`` (requiring
    ``'unsafe-eval'``) and emits its own inline ``x-data`` expressions. It keeps
    a relaxed policy; the public policy is what protects visitor sessions.
    """

    ADMIN_PATH_PREFIX = '/admin/'

    NONCE_BYTES = 16

    # Single placeholder so the shared directives live in one place;
    # ``{script_nonce}`` is the script-src token list, which differs between the
    # nonce-based public policy and the relaxed admin policy.
    POLICY_TEMPLATE = (
        "default-src 'self'; "
        "script-src {script_nonce}"
        "https://cdn.jsdelivr.net https://unpkg.com https://client.sleekplan.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "img-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com "
        "https://*.tile.openstreetmap.org; "
        "font-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com; "
        "connect-src 'self' https://client.sleekplan.com https://*.sleekplan.com; "
        "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com "
        "https://player.vimeo.com https://w.soundcloud.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.ADMIN_PATH_PREFIX):
            # The admin has no nonce; it relies on 'unsafe-inline'/'unsafe-eval'.
            request.csp_nonce = ''
            response = self.get_response(request)
            response['Content-Security-Policy'] = self._build_policy(
                "'unsafe-inline' 'unsafe-eval' "
            )
            return response

        nonce = secrets.token_urlsafe(self.NONCE_BYTES)
        # Set before the view renders so templates can stamp ``nonce=`` on
        # their inline scripts.
        request.csp_nonce = nonce
        response = self.get_response(request)
        response['Content-Security-Policy'] = self._build_policy(
            f"'nonce-{nonce}' "
        )
        return response

    @classmethod
    def _build_policy(cls, script_nonce):
        return cls.POLICY_TEMPLATE.format(script_nonce=script_nonce)


class AppFeatureGateMiddleware:
    """
    Middleware that enforces feature toggles by blocking access to disabled apps.
    
    Maps URL paths to app feature toggles:
    - /sos/ → APP_ENABLE_SOS
    - /teknik/ → APP_ENABLE_TEKNIK
    - /aktivitetsteam/ → APP_ENABLE_AKTIVITETSTEAM
    - /foto/ → APP_ENABLE_FOTO
    - /butikken/ → APP_ENABLE_BUTIKKEN
    - /sjak/ → APP_ENABLE_SJAK
    - /loeb/ → APP_ENABLE_LOEB
    - /depot/ → APP_ENABLE_DEPOT
    - /organization/volunteer/ → APP_ENABLE_CONTACTS
    - /organization/volunteerappointment/ → APP_ENABLE_LEGEAFTALER
    
    Always allows: /admin/, /static/, /media/, and all other /organization/ paths (login, logout, profile, etc.)
    """

    # Mapping of URL prefixes to feature toggle names
    APP_URL_MAP = {
        'sos': 'APP_ENABLE_SOS',
        'teknik': 'APP_ENABLE_TEKNIK',
        'aktivitetsteam': 'APP_ENABLE_AKTIVITETSTEAM',
        'foto': 'APP_ENABLE_FOTO',
        'butikken': 'APP_ENABLE_BUTIKKEN',
        'sjak': 'APP_ENABLE_SJAK',
        'loeb': 'APP_ENABLE_LOEB',
        'depot': 'APP_ENABLE_DEPOT',
    }

    # Specific organization sub-routes that have feature toggles
    # Maps sub-route to toggle name
    ORGANIZATION_TOGGLES = {
        'volunteer': 'APP_ENABLE_CONTACTS',
        'volunteerappointment': 'APP_ENABLE_LEGEAFTALER',
    }

    # URLs that should always be accessible
    ALWAYS_ALLOWED = ['/admin/', '/static/', '/media/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the requested path should be blocked
        if self._should_block_request(request.path):
            return render(request, '404.html', status=404)
        
        response = self.get_response(request)
        return response

    def _should_block_request(self, path):
        """
        Determine if a request should be blocked based on feature toggles.
        
        Returns True if the request is to a disabled app, False otherwise.
        """
        # Always allow certain paths
        for allowed_path in self.ALWAYS_ALLOWED:
            if path.startswith(allowed_path):
                return False

        # Check if the path matches any app URL prefix
        path_parts = path.strip('/').split('/')
        if not path_parts:
            return False

        first_part = path_parts[0].lower()

        # Special handling for organization URLs
        if first_part == 'organization':
            # Allow organization URLs by default (for login, logout, profile, etc.)
            # Only block specific sub-routes that have feature toggles
            if len(path_parts) > 1:
                sub_route = path_parts[1].lower()
                if sub_route in self.ORGANIZATION_TOGGLES:
                    toggle_name = self.ORGANIZATION_TOGGLES[sub_route]
                    is_enabled = getattr(config, toggle_name, True)
                    return not is_enabled
            return False

        # Check other app URL prefixes
        if first_part in self.APP_URL_MAP:
            toggle_name = self.APP_URL_MAP[first_part]
            is_enabled = getattr(config, toggle_name, True)
            return not is_enabled

        return False
