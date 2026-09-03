# Database schema reference

`construction_management_supabase.sql` is the canonical schema, as
actually run against the Supabase Postgres instance this project
connects to (provided by the team, committed here 2026-08-31 so it's not
something only reconstructable from the live database or chat history).

## How this relates to Django migrations

The live database was provisioned directly from this SQL file, ahead of
any Django migration. Django apps built against a table that already
exists here adopt it into migration history with `migrate --fake` /
`--fake-initial` rather than creating it — their model fields are
verified to match this file exactly first. If the live schema is ever
altered, update this file to match in the same change (it's meant to
stay the source of truth, not drift from reality).

## Tables modeled in Django so far

| Table(s) | Django app | Ticket |
|---|---|---|
| `tax_rates` | `taxes` | CPMAS-28 (minimal, FK target only) |
| `suppliers` | `suppliers` | CPMAS-28 (minimal, FK target only) |
| `users` (reflection only, `managed=False`) | `users` | CPMAS-29 (minimal, FK target only) |
| `material_categories`, `materials` | `inventory` | CPMAS-28 |
| `warehouses`, `stocks`, `stock_movements` | `inventory` | CPMAS-29 |
| `purchase_orders`, `purchase_order_items` | `purchasing` | CPMAS-30 |
| `goods_receipts`, `goods_receipt_items` | `purchasing` | CPMAS-31 |
| `supplier_invoices`, `supplier_invoice_items` | `invoicing` | CPMAS-32 |
| `expense_categories`, `expenses` | `expenses` | CPMAS-33 |
| `accounts`, `financial_transactions`, `transaction_lines` | `accounting` | CPMAS-34 |
| `client_invoices`, `client_invoice_items` | `invoicing` | CPMAS-35 |
| `payments`, `payment_allocations`, `receipts` | `payments` | CPMAS-35 |

Everything else in this file (`employees`, `contractors`, `documents`,
`notifications`, `audit_logs`, `units`, `timesheets`, and the rest) is
not yet modeled in Django -- those belong to other, currently unbuilt
tickets. `projects`/`clients` are modeled (CPMAS-47), just not listed
above since that ticket predates this table.

Where a not-yet-built table is needed as a foreign-key target (e.g.
`purchase_orders.created_by -> users.id`), the referencing app defines
only the minimal fields needed to satisfy that FK, not the full
ticket's functionality -- see each such model's docstring for specifics.
