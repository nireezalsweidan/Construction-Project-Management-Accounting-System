"""
Initial migration for the ``projects`` app (CPMAS-47, built by Nireez on
the projects-apis branch, merged here).

Registers Django's model-state awareness of the existing ``projects``
and ``project_employees`` tables, and a read-only filtered view onto the
shared ``documents`` table (``ProjectDocument``, permanently managed=False
-- that table is owned by the ``documents`` app, see CPMAS-25). This
migration exists purely so other apps' foreign keys (e.g.
expenses.Expense.project) resolve correctly.

``Project``/``ProjectEmployee`` are ``managed=True`` (real Django-owned
tables that happen to already exist in the live/dev database): this
migration's CreateModel operations must therefore be applied with
``migrate --fake-initial`` against a database that already has these
tables (any environment seeded from the schema SQL) so Django detects
they exist and skips the DDL, exactly as it would for any other
already-populated table being adopted into Django's migrations. A truly
empty database (e.g. the test suite's throwaway SQLite) has no such
conflict and gets real ``CREATE TABLE`` statements instead.

Added when merging projects-apis into backend for CPMAS-33 -- the
original branch had no migrations at all for this app. Project/
ProjectEmployee were originally captured here as managed=False (a no-op
placeholder) and later flipped to managed=True in 0002 via
AlterModelOptions -- which only updates migration *state*, never issues
the DDL to actually create the table. That left a fresh database (only
ever exercised by the test suite, since every real environment already
has these tables from the schema SQL) with no real projects/
project_employees tables at all, breaking any migration operation that
tries to alter them (see 0003). Fixed by declaring them managed=True
here from the start, in this already-applied-everywhere-but-tests
migration -- safe because Django never re-executes a migration whose
(app, name) it already has recorded as applied, on any database that
already ran this file.
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
            },
        ),
    ]
