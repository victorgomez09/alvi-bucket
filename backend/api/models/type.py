from django.db import models

class Type(models.Model):
    id = models.AutoField(primary_key=True, editable=False)
    name = models.CharField(max_length=100, null=False)
    creation_time = models.DateTimeField(auto_created=True)
    update_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return super().__str__()