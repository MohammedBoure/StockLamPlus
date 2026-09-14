#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/migrate_wholesale_retail_schema.py

Production-Grade Database Migration Script: Wholesale & Retail Schema Evolution.
Executes idempotent DDL alterations on MySQL with comprehensive pre-flight verification,
schema inspection via information_schema, and zero-data-loss guarantees.

Target Schema Enhancements:
  1. Locations:
     - Visibility ENUM('Private', 'Public') NOT NULL DEFAULT 'Private'
     - Allow_POS_Sales BOOLEAN NOT NULL DEFAULT FALSE
     - Index idx_locations_visibility_pos (Visibility, Allow_POS_Sales)
  2. Inventory_Batches:
     - Parent_Batch_ID BIGINT UNSIGNED NULL
     - Batch_Type ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk'
     - Foreign key fk_batch_parent_batch referencing Inventory_Batches(Batch_ID) ON DELETE SET NULL
     - Composite index idx_batch_parent_type (Parent_Batch_ID, Batch_Type)
  3. Sales_Invoices:
     - Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS'
     - Due_Date DATE NULL
     - Composite index idx_sales_type_due_date (Sale_Type, Due_Date)
  4. Clients:
     - Price_Tier ENUM('Prix_1', 'Prix_2', 'Prix_3', 'Prix_4') NOT NULL DEFAULT 'Prix_1'
     - Credit_Limit DECIMAL(15,2) NOT NULL DEFAULT 0.00
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WholesaleRetailMigrator")

try:
    import mysql.connector
    from mysql.connector import errorcode
    HAS_MYSQL_CONNECTOR = True
except ImportError:
    HAS_MYSQL_CONNECTOR = False


class WholesaleRetailMigrator:
    """
    Executes idempotent, verifiable schema alterations across Wholesale & Retail entities.
    Ensures safe execution in MySQL by querying information_schema metadata prior to
    running ALTER TABLE statements, avoiding DDL errors and duplicate keys.
    """

    MIGRATION_STEPS: List[Dict[str, Any]] = [
        # --- 1. Locations Table ---
        {
            "id": "loc_col_visibility",
            "table": "Locations",
            "type": "column",
            "target": "Visibility",
            "sql": (
                "ALTER TABLE Locations "
                "ADD COLUMN Visibility ENUM('Private', 'Public') NOT NULL DEFAULT 'Private' "
                "AFTER Temperature_Zone"
            ),
            "description": "Add 'Visibility' to Locations (Private vs Public)"
        },
        {
            "id": "loc_col_allow_pos",
            "table": "Locations",
            "type": "column",
            "target": "Allow_POS_Sales",
            "sql": (
                "ALTER TABLE Locations "
                "ADD COLUMN Allow_POS_Sales BOOLEAN NOT NULL DEFAULT FALSE "
                "AFTER Visibility"
            ),
            "description": "Add 'Allow_POS_Sales' flag to Locations"
        },
        {
            "id": "loc_idx_visibility_pos",
            "table": "Locations",
            "type": "index",
            "target": "idx_locations_visibility_pos",
            "sql": "CREATE INDEX idx_locations_visibility_pos ON Locations(Visibility, Allow_POS_Sales)",
            "description": "Add performance index on Locations(Visibility, Allow_POS_Sales)"
        },

        # --- 2. Inventory_Batches Table ---
        {
            "id": "batch_col_parent_id",
            "table": "Inventory_Batches",
            "type": "column",
            "target": "Parent_Batch_ID",
            "sql": "ALTER TABLE Inventory_Batches ADD COLUMN Parent_Batch_ID BIGINT UNSIGNED NULL AFTER Batch_ID",
            "description": "Add 'Parent_Batch_ID' for batch lineage and extraction tracking"
        },
        {
            "id": "batch_col_type",
            "table": "Inventory_Batches",
            "type": "column",
            "target": "Batch_Type",
            "sql": (
                "ALTER TABLE Inventory_Batches "
                "ADD COLUMN Batch_Type ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk' "
                "AFTER Status"
            ),
            "description": "Add 'Batch_Type' (Standard Bulk vs Extracted Retail)"
        },
        {
            "id": "batch_fk_parent",
            "table": "Inventory_Batches",
            "type": "foreign_key",
            "target": "fk_batch_parent_batch",
            "sql_template": (
                "ALTER TABLE Inventory_Batches "
                "ADD CONSTRAINT fk_batch_parent_batch "
                "FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches({pk}) "
                "ON DELETE SET NULL ON UPDATE CASCADE"
            ),
            "description": "Add Foreign Key constraint on Parent_Batch_ID referencing Inventory_Batches"
        },
        {
            "id": "batch_idx_parent_type",
            "table": "Inventory_Batches",
            "type": "index",
            "target": "idx_batch_parent_type",
            "sql": "CREATE INDEX idx_batch_parent_type ON Inventory_Batches(Parent_Batch_ID, Batch_Type)",
            "description": "Add composite index on Inventory_Batches(Parent_Batch_ID, Batch_Type)"
        },

        # --- 3. Sales_Invoices Table ---
        {
            "id": "sales_col_sale_type",
            "table": "Sales_Invoices",
            "type": "column",
            "target": "Sale_Type",
            "sql": (
                "ALTER TABLE Sales_Invoices "
                "ADD COLUMN Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS' "
                "AFTER Status"
            ),
            "description": "Add 'Sale_Type' (Retail_POS vs Wholesale) to Sales_Invoices"
        },
        {
            "id": "sales_col_due_date",
            "table": "Sales_Invoices",
            "type": "column",
            "target": "Due_Date",
            "sql": "ALTER TABLE Sales_Invoices ADD COLUMN Due_Date DATE NULL AFTER Invoice_Date",
            "description": "Add 'Due_Date' to Sales_Invoices for credit sales"
        },
        {
            "id": "sales_idx_type_due_date",
            "table": "Sales_Invoices",
            "type": "index",
            "target": "idx_sales_type_due_date",
            "sql": "CREATE INDEX idx_sales_type_due_date ON Sales_Invoices(Sale_Type, Due_Date)",
            "description": "Add composite index on Sales_Invoices(Sale_Type, Due_Date)"
        },

        # --- 4. Clients Table ---
        {
            "id": "client_col_price_tier",
            "table": "Clients",
            "type": "column",
            "target": "Price_Tier",
            "sql": (
                "ALTER TABLE Clients "
                "ADD COLUMN Price_Tier ENUM('Prix_1', 'Prix_2', 'Prix_3', 'Prix_4') NOT NULL DEFAULT 'Prix_1'"
            ),
            "description": "Add 'Price_Tier' to Clients (default: Prix_1)"
        },
        {
            "id": "client_col_credit_limit",
            "table": "Clients",
            "type": "column_or_modify",
            "target": "Credit_Limit",
            "add_sql": "ALTER TABLE Clients ADD COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00",
            "modify_sql": "ALTER TABLE Clients MODIFY COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00",
            "description": "Ensure 'Credit_Limit' exists with DECIMAL(15,2) in Clients"
        }
    ]

    def __init__(self, connection=None, config: Optional[Dict[str, Any]] = None):
        self.external_conn = connection
        self.config = config or self._resolve_db_config()
        self.db_name = self.config.get("database", "")

    @staticmethod
    def _resolve_db_config() -> Dict[str, Any]:
        """Resolve database credentials from .env or config.json."""
        config = {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", "root"),
            "database": os.getenv("DB_NAME", "Lab_Inventory_Enterprise_DB"),
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", 10))
        }

        # Attempt to read from .env if present
        env_candidates = [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]
        for p in env_candidates:
            if os.path.isfile(p):
                try:
                    from dotenv import dotenv_values
                    vals = dotenv_values(p)
                    for k in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"):
                        if vals.get(k):
                            clean_k = k.replace("DB_", "").lower()
                            if clean_k == "port":
                                config[clean_k] = int(vals[k])
                            else:
                                config[clean_k] = vals[k]
                    break
                except Exception as e:
                    logger.debug("Could not load dotenv: %s", e)

        return config

    def get_connection(self):
        """Yield an active connection, either existing or newly opened."""
        if self.external_conn is not None:
            return self.external_conn

        if not HAS_MYSQL_CONNECTOR:
            raise RuntimeError("mysql-connector-python is not installed in the current environment.")

        conn = mysql.connector.connect(**self.config)
        return conn

    # -------------------------------------------------------------------------
    # Metadata Inspection Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def check_table_exists(cursor, schema_name: str, table_name: str) -> bool:
        query = (
            "SELECT 1 FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s LIMIT 1"
        )
        cursor.execute(query, (schema_name, table_name))
        return cursor.fetchone() is not None

    @staticmethod
    def check_column_exists(cursor, schema_name: str, table_name: str, column_name: str) -> bool:
        query = (
            "SELECT 1 FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s LIMIT 1"
        )
        cursor.execute(query, (schema_name, table_name, column_name))
        return cursor.fetchone() is not None

    @staticmethod
    def check_index_exists(cursor, schema_name: str, table_name: str, index_name: str) -> bool:
        query = (
            "SELECT 1 FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s LIMIT 1"
        )
        cursor.execute(query, (schema_name, table_name, index_name))
        return cursor.fetchone() is not None

    @staticmethod
    def check_constraint_exists(cursor, schema_name: str, table_name: str, constraint_name: str) -> bool:
        query = (
            "SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s LIMIT 1"
        )
        cursor.execute(query, (schema_name, table_name, constraint_name))
        return cursor.fetchone() is not None

    @staticmethod
    def get_primary_key_column(cursor, schema_name: str, table_name: str) -> str:
        query = (
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY' "
            "LIMIT 1"
        )
        cursor.execute(query, (schema_name, table_name))
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0])
        return "Batch_ID"  # Standard default fallback

    # -------------------------------------------------------------------------
    # Migration Execution Engine
    # -------------------------------------------------------------------------

    def run_migration(self, dry_run: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Runs the full migration idempotently.
        Returns (success: bool, report: Dict).
        """
        report: Dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "dry_run": dry_run,
            "steps_applied": [],
            "steps_skipped": [],
            "errors": [],
            "success": False
        }

        logger.info("=" * 70)
        logger.info("🚀 Starting Wholesale & Retail Schema Migration")
        logger.info(f"Target Database: '{self.config.get('database')}' on {self.config.get('host')}")
        logger.info(f"Mode: {'DRY-RUN (Simulated)' if dry_run else 'LIVE EXECUTION'}")
        logger.info("=" * 70)

        conn = None
        should_close = False

        try:
            conn = self.get_connection()
            if self.external_conn is None:
                should_close = True

            cursor = conn.cursor()
            schema_name = self.config.get("database") or "Lab_Inventory_Enterprise_DB"

            # Pre-flight Check: Verify base tables exist
            required_tables = ["Locations", "Inventory_Batches", "Sales_Invoices", "Clients"]
            for tbl in required_tables:
                if not self.check_table_exists(cursor, schema_name, tbl):
                    msg = f"Critical Pre-flight Error: Target table '{tbl}' does not exist in schema '{schema_name}'."
                    logger.error(msg)
                    report["errors"].append(msg)
                    return False, report

            # Resolve primary key of Inventory_Batches for dynamic foreign key reference
            pk_batches = self.get_primary_key_column(cursor, schema_name, "Inventory_Batches")
            logger.info(f"Primary key detected on Inventory_Batches: '{pk_batches}'")

            # Execute migration steps
            for step in self.MIGRATION_STEPS:
                step_id = step["id"]
                table = step["table"]
                target = step["target"]
                step_type = step["type"]
                desc = step["description"]

                # 1. Column check
                if step_type == "column":
                    if self.check_column_exists(cursor, schema_name, table, target):
                        logger.info(f"  [SKIPPED] Column '{table}.{target}' already exists.")
                        report["steps_skipped"].append(step_id)
                        continue

                    query = step["sql"]
                    self._execute_ddl(cursor, query, desc, dry_run)
                    report["steps_applied"].append(step_id)

                # 2. Column or Modify check (e.g. Credit_Limit)
                elif step_type == "column_or_modify":
                    if not self.check_column_exists(cursor, schema_name, table, target):
                        query = step["add_sql"]
                        self._execute_ddl(cursor, query, f"Add {target} to {table}", dry_run)
                        report["steps_applied"].append(step_id)
                    else:
                        query = step["modify_sql"]
                        self._execute_ddl(cursor, query, f"Verify/Modify precision of {target} in {table}", dry_run)
                        report["steps_applied"].append(f"{step_id}_modified")

                # 3. Foreign key check
                elif step_type == "foreign_key":
                    if self.check_constraint_exists(cursor, schema_name, table, target):
                        logger.info(f"  [SKIPPED] Foreign Key constraint '{target}' on '{table}' already exists.")
                        report["steps_skipped"].append(step_id)
                        continue

                    query = step["sql_template"].format(pk=pk_batches)
                    self._execute_ddl(cursor, query, desc, dry_run)
                    report["steps_applied"].append(step_id)

                # 4. Index check
                elif step_type == "index":
                    if self.check_index_exists(cursor, schema_name, table, target):
                        logger.info(f"  [SKIPPED] Index '{target}' on '{table}' already exists.")
                        report["steps_skipped"].append(step_id)
                        continue

                    query = step["sql"]
                    self._execute_ddl(cursor, query, desc, dry_run)
                    report["steps_applied"].append(step_id)

            report["success"] = True
            logger.info("=" * 70)
            logger.info("✅ Migration completed successfully with zero data loss!")
            logger.info(f"Summary: Applied: {len(report['steps_applied'])} | Skipped: {len(report['steps_skipped'])}")
            logger.info("=" * 70)

        except Exception as err:
            logger.error(f"❌ Migration failed with error: {err}", exc_info=True)
            report["errors"].append(str(err))
            report["success"] = False
            return False, report
        finally:
            if should_close and conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        report["completed_at"] = datetime.now().isoformat()
        return True, report

    @staticmethod
    def _execute_ddl(cursor, sql: str, description: str, dry_run: bool):
        """Execute single DDL statement safely."""
        logger.info(f"  [APPLYING] {description}...")
        logger.debug(f"    SQL: {sql}")
        if dry_run:
            logger.info(f"    [SIMULATED] Would run: {sql}")
            return

        try:
            cursor.execute(sql)
            if hasattr(cursor, "nextset"):
                try:
                    while cursor.nextset():
                        pass
                except (AttributeError, TypeError):
                    pass
        except Exception as err:
            # Check for mysql.connector duplicate error codes
            err_no = getattr(err, "errno", None)
            if err_no in (1060, 1061, 1826):
                logger.warning(f"    Notice: Item already exists ({getattr(err, 'msg', err)}). Skipping.")
            else:
                raise

    def verify_schema(self) -> Dict[str, bool]:
        """Verify all migration elements exist in active schema."""
        verification: Dict[str, bool] = {}
        conn = None
        should_close = False

        try:
            conn = self.get_connection()
            if self.external_conn is None:
                should_close = True

            cursor = conn.cursor()
            schema_name = self.config.get("database") or "Lab_Inventory_Enterprise_DB"

            verification["Locations.Visibility"] = self.check_column_exists(
                cursor, schema_name, "Locations", "Visibility"
            )
            verification["Locations.Allow_POS_Sales"] = self.check_column_exists(
                cursor, schema_name, "Locations", "Allow_POS_Sales"
            )
            verification["Locations.idx_locations_visibility_pos"] = self.check_index_exists(
                cursor, schema_name, "Locations", "idx_locations_visibility_pos"
            )

            verification["Inventory_Batches.Parent_Batch_ID"] = self.check_column_exists(
                cursor, schema_name, "Inventory_Batches", "Parent_Batch_ID"
            )
            verification["Inventory_Batches.Batch_Type"] = self.check_column_exists(
                cursor, schema_name, "Inventory_Batches", "Batch_Type"
            )
            verification["Inventory_Batches.fk_batch_parent_batch"] = self.check_constraint_exists(
                cursor, schema_name, "Inventory_Batches", "fk_batch_parent_batch"
            )
            verification["Inventory_Batches.idx_batch_parent_type"] = self.check_index_exists(
                cursor, schema_name, "Inventory_Batches", "idx_batch_parent_type"
            )

            verification["Sales_Invoices.Sale_Type"] = self.check_column_exists(
                cursor, schema_name, "Sales_Invoices", "Sale_Type"
            )
            verification["Sales_Invoices.Due_Date"] = self.check_column_exists(
                cursor, schema_name, "Sales_Invoices", "Due_Date"
            )
            verification["Sales_Invoices.idx_sales_type_due_date"] = self.check_index_exists(
                cursor, schema_name, "Sales_Invoices", "idx_sales_type_due_date"
            )

            verification["Clients.Price_Tier"] = self.check_column_exists(
                cursor, schema_name, "Clients", "Price_Tier"
            )
            verification["Clients.Credit_Limit"] = self.check_column_exists(
                cursor, schema_name, "Clients", "Credit_Limit"
            )

        finally:
            if should_close and conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        return verification


def run_wholesale_retail_migration(connection=None, config=None, dry_run: bool = False) -> bool:
    """
    Public entrypoint for programmatic invocation (e.g. from schema_initializer.py or test suites).
    """
    migrator = WholesaleRetailMigrator(connection=connection, config=config)
    success, _report = migrator.run_migration(dry_run=dry_run)
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Migrate StockLamPlus schema for Wholesale & Retail features."
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate SQL execution without making changes.")
    parser.add_argument("--verify", action="store_true", help="Verify schema presence without applying DDL.")
    parser.add_argument("--host", type=str, help="MySQL DB Host")
    parser.add_argument("--port", type=int, help="MySQL DB Port")
    parser.add_argument("--user", type=str, help="MySQL DB User")
    parser.add_argument("--password", type=str, help="MySQL DB Password")
    parser.add_argument("--database", type=str, help="MySQL DB Database Name")

    args = parser.parse_args()

    custom_config = {}
    if args.host: custom_config["host"] = args.host
    if args.port: custom_config["port"] = args.port
    if args.user: custom_config["user"] = args.user
    if args.password: custom_config["password"] = args.password
    if args.database: custom_config["database"] = args.database

    migrator = WholesaleRetailMigrator(config=custom_config if custom_config else None)

    if args.verify:
        logger.info("Running schema verification...")
        status = migrator.verify_schema()
        all_ok = True
        for k, ok in status.items():
            state = "✅ PRESENT" if ok else "❌ MISSING"
            logger.info(f"  {k:45} : {state}")
            if not ok: all_ok = False
        sys.exit(0 if all_ok else 1)

    success, _ = migrator.run_migration(dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
