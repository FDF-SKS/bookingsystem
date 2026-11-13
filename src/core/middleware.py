"""
App Feature Gate Middleware

This middleware blocks access to disabled apps by returning a 404 response.
It checks the constance configuration to determine if an app is enabled.
"""
from constance import config
from django.shortcuts import render


class ContentSecurityPolicyMiddleware:
    """
    Set a Content-Security-Policy header on every response.

    The policy is intentionally permissive about inline scripts/styles
    (``'unsafe-inline'``) because the templates and third-party SDKs (Bootstrap,
    Leaflet, Sleekplan, etc.) rely on them. External script/style sources are
    still restricted to the exact hosts below, which blocks arbitrary
    third-party script injection.

    The Django/Unfold admin is a special case: Unfold's Alpine.js evaluates
    ``x-*`` expressions via ``new Function``, which browsers only allow when
    ``'unsafe-eval'`` is present. That relaxation is scoped to the staff-only
    ``/admin/`` prefix so the public site keeps a strict policy.
    """

    CSP_VALUE = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' "
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

    ADMIN_CSP_VALUE = CSP_VALUE.replace(
        "script-src 'self' 'unsafe-inline' ",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' ",
    )

    ADMIN_PATH_PREFIX = '/admin/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.ADMIN_PATH_PREFIX):
            response['Content-Security-Policy'] = self.ADMIN_CSP_VALUE
        else:
            response['Content-Security-Policy'] = self.CSP_VALUE
        return response


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


