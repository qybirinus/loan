# Generated by Django 5.0.7 on 2024-07-19 06:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0006_rename_date_payment_due_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payment',
            name='paid',
        ),
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(default='ยังไม่ถึงกำหนด', max_length=20),
        ),
        migrations.AlterField(
            model_name='payment',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='payment',
            name='slip',
            field=models.ImageField(blank=True, null=True, upload_to='slips/'),
        ),
    ]
