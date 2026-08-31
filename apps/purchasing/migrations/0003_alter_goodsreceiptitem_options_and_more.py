"""
Migration for the ``purchasing`` app: adds default ordering to
PurchaseOrderItem and GoodsReceiptItem (both order by id).

AlterModelOptions is Django-state-only -- no DDL, nothing to reconcile
against the live database. Added after testing surfaced a
UnorderedObjectListWarning from DRF pagination on both models' list
endpoints (neither table has a natural ordering column in the schema).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0002_goodsreceipt_goodsreceiptitem'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='goodsreceiptitem',
            options={'ordering': ['id'], 'verbose_name': 'Goods Receipt Item', 'verbose_name_plural': 'Goods Receipt Items'},
        ),
        migrations.AlterModelOptions(
            name='purchaseorderitem',
            options={'ordering': ['id'], 'verbose_name': 'Purchase Order Item', 'verbose_name_plural': 'Purchase Order Items'},
        ),
    ]
