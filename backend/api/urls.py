from django.urls import path
from api.views import JarDownloadView

urlpatterns = [
    # Maps GET /api/jar/download/ to our view
    path('jar/download/', JarDownloadView.as_view(), name='jar-download'),
]
