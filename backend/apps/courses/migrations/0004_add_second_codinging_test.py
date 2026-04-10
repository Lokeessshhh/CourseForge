# Generated migration for 2 coding tests per week

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_course_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='codingtest',
            name='test_number',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='weekplan',
            name='coding_test_1_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='weekplan',
            name='coding_test_2_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterUniqueTogether(
            name='codingtest',
            unique_together={('course', 'week_number', 'test_number')},
        ),
    ]
