# Migration to add coding test tracking fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_add_second_codinging_test'),
    ]

    operations = [
        migrations.AddField(
            model_name='weekplan',
            name='coding_tests_generated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='weekplan',
            name='coding_test_1_unlocked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='weekplan',
            name='coding_test_2_unlocked',
            field=models.BooleanField(default=False),
        ),
    ]
