# forms.py

from django import forms
from multiupload.fields import MultiFileField

class DocumentForm(forms.Form):
    files = MultiFileField(
        max_num=500,  # Maximum number of files allowed
        min_num=1,   # Minimum number of files required
        max_file_size=1024*1024*5,  # Maximum file size in bytes (5 MB)
        label=''  # Remove the label completely
    )

   