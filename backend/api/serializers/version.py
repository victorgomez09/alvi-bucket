from rest_framework import serializers
from api.models import Version

class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version