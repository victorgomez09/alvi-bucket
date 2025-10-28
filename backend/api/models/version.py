from django.db import models
from api.models import Type

class Version(models.Model):
    id = models.AutoField(primary_key=True, editable=False)
    version_number = models.CharField(max_length=100, null=False)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)

    def __str__(self):
        return super().__str__()