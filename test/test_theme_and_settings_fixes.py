import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

# Assurer l'existence d'une instance QApplication pour les widgets Qt
app = QApplication.instance() or QApplication([])

from ui.widgets.settings.lab_info_tab import LabInfoTab
from ui.widgets.settings.auto_backup_tab import AutoBackupTab
from ui.widgets.settings.settings_tab import SettingsTab
from ui.navigation_permissions import has_navigation_permission, has_permission, NAVIGATION_PERMISSION_FALLBACKS
from ui.widgets.inventory.tabs_dispatch import DispatchTab
from ui.widgets.procurement.procurement_tabs import PurchaseOrdersTab


class ThemeAndSettingsFixesTests(unittest.TestCase):
    def test_lab_info_tab(self):
        settings = {
            "lab_name": "Test Lab",
            "lab_address": "123 Test St",
            "lab_nif": "000123456789",
            "lab_rc": "987654321",
        }
        tab = LabInfoTab(settings)
        self.assertEqual(tab.txt_lab_name.text(), "Test Lab")
        self.assertEqual(tab.txt_lab_address.text(), "123 Test St")
        self.assertEqual(tab.txt_lab_nif.text(), "000123456789")
        self.assertEqual(tab.txt_lab_rc.text(), "987654321")

        tab.txt_lab_name.setText("Updated Lab")
        res = tab.get_settings()
        self.assertEqual(res["lab_name"], "Updated Lab")
        self.assertEqual(res["lab_address"], "123 Test St")

    def test_auto_backup_tab(self):
        settings = {
            "auto_backup_enabled": True,
            "auto_backup_interval": 45.0,
            "auto_backup_password": "secret_password",
            "auto_backup_max_files": 10,
            "backup_paths": ["C:/Backups"],
        }
        mock_dm = MagicMock()
        tab = AutoBackupTab(settings=settings, data_manager=mock_dm)
        self.assertTrue(tab.chk_auto_backup.isChecked())
        self.assertEqual(tab.spin_auto_interval.value(), 45.0)
        self.assertEqual(tab.txt_auto_pwd.text(), "secret_password")
        self.assertEqual(tab.spin_max_backups.value(), 10)
        self.assertEqual(tab.list_backup_paths.count(), 1)
        self.assertEqual(tab.list_backup_paths.item(0).text(), "C:/Backups")

        tab.spin_auto_interval.setValue(90.0)
        res = tab.get_settings()
        self.assertEqual(res["auto_backup_interval"], 90.0)
        self.assertTrue(res["auto_backup_enabled"])
        self.assertEqual(res["auto_backup_max_files"], 10)

    def test_settings_tab_tabs_separation_and_compatibility(self):
        mock_dm = MagicMock()
        mock_dm.current_user = {"Username": "admin"}
        mock_dm.templates.get_all_templates.return_value = []
        mock_dm.templates.get_active_template_name.return_value = ""
        mock_dm.templates.get_active_template.return_value = None
        mock_dm.templates.get_template_by_name.return_value = None
        mock_dm.printer.config = {"active_label_template": "Standard"}
        mock_dm.receipt_templates.get_all_templates.return_value = []
        mock_dm.receipt_templates.get_active_template_name.return_value = ""
        mock_dm.receipt_templates.get_template.return_value = None
        mock_store = MagicMock()
        mock_store.general_path = "mock_config.json"
        mock_store.load_general.return_value = {
            "lab_name": "Lab Alpha",
            "auto_backup_enabled": True,
        }

        tab = SettingsTab(mock_dm, local_store=mock_store)
        self.assertIsInstance(tab.tab_lab_info, LabInfoTab)
        self.assertIsInstance(tab.tab_auto_backup, AutoBackupTab)
        self.assertIs(tab.tab_general, tab.tab_lab_info)

        # Vérifier l'accès rétrocompatible aux propriétés
        self.assertEqual(tab.txt_lab_name.text(), "Lab Alpha")
        self.assertTrue(tab.chk_auto_backup.isChecked())

        # Vérifier que les anciennes alertes ne sont plus dans l'interface
        self.assertFalse(hasattr(tab, "spin_expiry"))
        self.assertFalse(hasattr(tab, "spin_stock"))
        self.assertFalse(hasattr(tab, "grp_view_mode"))
        self.assertFalse(hasattr(tab, "perform_archive_logs"))
        self.assertFalse(hasattr(tab, "toggle_archive_view"))

    def test_navigation_permissions_includes_tab_auto_backup(self):
        self.assertIn("tab_auto_backup", NAVIGATION_PERMISSION_FALLBACKS["nav_settings"])

        user = {"Permissions": {"tab_auto_backup": True}}
        self.assertTrue(has_navigation_permission(user, "nav_settings"))
        self.assertTrue(has_permission(user, "tab_auto_backup"))

    def test_dispatch_tab_barcode_no_dot_emoji(self):
        mock_dm = MagicMock()
        mock_dm.db = MagicMock()
        mock_dm.db.get_db_connection = MagicMock()
        mock_dm.locations = MagicMock()
        mock_dm.locations.get_all_locations.return_value = []

        tab = DispatchTab(mock_dm)
        placeholder = tab.barcode_input.placeholderText()
        self.assertNotIn("🔴", placeholder)
        self.assertIn("Scannez", placeholder)

    def test_procurement_date_fields_not_cropped(self):
        mock_dm = MagicMock()
        mock_dm.po = MagicMock()
        mock_dm.po.get_all_orders.return_value = []

        tab = PurchaseOrdersTab(mock_dm)
        self.assertGreaterEqual(tab.date_from.width(), 140)
        self.assertGreaterEqual(tab.date_to.width(), 140)


if __name__ == "__main__":
    unittest.main()
