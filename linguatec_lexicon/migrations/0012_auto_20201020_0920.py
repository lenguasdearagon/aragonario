# Generated by Django 2.2.13 on 2020-10-20 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linguatec_lexicon', '0011_auto_entry_variations_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lexicon',
            name='name',
            field=models.CharField(max_length=32, unique=True),
        ),
    ]