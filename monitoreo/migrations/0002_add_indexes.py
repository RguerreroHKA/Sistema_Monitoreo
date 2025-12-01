# Generated migration file
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('monitoreo', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='eventodeacceso',
            index=models.Index(fields=['email_usuario', '-timestamp'], name='idx_email_timestamp'),
        ),
        migrations.AddIndex(
            model_name='eventodeacceso',
            index=models.Index(fields=['es_anomalia', '-timestamp'], name='idx_anomalia_timestamp'),
        ),
        migrations.AddIndex(
            model_name='eventodeacceso',
            index=models.Index(fields=['tipo_evento', '-timestamp'], name='idx_tipo_timestamp'),
        ),
        migrations.AddIndex(
            model_name='eventodeacceso',
            index=models.Index(fields=['archivo_id'], name='idx_archivo_id'),
        ),
        migrations.AddIndex(
            model_name='eventodeacceso',
            index=models.Index(fields=['timestamp'], name='idx_timestamp'),
        ),
    ]
