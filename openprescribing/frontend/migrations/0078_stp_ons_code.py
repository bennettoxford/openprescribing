# Generated by Django 2.2.18 on 2022-09-22 18:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0077_remove_stp_regional_team'),
    ]

    operations = [
        migrations.AddField(
            model_name='stp',
            name='ons_code',
            field=models.CharField(blank=True, max_length=9, null=True),
        ),
    ]