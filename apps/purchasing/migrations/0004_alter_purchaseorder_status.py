"""
Migration for the ``purchasing`` app: adds a database index to
PurchaseOrder.status.

An equivalent index (idx_purchase_orders_status) already exists on the
live database under a different name, per the canonical
construction_management_supabase.sql -- this migration is applied there
with ``--fake`` to avoid creating a redundant duplicate index. On a
fresh environment it runs normally and creates the index for real.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0003_alter_goodsreceiptitem_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseorder',
            name='status',
            field=models.CharField(choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('PARTIALLY_RECEIVED', 'Partially Received'), ('RECEIVED', 'Received'), ('CANCELLED', 'Cancelled')], db_index=True, default='DRAFT', max_length=20),
        ),
    ]
