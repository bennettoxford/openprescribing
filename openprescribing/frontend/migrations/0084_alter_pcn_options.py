# Generated by Django 4.2.20 on 2025-04-22 08:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("frontend", "0083_measure_radar_exclude"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pcn",
            options={"ordering": ["name"]},
        ),
    ]
