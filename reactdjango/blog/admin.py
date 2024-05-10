from django.contrib import admin
from .models import Document

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'pdf_file')
    search_fields = ('pdf_file',)

admin.site.register(Document, DocumentAdmin)


# Register your models here.
