from django.urls import path
from api.views import JarDownloadView, VanillaVersions, PaperVersions, ForgeVersions, NeoForgeVersions

urlpatterns = [
    # Maps GET /api/jar/download/ to our view
    path('jar/download/', JarDownloadView.as_view(), name='jar-download'),
    path('versions/vanilla', VanillaVersions.as_view(), name='vanilla-versions'),
    path('versions/paper', PaperVersions.as_view(), name='paper-versions'),
    path('versions/forge', ForgeVersions.as_view(), name='forge-versions'),
    path('versions/neoforge', NeoForgeVersions.as_view(), name='neoforge-versions')
]
