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
from database.client_payment_manager import ClientPaymentManager
from ui.navigation_permissions import has_navigation_permission, has_permission

try:
    from PySide6.QtWidgets import QApplication
    from ui.widgets.sales.searchable_client_combo import SearchableClientComboBox
    HAS_QT = True
except (ImportError, RuntimeError):
    HAS_QT = False


class TestDebtsManagementBackend(unittest.TestCase):
    """
    Tests pour les méthodes de gestion des dettes, de réconciliation comptable (audit)
    et de règlements globaux FIFO / avances libres.
    """

    def setUp(self):
        self.mock_db = MagicMock()
        self.client_manager = ClientManager(self.mock_db)
        self.client_payment_manager = ClientPaymentManager(self.mock_db)

    def test_audit_client_debt_balance_balanced(self):
        """Vérifie que audit_client_debt_balance confirme l'équilibre lorsque Solde = Invoiced - Paid - CreditNotes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock responses for audit queries
        mock_cursor.fetchone.side_effect = [
            # 1. SELECT Client profile
            {'Client_ID': 10, 'Client_Name': 'Laboratoire Espoir', 'Credit_Limit': 100000.0, 'Price_Tier': 'Prix_3'},
            # 2. Total Invoiced
            {'total_invoiced': 50000.0, 'count_invoices': 5},
            # 3. Total POS Cash Payments
            {'pos_paid': 10000.0, 'count_pos_payments': 2},
            # 4. Total Client_Payments
            {'client_paid': 15000.0, 'count_client_payments': 3},
            # 5. Total Credit Notes
            {'total_credit_notes': 5000.0, 'count_credit_notes': 1},
            # For get_client_balance inside audit:
            {'Client_ID': 10, 'Client_Name': 'Laboratoire Espoir', 'Credit_Limit': 100000.0, 'Price_Tier': 'Prix_3'},
            {'total_invoiced': 50000.0},
            {'pos_paid': 10000.0},
            {'client_paid': 15000.0},
            {'total_cn': 5000.0}
        ]

        audit = self.client_manager.audit_client_debt_balance(10)

        self.assertTrue(audit['is_balanced'])
        self.assertEqual(audit['current_balance'], 20000.0)
        self.assertEqual(audit['expected_balance'], 20000.0)
        self.assertEqual(audit['discrepancy'], 0.0)
        self.assertEqual(audit['total_invoiced'], 50000.0)
        self.assertEqual(audit['total_paid'], 25000.0)
        self.assertEqual(audit['total_credit_notes'], 5000.0)

    def test_get_client_unpaid_invoices(self):
        """Vérifie la récupération des factures impayées et le calcul des jours de retard."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'Invoice_ID': 101,
                'Invoice_No': 'FAC-2026-001',
                'Invoice_Date': '2026-01-01',
                'Due_Date': '2026-01-31',
                'Sale_Type': 'Wholesale',
                'Status': 'Validated',
                'Total_Amount_TTC': 15000.0,
                'Paid_Amount': 5000.0,
                'Remaining_Balance': 10000.0
            }
        ]

        invoices = self.client_manager.get_client_unpaid_invoices(10)
        self.assertEqual(len(invoices), 1)
        inv = invoices[0]
        self.assertEqual(inv['Invoice_No'], 'FAC-2026-001')
        self.assertEqual(inv['Remaining_Balance'], 10000.0)
        self.assertTrue(inv['Is_Overdue'])
        self.assertGreater(inv['Days_Overdue'], 0)

    def test_add_global_payment_fifo_allocation(self):
        """Vérifie que add_global_payment en mode FIFO alloue le montant aux factures les plus anciennes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Client profile
        mock_cursor.fetchone.return_value = {'Client_ID': 10, 'Client_Name': 'Clinique Centrale'}

        # Unpaid invoices ordered by date ASC
        mock_cursor.fetchall.return_value = [
            {'Invoice_ID': 101, 'Invoice_No': 'FAC-101', 'Invoice_Date': '2026-01-01', 'Total_Amount_TTC': 10000.0, 'Paid_Amount': 0.0, 'Remaining': 10000.0},
            {'Invoice_ID': 102, 'Invoice_No': 'FAC-102', 'Invoice_Date': '2026-01-15', 'Total_Amount_TTC': 15000.0, 'Paid_Amount': 5000.0, 'Remaining': 10000.0},
        ]
        mock_cursor.lastrowid = 501

        # Pay 15,000 DA: should allocate 10,000 to FAC-101 (Paid), 5,000 to FAC-102 (Validated)
        res = self.client_payment_manager.add_global_payment(
            client_id=10,
            payment_date='2026-09-14',
            amount=15000.0,
            payment_method='Virement',
            auto_allocate_fifo=True
        )

        self.assertIsNotNone(res)
        self.assertTrue(res['success'])
        self.assertEqual(res['total_amount'], 15000.0)
        self.assertEqual(res['allocated_to_invoices'], 15000.0)
        self.assertEqual(res['free_advance'], 0.0)
        self.assertEqual(len(res['invoices_affected']), 2)

        # First invoice fully paid
        inv1 = res['invoices_affected'][0]
        self.assertEqual(inv1['invoice_id'], 101)
        self.assertEqual(inv1['allocated'], 10000.0)
        self.assertEqual(inv1['new_status'], 'Paid')

        # Second invoice partially paid
        inv2 = res['invoices_affected'][1]
        self.assertEqual(inv2['invoice_id'], 102)
        self.assertEqual(inv2['allocated'], 5000.0)
        self.assertEqual(inv2['new_status'], 'Validated')

    def test_add_global_payment_free_advance(self):
        """Vérifie que add_global_payment avec auto_allocate_fifo=False enregistre un acompte libre non lettré."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {'Client_ID': 10, 'Client_Name': 'Clinique Centrale'}
        mock_cursor.lastrowid = 601

        res = self.client_payment_manager.add_global_payment(
            client_id=10,
            payment_date='2026-09-14',
            amount=8000.0,
            payment_method='Chèque',
            auto_allocate_fifo=False
        )

        self.assertIsNotNone(res)
        self.assertTrue(res['success'])
        self.assertEqual(res['free_advance'], 8000.0)
        self.assertEqual(res['allocated_to_invoices'], 0.0)


class TestDebtsNavigationPermissions(unittest.TestCase):
    """Vérifie les permissions de navigation et d'encaissement pour la gestion des créances."""

    def test_nav_debts_fallback_to_nav_sales(self):
        user = {"Permissions": {"nav_sales": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_explicit_grant(self):
        user = {"Permissions": {"nav_debts": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_granular_view_grant(self):
        user = {"Permissions": {"debts_management:view": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_explicit_deny(self):
        user = {
            "Permissions": {
                "nav_sales": True,
                "nav_debts": False
            }
        }
        self.assertFalse(has_navigation_permission(user, "nav_debts"))


class TestSearchableClientComboBox(unittest.TestCase):
    """Tests unitaires du widget d'autocomplétion client par nom et par téléphone."""

    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    def test_searchable_client_combo_name_and_phone(self):
        if not HAS_QT:
            self.skipTest("PySide6 not available in headless test environment.")

        combo = SearchableClientComboBox()
        clients = [
            {'Client_ID': 1, 'Client_Name': 'Laboratoire Al-Amal', 'Phone': '0550123456'},
            {'Client_ID': 2, 'Client_Name': 'Clinique El-Chifa', 'Phone': '0661987654'},
            {'Client_ID': 3, 'Client_Name': 'Pharmacie Centrale', 'Phone': ''}
        ]
        combo.set_clients(clients)

        # 1. Default should be "Tous les Clients" with ID None
        self.assertEqual(combo.count(), 4)
        self.assertIsNone(combo.get_selected_client_id())

        # 2. Display formats
        self.assertEqual(combo.itemText(0), "Tous les Clients")
        self.assertEqual(combo.itemText(1), "Laboratoire Al-Amal (0550123456)")
        self.assertEqual(combo.itemText(2), "Clinique El-Chifa (0661987654)")
        self.assertEqual(combo.itemText(3), "Pharmacie Centrale")

        # 3. Select programmatically
        combo.set_selected_client_id(2)
        self.assertEqual(combo.get_selected_client_id(), 2)

        # 4. Search resolution by phone digits
        combo.setEditText("0550")
        resolved = combo._resolve_from_text()
        self.assertEqual(resolved, 1)

        # 5. Search resolution by client name text
        combo.setEditText("Chifa")
        resolved_name = combo._resolve_from_text()
        self.assertEqual(resolved_name, 2)


if __name__ == "__main__":
    unittest.main()
