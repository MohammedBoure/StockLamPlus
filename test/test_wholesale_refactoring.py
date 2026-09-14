import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date, datetime

import sys
import types

# Ensure mocks for third-party DB connectors if not present
try:
    import mysql.connector
except ImportError:
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

from database.client_manager import ClientManager


class TestWholesaleAccountingSegregation(unittest.TestCase):
    """
    Vérifie la stricte ségrégation comptable des Devis et Bons de Commande brouillon
    qui ne doivent JAMAIS impacter la dette financière du client dans ClientManager.
    """

    def setUp(self):
        self.mock_db = MagicMock()
        self.client_manager = ClientManager(self.mock_db)

    def test_get_client_balance_excludes_draft_and_quotes(self):
        """get_client_balance must exclude Status in ('Cancelled', 'Draft') and DEV-%, BC-%."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock client profile
        mock_cursor.fetchone.side_effect = [
            {'Client_ID': 1, 'Client_Name': 'Grossiste Alpha', 'Credit_Limit': 50000.0, 'Price_Tier': 'Prix_3'},
            {'total_invoiced': 12000.0},  # Factures validées uniquement
            {'pos_paid': 2000.0},
            {'client_paid': 3000.0},
            {'total_cn': 1000.0}
        ]

        bal = self.client_manager.get_client_balance(1)

        self.assertEqual(bal['total_invoiced'], 12000.0)
        self.assertEqual(bal['total_paid'], 5000.0)
        self.assertEqual(bal['total_credit_notes'], 1000.0)
        self.assertEqual(bal['current_balance'], 6000.0)  # 12000 - 5000 - 1000
        self.assertEqual(bal['available_credit'], 44000.0)  # 50000 - 6000

        # Verify SQL query excludes Cancelled, Draft, DEV-%, BC-%
        executed_sqls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        self.assertTrue(any("NOT IN ('Cancelled', 'Draft')" in q and "NOT LIKE 'DEV-%'" in q for q in executed_sqls))

    def test_get_client_ledger_segregates_non_binding_documents(self):
        """get_client_ledger sets debit = 0.00 and is_non_binding = True for Devis and BCs."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            'Client_ID': 1, 'Client_Name': 'Client B2B Test', 'Credit_Limit': 100000.0, 'Price_Tier': 'Prix_2'
        }

        # Return 1 validated invoice and 1 quote (Devis) and 1 draft order (BC)
        mock_cursor.fetchall.side_effect = [
            [
                {
                    'Invoice_ID': 101, 'Invoice_No': 'FAC-2026-001', 'op_date': '2026-09-01',
                    'Total_Amount_TTC': 15000.0, 'Sale_Type': 'Wholesale', 'Status': 'Validated'
                },
                {
                    'Invoice_ID': 102, 'Invoice_No': 'DEV-2026-001', 'op_date': '2026-09-05',
                    'Total_Amount_TTC': 80000.0, 'Sale_Type': 'Wholesale', 'Status': 'Draft'
                },
                {
                    'Invoice_ID': 103, 'Invoice_No': 'BC-2026-001', 'op_date': '2026-09-10',
                    'Total_Amount_TTC': 45000.0, 'Sale_Type': 'Wholesale', 'Status': 'Draft'
                }
            ],
            [],  # pos payments
            [],  # client payments
            []   # credit notes
        ]

        ledger = self.client_manager.get_client_ledger(1)
        txs = ledger['transactions']

        self.assertEqual(len(txs), 3)

        # FAC
        self.assertEqual(txs[0]['reference'], 'FAC-2026-001')
        self.assertEqual(txs[0]['debit'], 15000.0)
        self.assertFalse(txs[0]['is_non_binding'])
        self.assertEqual(txs[0]['balance'], 15000.0)

        # DEV (Quote): debit must be 0.00, balance unchanged
        self.assertEqual(txs[1]['reference'], 'DEV-2026-001')
        self.assertEqual(txs[1]['debit'], 0.0)
        self.assertTrue(txs[1]['is_non_binding'])
        self.assertEqual(txs[1]['balance'], 15000.0)
        self.assertIn("Hors bilan", txs[1]['notes'])

        # BC (Order): debit must be 0.00, balance unchanged
        self.assertEqual(txs[2]['reference'], 'BC-2026-001')
        self.assertEqual(txs[2]['debit'], 0.0)
        self.assertTrue(txs[2]['is_non_binding'])
        self.assertEqual(txs[2]['balance'], 15000.0)
        self.assertIn("Hors bilan", txs[2]['notes'])

        self.assertEqual(ledger['final_balance'], 15000.0)


try:
    from PySide6.QtWidgets import QApplication
    from ui.widgets.wholesale_sales.wholesale_sales_tab import WholesaleSalesTab
    HAS_QT = True
except ImportError:
    HAS_QT = False


class TestWholesaleBusinessLogic(unittest.TestCase):
    """
    Tests unitaires sur la résolution tarifaire, la détection des dépassements de crédit
    et les règles métier de vente en gros.
    """

    def test_price_tier_resolution(self):
        if not HAS_QT:
            self.skipTest("PySide6 not available in this test runner environment")

        tab = WholesaleSalesTab.__new__(WholesaleSalesTab)

        batch = {
            'Selling_Price_HT': 100.0,
            'Selling_Price_HT_2': 90.0,
            'Selling_Price_HT_3': 80.0,
            'Selling_Price_HT_4': 70.0
        }

        self.assertEqual(tab._resolve_price_tier(batch, 'Prix_1'), 100.0)
        self.assertEqual(tab._resolve_price_tier(batch, 'Prix_2'), 90.0)
        self.assertEqual(tab._resolve_price_tier(batch, 'Prix_3'), 80.0)
        self.assertEqual(tab._resolve_price_tier(batch, 'Prix_4'), 70.0)

        # Fallback if tier 4 is null
        batch_fallback = {
            'Selling_Price_HT': 100.0,
            'Selling_Price_HT_2': 90.0,
            'Selling_Price_HT_3': None,
            'Selling_Price_HT_4': None
        }
        self.assertEqual(tab._resolve_price_tier(batch_fallback, 'Prix_4'), 90.0)


if __name__ == '__main__':
    unittest.main()
