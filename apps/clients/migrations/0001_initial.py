"""
Initial migration for the ``clients`` app (built by Nireez on the
projects-apis branch, merged here).

Registers Django's model-state awareness of the existing ``clients`` and
related tables -- all managed=False, so every operation here is a no-op
at the database level; these tables already exist and are owned
elsewhere.

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
            name='Client',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('company_name', models.CharField(blank=True, max_length=255, null=True)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('email', models.EmailField(blank=True, max_length=255, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('tax_id', models.CharField(blank=True, max_length=100, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'clients',
                'ordering': ['name'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ClientDocument',
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
            name='ClientInvoiceSummary',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('client_id', models.UUIDField()),
                ('project_id', models.UUIDField(blank=True, null=True)),
                ('unit_id', models.UUIDField(blank=True, null=True)),
                ('invoice_number', models.CharField(max_length=100, unique=True)),
                ('invoice_date', models.DateField()),
                ('due_date', models.DateField(blank=True, null=True)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('discount_amount', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=18, null=True)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('SENT', 'Sent'), ('PARTIALLY_PAID', 'Partially Paid'), ('PAID', 'Paid'), ('OVERDUE', 'Overdue'), ('CANCELLED', 'Cancelled')], default='DRAFT', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'client_invoices',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='ClientPayment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('payment_number', models.CharField(max_length=100, unique=True)),
                ('payment_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=18)),
                ('direction', models.CharField(max_length=20)),
                ('payment_method', models.CharField(max_length=50)),
                ('client_id', models.UUIDField(blank=True, null=True)),
                ('supplier_id', models.UUIDField(blank=True, null=True)),
                ('reference', models.CharField(blank=True, max_length=255, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'payments',
                'ordering': ['-payment_date'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='PaymentAllocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('payment_id', models.UUIDField()),
                ('client_invoice_id', models.UUIDField(blank=True, null=True)),
                ('supplier_invoice_id', models.UUIDField(blank=True, null=True)),
                ('allocated_amount', models.DecimalField(decimal_places=2, max_digits=18)),
            ],
            options={
                'db_table': 'payment_allocations',
                'managed': False,
            },
        ),
    ]
