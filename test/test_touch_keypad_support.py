import os
import unittest
from unittest.mock import MagicMock
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTableWidgetItem, QDoubleSpinBox
    from PySide6.QtCore import Qt
    from ui.widgets.sales.touch_keypad import TouchKeypadDialog
    from ui.widgets.wholesale_sales.wholesale_sales_tab import WholesaleSalesTab
    HAS_QT = True
except ImportError:
    HAS_QT = False


class TestTouchKeypadSupport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])
        else:
            cls.app = None

    def setUp(self):
        if not HAS_QT:
            self.skipTest("PySide6 not available in this environment")

        self.mock_dm = MagicMock()
        self.mock_dm.clients.get_all_clients_with_balances.return_value = [
            {
                "Client_ID": 1,
                "Client_Name": "Pharmacie Centrale",
                "City": "Alger",
                "Price_Tier": "Prix_2",
                "Credit_Limit": 500000.0,
                "Current_Balance": 10000.0,
            }
        ]
        self.mock_dm.batches.get_all_batches_with_details.return_value = [
            {
                "Batch_ID": 10,
                "Product_ID": 101,
                "Product_Name": "Paracétamol 500mg",
                "Internal_Barcode": "61300001",
                "External_Barcode": "61300002",
                "Lot_Number": "LOT-2026-A",
                "Expiry_Date": "2027-12-31",
                "Location_Name": "Entrepôt Principal",
                "Quantity_Current": 150.0,
                "Selling_Price_HT": 120.0,
                "Selling_Price_HT_2": 110.0,
                "Selling_Price_HT_3": 105.0,
                "Selling_Price_HT_4": 100.0,
                "Selling_TVA_Percent": 19.0,
            }
        ]

    def test_touch_keypad_standalone(self):
        """Test that TouchKeypadDialog initializes properly with zero focus stealing."""
        keypad = TouchKeypadDialog(parent=None)
        self.assertEqual(keypad.focusPolicy(), Qt.NoFocus)
        self.assertTrue(keypad.testAttribute(Qt.WA_ShowWithoutActivating))
        self.assertEqual(keypad.stacked_pages.currentIndex(), 0)
        self.assertEqual(keypad.width(), 330)

        # Mode switching
        keypad.switch_to_letters()
        self.assertEqual(keypad.stacked_pages.currentIndex(), 1)
        self.assertEqual(keypad.width(), 520)

        keypad.switch_to_numpad()
        self.assertEqual(keypad.stacked_pages.currentIndex(), 0)
        self.assertEqual(keypad.width(), 330)

        # Layout toggle
        self.assertEqual(keypad.keyboard_layout_mode, "AZERTY")
        keypad.toggle_azerty_qwerty()
        self.assertEqual(keypad.keyboard_layout_mode, "QWERTY")
        keypad.toggle_azerty_qwerty()
        self.assertEqual(keypad.keyboard_layout_mode, "AZERTY")

    def test_wholesale_touch_support_and_keypad(self):
        """Test touch support and virtual keypad integration in WholesaleSalesTab."""
        tab = WholesaleSalesTab(self.mock_dm)

        # 1. Check touch ergonomics in Wholesale UI
        self.assertEqual(tab.cart_table.verticalHeader().defaultSectionSize(), 44)
        self.assertTrue(hasattr(tab, 'btn_keypad'))
        self.assertTrue(hasattr(tab, 'btn_keypad_search'))
        self.assertEqual(tab.btn_keypad.text(), "🔢 Pavé Tactile")
        self.assertEqual(tab.btn_keypad_search.text(), "🔢")

        # 2. Toggle touch keypad
        self.assertIsNone(tab.touch_keypad)
        tab.toggle_touch_keypad()
        self.assertIsNotNone(tab.touch_keypad)
        self.assertTrue(tab.touch_keypad.isVisible())

        # 3. Test focus actions with keypad
        keypad = tab.touch_keypad

        # Search focus
        keypad.focus_search()
        self.assertEqual(keypad.last_target_widget, tab.search_input)

        # Client focus
        keypad.focus_client()
        expected_client_target = tab.cb_client.lineEdit() or tab.cb_client
        self.assertEqual(keypad.last_target_widget, expected_client_target)

        # Qty focus with empty cart -> targets spin_quick_qty
        keypad.focus_qty()
        expected_qty_target = tab.spin_quick_qty.lineEdit() or tab.spin_quick_qty
        self.assertEqual(keypad.last_target_widget, expected_qty_target)

        # 4. Add item to cart and test row actions
        batch = self.mock_dm.batches.get_all_batches_with_details.return_value[0]
        tab.add_batch_to_cart(batch, qty=5.0)
        self.assertEqual(tab.cart_table.rowCount(), 1)

        # Focus cart row quantity
        keypad.focus_qty()
        qty_spin = tab.cart_table.cellWidget(0, 9)
        self.assertIsInstance(qty_spin, QDoubleSpinBox)
        self.assertEqual(qty_spin.value(), 5.0)

        # Adjust quantity (+1.0)
        keypad.adjust_active_qty(1.0)
        self.assertEqual(qty_spin.value(), 6.0)

        # Adjust quantity (-1.0)
        keypad.adjust_active_qty(-1.0)
        self.assertEqual(qty_spin.value(), 5.0)

        # Focus price
        keypad.focus_price()
        price_spin = tab.cart_table.cellWidget(0, 7)
        self.assertIsInstance(price_spin, QDoubleSpinBox)
        self.assertEqual(price_spin.value(), 110.0)  # Prix_2 for Pharmacie Centrale

        # Focus remise
        keypad.focus_remise()
        remise_spin = tab.cart_table.cellWidget(0, 10)
        self.assertIsInstance(remise_spin, QDoubleSpinBox)
        self.assertEqual(remise_spin.value(), 0.0)

        # Delete row via keypad
        keypad.delete_active_cart_row()
        self.assertEqual(tab.cart_table.rowCount(), 0)

        # Clean up
        tab.touch_keypad.hide()

    def test_pos_parent_compatibility(self):
        """Test that TouchKeypadDialog maintains 100% backward compatibility with POS tab mock."""
        mock_pos = MagicMock()
        mock_pos.cart_table.rowCount.return_value = 1
        mock_pos.cart_table.currentRow.return_value = 0
        mock_pos.cart_table.columnCount.return_value = 11

        mock_header_search = MagicMock()
        mock_header_search.text.return_value = "Produit"
        mock_header_qty = MagicMock()
        mock_header_qty.text.return_value = "Qté vendue"
        mock_header_price = MagicMock()
        mock_header_price.text.return_value = "Prix HT"
        mock_header_remise = MagicMock()
        mock_header_remise.text.return_value = "Remise"

        def get_header_item(col):
            mapping = {1: mock_header_search, 2: mock_header_qty, 3: mock_header_price, 4: mock_header_remise}
            return mapping.get(col, None)

        mock_pos.cart_table.horizontalHeaderItem.side_effect = get_header_item

        mock_qty_widget = MagicMock(spec=QDoubleSpinBox)
        mock_qty_widget.value.return_value = 2.0
        mock_qty_widget.minimum.return_value = 0.01
        mock_qty_widget.maximum.return_value = 999.0
        mock_pos.cart_table.cellWidget.return_value = mock_qty_widget

        keypad = TouchKeypadDialog(parent=None)
        keypad.pos_tab = mock_pos
        self.assertEqual(keypad._find_cart_column(["qté", "quantité"]), 2)
        self.assertEqual(keypad._find_cart_column(["prix"]), 3)
        self.assertEqual(keypad._find_cart_column(["remise"]), 4)


if __name__ == "__main__":
    unittest.main()
