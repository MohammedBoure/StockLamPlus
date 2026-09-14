import unittest
from unittest.mock import MagicMock
from tools.migrate_wholesale_retail_schema import WholesaleRetailMigrator, run_wholesale_retail_migration

class TestWholesaleRetailMigration(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.nextset.return_value = False
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.migrator = WholesaleRetailMigrator(
            connection=self.mock_conn,
            config={"database": "test_db", "host": "localhost"}
        )

    def test_check_table_exists(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.assertTrue(WholesaleRetailMigrator.check_table_exists(self.mock_cursor, "test_db", "Locations"))
        self.mock_cursor.fetchone.return_value = None
        self.assertFalse(WholesaleRetailMigrator.check_table_exists(self.mock_cursor, "test_db", "NonExistent"))

    def test_check_column_exists(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.assertTrue(WholesaleRetailMigrator.check_column_exists(self.mock_cursor, "test_db", "Locations", "Visibility"))
        self.mock_cursor.fetchone.return_value = None
        self.assertFalse(WholesaleRetailMigrator.check_column_exists(self.mock_cursor, "test_db", "Locations", "Foo"))

    def test_check_index_exists(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.assertTrue(WholesaleRetailMigrator.check_index_exists(self.mock_cursor, "test_db", "Locations", "idx_locations_visibility_pos"))

    def test_check_constraint_exists(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.assertTrue(WholesaleRetailMigrator.check_constraint_exists(self.mock_cursor, "test_db", "Inventory_Batches", "fk_batch_parent_batch"))

    def test_get_primary_key_column(self):
        self.mock_cursor.fetchone.return_value = ("Batch_ID",)
        pk = WholesaleRetailMigrator.get_primary_key_column(self.mock_cursor, "test_db", "Inventory_Batches")
        self.assertEqual(pk, "Batch_ID")

    def test_run_migration_all_new(self):
        # Tables exist
        # Table exists checks return True
        # Columns/indexes/constraints do NOT exist initially
        def mock_fetchone_side_effect():
            # Will be called sequentially
            return None

        def mock_table_or_col(*args, **kwargs):
            if self.mock_cursor.execute.call_args:
                query = self.mock_cursor.execute.call_args[0][0]
                if "information_schema.TABLES" in query:
                    return (1,)
                if "information_schema.KEY_COLUMN_USAGE" in query:
                    return ("Batch_ID",)
            return None

        self.mock_cursor.fetchone.side_effect = mock_table_or_col

        success, report = self.migrator.run_migration(dry_run=False)
        self.assertTrue(success)
        self.assertEqual(len(report["steps_applied"]), len(WholesaleRetailMigrator.MIGRATION_STEPS))
        self.assertEqual(len(report["steps_skipped"]), 0)

    def test_run_migration_idempotent_skip_existing(self):
        # All tables, columns, indexes, constraints already exist
        self.mock_cursor.fetchone.return_value = (1,)
        self.migrator.get_primary_key_column = MagicMock(return_value="Batch_ID")

        success, report = self.migrator.run_migration(dry_run=False)
        self.assertTrue(success)
        self.assertGreater(len(report["steps_skipped"]), 0)

    def test_run_wholesale_retail_migration_entrypoint(self):
        self.mock_cursor.fetchone.return_value = (1,)
        self.migrator.get_primary_key_column = MagicMock(return_value="Batch_ID")
        success = run_wholesale_retail_migration(connection=self.mock_conn, config={"database": "test_db"}, dry_run=True)
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
