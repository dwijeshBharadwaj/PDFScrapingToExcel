# Generated by Django 5.0.4 on 2024-04-28 18:03

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("blog", "0004_remove_pdffile_document_delete_document_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pdf_file", models.FileField(upload_to="pdf_documents/")),
            ],
        ),
    ]
