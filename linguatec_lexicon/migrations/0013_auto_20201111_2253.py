# Generated by Django 2.2.13 on 2020-11-11 22:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linguatec_lexicon', '0012_lexicon_name_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lexicon',
            name='dst_language',
            field=models.CharField(max_length=2),
        ),
        migrations.AlterField(
            model_name='lexicon',
            name='src_language',
            field=models.CharField(max_length=2),
        ),
    ]
