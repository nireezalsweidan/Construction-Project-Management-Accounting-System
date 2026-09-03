"""
Initial migration for the ``projects`` app (CPMAS-47, built by Nireez on
the projects-apis branch, merged here).

Registers Django's model-state awareness of the existing ``projects``,
``project_employees``, and ``documents`` (filtered view, ProjectDocument)
tables -- all managed=False, so every operation here is a no-op at the
database level; these tables already exist and are owned elsewhere. This
migration exists purely so other apps' foreign keys (e.g.
expenses.Expense.project) resolve correctly.

Added when merging projects-apis into backend for CPMAS-33 -- the
original branch had no migrations at all for this app.
"""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('manager_id', models.UUIDField(blank=True, null=True)),
                ('buyer_id', models.UUIDField(blank=True, null=True)),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=100, unique=True)),
                ('location', models.TextField(blank=True, null=True)),
                ('project_type', models.CharField(choices=[('WHOLE_BUILDING', 'Whole Building'), ('MULTI_UNIT', 'Multi Unit')], max_length=20)),
                ('estimated_sale_price', models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ('actual_sale_price', models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ('start_date', models.DateField()),
                ('expected_completion_date', models.DateField(blank=True, null=True)),
                ('actual_completion_date', models.DateField(blank=True, null=True)),
                ('contract_value', models.DecimalField(decimal_places=2, max_digits=18)),
                ('status', models.CharField(choices=[('PLANNING', 'Planning'), ('ACTIVE', 'Active'), ('ON_HOLD', 'On Hold'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], default='PLANNING', max_length=20)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'projects',
                'ordering': ['-created_at'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ProjectDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('uploaded_by', models.UUIDField()),
                ('file_name', models.CharField(max_length=255)),
                ('file_path', models.CharField(max_length=500)),
                ('file_type', models.CharField(blank=True, max_length=100, null=True)),
                ('file_size', models.BigIntegerField(blank=True, null=True)),
                ('document_type', models.CharField(blank=True, max_length=100, null=True)),
                ('entity_type', models.CharField(max_length=100)),
                ('entity_id', models.UUIDField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'documents',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ProjectEmployee',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('employee_id', models.UUIDField()),
                ('assigned_at', models.DateField()),
                ('released_at', models.DateField(blank=True, null=True)),
                ('role_on_project', models.CharField(blank=True, max_length=150, null=True)),
            ],
            options={
                'db_table': 'project_employees',
                'managed': False,
            },
        ),
    ]
