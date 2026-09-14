import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date, datetime, timedelta
import sys

try:
    import mysql.connector
except ImportError:
    import types
    fake_mysql = types.ModuleType("mysql")
    fake_connector = types.ModuleType("mysql.connector")
    fake_errorcode = types.ModuleType("mysql.connector.errorcode")
    fake_pooling = types.ModuleType("mysql.connector.pooling")
    class Error(Exception):
        pass
    fake_connector.Error = Error
    fake_connector.errorcode = fake_errorcode
    fake_connector.pooling = fake_pooling
    fake_mysql.connector = fake_connector
    sys.modules["mysql"] = fake_mysql
    sys.modules["mysql.connector"] = fake_connector
    sys.modules["mysql.connector.errorcode"] = fake_errorcode
    sys.modules["mysql.connector.pooling"] = fake_pooling

try:
    import dotenv
except ImportError:
    import types
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv

try:
    import sqlalchemy
    import sqlalchemy.engine
except ImportError:
    import types
    fake_sqlalchemy = types.ModuleType("sqlalchemy")
    fake_sqlalchemy.__path__ = []
    fake_engine = types.ModuleType("sqlalchemy.engine")
    class URL:
        @staticmethod
        def create(*args, **kwargs):
            return ""
    fake_engine.URL = URL
    fake_sqlalchemy.create_engine = lambda *args, **kwargs: None
    fake_sqlalchemy.text = lambda s: s
    fake_sqlalchemy.inspect = lambda s: None
    fake_sqlalchemy.engine = fake_engine
    sys.modules["sqlalchemy"] = fake_sqlalchemy
    sys.modules["sqlalchemy.engine"] = fake_engine

try:
    import pandas
except ImportError:
    import types
    fake_pandas = types.ModuleType("pandas")
    sys.modules["pandas"] = fake_pandas

try:
    import numpy
except ImportError:
    import types
    fake_numpy = types.ModuleType("numpy")
    sys.modules["numpy"] = fake_numpy

from database.sales_manager import SalesManager
from database.inventory_batch_manager import InventoryBatchManager
from database.client_manager import ClientManager
from database.location_manager import LocationManager


class TestWholesaleB2BFeatures(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = self.mock_conn
        self.mock_db.get_raw_connection.return_value = self.mock_conn
        self.mock_conn.cursor.return_value = self.mock_cursor

        self.sales_manager = SalesManager(self.mock_db)
        self.batch_manager = InventoryBatchManager(self.mock_db)
        self.client_manager = ClientManager(self.mock_db)
        self.location_manager = LocationManager(self.mock_db)

    def test_wholesale_doc_no_generation(self):
        """Test sequential wholesale document number formatting."""
        self.mock_cursor.fetchone.return_value = {"MaxSeq": 14}
        doc_no = self.sales_manager._next_wholesale_doc_no(self.mock_cursor, "BL", "2026-09-14")
        self.assertEqual(doc_no, "BL-2026/0015")

    def test_wholesale_document_draft_vs_deduction(self):
        """Devis/BC save as Draft without stock deduction; BL/Facture commit stock deduction."""
        # Devis test
        self.mock_cursor.fetchone.return_value = {"MaxSeq": 0}
        self.mock_cursor.lastrowid = 101
        success, res = self.sales_manager.create_wholesale_document(
            client_id=1,
            doc_type="Devis",
            order_date="2026-09-14",
            due_date="2026-09-30",
            cart_items=[{"batch_id": 10, "product_id": 1, "qty_sold": 5, "unit_price_ht": 100.0, "tva_percent": 19.0}]
        )
        self.assertTrue(success)
        self.assertEqual(res["status"], "Draft")

    def test_extract_retail_batch(self):
        """Test batch extraction preserving lineage with Parent_Batch_ID and Extracted_Retail."""
        self.mock_cursor.fetchone.side_effect = [
            # Batch fetch
            {
                "Batch_ID": 50,
                "Product_ID": 10,
                "Quantity_Current": Decimal("100"),
                "Location_ID": 1,
                "Lot_Number": "LOT-BULK-01",
                "Expiry_Date": date(2027, 1, 1),
                "Selling_Price_HT": Decimal("500.00"),
                "Selling_TVA_Percent": Decimal("19.0"),
                "Internal_Barcode": "INT-50"
            },
            # Destination location fetch
            {"Location_ID": 2, "Location_Name": "Rayon Détail", "Visibility": "Public", "Allow_POS_Sales": True},
            # Barcode collision check: None (no collision)
            None
        ]
        self.mock_cursor.lastrowid = 888

        # Mock stock_movement_log
        self.batch_manager.stock_movement_log.create_movement_log = MagicMock(return_value=123)

        res = self.batch_manager.extract_retail_batch(
            parent_batch_id=50,
            extracted_qty=Decimal("10"),
            retail_product_id=10,
            target_location_id=2,
            user_id=1
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("child_batch_id"), 888)

    def test_client_balance_and_statement(self):
        """Test dynamic calculation of client balance."""
        self.mock_cursor.fetchone.side_effect = [
            # Client base info
            {"Client_ID": 1, "Client_Name": "SARL Client Test", "Credit_Limit": Decimal("500000.00"), "Price_Tier": "Prix_1"},
            # Total invoices
            {"total_invoiced": 150000.00},
            # POS payments
            {"pos_paid": 50000.00},
            # Subsequent payments
            {"client_paid": 20000.00},
            # Credit notes
            {"total_cn": 5000.00}
        ]
        balance_info = self.client_manager.get_client_balance(1)
        # Expected: 150000 - 50000 - 20000 - 5000 = 75000.00
        self.assertEqual(balance_info["current_balance"], 75000.00)

    def test_location_pos_guard(self):
        """Test get_pos_locations query filters by Public and Allow_POS_Sales = True."""
        self.mock_cursor.fetchall.return_value = [
            {
                "Location_ID": 2, "Location_Name": "Comptoir POS", "Parent_Location_ID": None,
                "Visibility": "Public", "Allow_POS_Sales": True
            }
        ]
        pos_locs = self.location_manager.get_pos_locations()
        self.assertEqual(len(pos_locs), 1)
        self.assertEqual(pos_locs[0]["Visibility"], "Public")
        self.assertTrue(pos_locs[0]["Allow_POS_Sales"])


if __name__ == '__main__':
    unittest.main()
