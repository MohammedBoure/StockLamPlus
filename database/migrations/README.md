# Database Migrations (`database/migrations`)

This directory contains standalone, reproducible SQL migration scripts for schema upgrades, architectural evolution, and data migrations.

## Files and Purpose

- **`20260914_wholesale_retail_migration.sql`**: Idempotent SQL migration script introducing wholesale and retail schema support across `Locations` (visibility & POS allowance), `Inventory_Batches` (parent batch linkage & batch type), `Sales_Invoices` (sale classification & due date), and `Clients` (price tier & credit limit).
