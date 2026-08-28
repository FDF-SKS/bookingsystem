from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from . import views
from django.shortcuts import render
#from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf.urls import handler404, handler500, handler403
from django.conf.urls.static import static

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'
handler403 = 'django.views.defaults.permission_denied'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),  # Protect the view with login_required
    path('organization/', include('organization.urls')),
    path('butikken/', include('Butikken.urls')),
    path('aktivitetsteam/', include('AktivitetsTeam.urls')),
    path('sjak/', include('Sjak.urls')),
    path('teknik/', include('Teknik.urls')),
    path('SOS/', include('SOS.urls')),
    path('foto/', include('Foto.urls')),
    path('depot/', include('Depot.urls')),
    path('loeb/', include('Loeb.urls')),
    
    # NEW: Comments URLs
    path('comments/', include('django_comments_xtd.urls')),
    path('comments/', include('django_comments.urls')),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.png')),
    path('test-404/', lambda r: render(r, '404.html')),
    path('test-500/', lambda r: render(r, '500.html')),
    path('test-403/', lambda r: render(r, '403.html')),
] #+ debug_toolbar_urls()

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



