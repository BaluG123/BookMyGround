from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_ground_verification(apps, schema_editor):
    Ground = apps.get_model('grounds', 'Ground')
    for ground in Ground.objects.all():
        if ground.is_verified and ground.is_active:
            ground.verification_status = 'approved'
        elif ground.is_verified:
            ground.verification_status = 'approved'
        else:
            ground.verification_status = 'pending'
            if ground.is_active:
                ground.is_active = False
        ground.save(update_fields=['verification_status', 'is_active'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('grounds', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ground',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='ground',
            name='submitted_for_review_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ground',
            name='verification_status',
            field=models.CharField(
                choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='ground',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ground',
            name='verified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='verified_grounds',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_ground_verification, migrations.RunPython.noop),
    ]
