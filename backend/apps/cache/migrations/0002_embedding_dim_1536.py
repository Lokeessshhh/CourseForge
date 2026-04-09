"""
Migration: Change QueryCache embedding dimension from 384 to 1536.
"""
from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ("cache", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="querycache",
            name="query_embedding",
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]
