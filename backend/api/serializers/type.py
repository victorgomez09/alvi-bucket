from rest_framework import serializers
from api.models import Type

class TypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type