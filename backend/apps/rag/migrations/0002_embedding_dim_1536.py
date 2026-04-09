"""
Migration: Change embedding dimension from 384 to 1536.
Also rebuildes indexes for the new dimension.

Run with: python manage.py makemigrations rag --name 0002_embedding_dim_1536
Or apply manually with the SQL below.

NOTE: This migration MUST be run before using the new RAG pipeline.
Existing 384-dim embeddings will become invalid and need to be re-indexed.
"""
from django.db import migrations
from pgvector.django import VectorField


class Migration(migrations.Migration):

    dependencies = [
        ("rag", "0001_initial"),
    ]

    operations = [
        # Change Chunk dense_embedding from 384 to 1536
        migrations.AlterField(
            model_name="chunk",
            name="dense_embedding",
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
    ]
