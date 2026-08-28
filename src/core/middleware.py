"""
App Feature Gate Middleware

This middleware blocks access to disabled apps by returning a 404 response.
It checks the constance configuration to determine if an app is enabled.
"""
from django.shortcuts import render
from constance import config


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


