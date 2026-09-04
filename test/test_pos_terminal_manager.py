import unittest
from unittest.mock import MagicMock
from database.pos_terminal_manager import POSTerminalManager


class TestPOSTerminalManager(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.conn = MagicMock()
        self.cursor = MagicMock()
        self.db.get_db_connection.return_value.__enter__.return_value = self.conn
        self.conn.cursor.return_value = self.cursor
        self.manager = POSTerminalManager(self.db)

    def test_add_terminal_success(self):
        # First check exists returns None
        self.cursor.fetchone.return_value = None
        self.cursor.lastrowid = 12

        success, msg, term_id = self.manager.add_terminal("CAISSE-02", "Caisse Étage", True)
        self.assertTrue(success)
        self.assertEqual(term_id, 12)
        self.conn.commit.assert_called()

    def test_add_terminal_duplicate(self):
        self.cursor.fetchone.return_value = {"Terminal_ID": 1}

        success, msg, term_id = self.manager.add_terminal("CAISSE-01", "Caisse Principale")
        self.assertFalse(success)
        self.assertIn("existe déjà", msg)

    def test_delete_terminal_with_sessions_deactivates_instead(self):
        # 3 sessions exist
        self.cursor.fetchone.return_value = {"cnt": 3}

        success, msg = self.manager.delete_terminal(1)
        self.assertTrue(success)
        self.assertIn("désactivée au lieu d'être supprimée", msg)
        self.conn.commit.assert_called()


if __name__ == "__main__":
    unittest.main()
