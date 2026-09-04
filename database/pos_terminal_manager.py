# database/pos_terminal_manager.py

import logging
import os
import socket
from typing import Dict, Optional, Tuple


class POSTerminalManager:
    """Manage local POS terminal identity for multi-caisse sales."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_schema()

    def _ensure_schema(self):
        if POSTerminalManager._schema_checked:
            return
        queries = [
            """
            CREATE TABLE IF NOT EXISTS POS_Terminals (
                Terminal_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Terminal_Code VARCHAR(100) NOT NULL UNIQUE,
                Terminal_Name VARCHAR(150) NOT NULL,
                Is_Active BOOLEAN DEFAULT TRUE,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    cursor.execute(query)
                POSTerminalManager._schema_checked = True
        except Exception as e:
            logging.error(f"POS terminal schema check failed: {e}", exc_info=True)

    def get_default_terminal_code(self) -> str:
        configured = os.getenv("POS_TERMINAL_CODE")
        raw = configured or socket.gethostname() or "POS-DEFAULT"
        cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw.strip())
        return (cleaned or "POS-DEFAULT")[:100]

    def get_or_create_default_terminal(self) -> Optional[Dict]:
        code = self.get_default_terminal_code()
        name = os.getenv("POS_TERMINAL_NAME") or f"Caisse {code}"
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM POS_Terminals WHERE Terminal_Code = %s",
                    (code,),
                )
                terminal = cursor.fetchone()
                if terminal:
                    return terminal

                cursor.execute(
                    """
                    INSERT INTO POS_Terminals (Terminal_Code, Terminal_Name)
                    VALUES (%s, %s)
                    """,
                    (code, name[:150]),
                )
                terminal_id = cursor.lastrowid
                return {
                    "Terminal_ID": terminal_id,
                    "Terminal_Code": code,
                    "Terminal_Name": name[:150],
                    "Is_Active": True,
                }
        except Exception as e:
            logging.error(f"Could not get/create POS terminal: {e}", exc_info=True)
            return None

    def get_all_terminals(self, include_inactive: bool = True) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT t.*, 
                           COUNT(s.Cash_Session_ID) AS Total_Sessions,
                           SUM(CASE WHEN s.Status = 'Open' THEN 1 ELSE 0 END) AS Has_Open_Session
                    FROM POS_Terminals t
                    LEFT JOIN POS_Cash_Sessions s ON t.Terminal_ID = s.Terminal_ID
                """
                if not include_inactive:
                    query += " WHERE t.Is_Active = 1"
                query += " GROUP BY t.Terminal_ID ORDER BY t.Terminal_ID ASC"
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    cursor.execute("INSERT INTO POS_Terminals (Terminal_Code, Terminal_Name, Is_Active) VALUES ('CAISSE-01', 'Caisse Principale', 1)")
                    conn.commit()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                return rows
        except Exception as e:
            logging.error(f"Could not fetch all terminals: {e}", exc_info=True)
            return []

    def add_terminal(self, terminal_code: str, terminal_name: str, is_active: bool = True) -> Tuple[bool, str, Optional[int]]:
        code = str(terminal_code).strip().upper()
        name = str(terminal_name).strip()
        if not code or not name:
            return False, "Le code et le nom de la caisse sont obligatoires.", None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Terminal_ID FROM POS_Terminals WHERE Terminal_Code = %s", (code,))
                if cursor.fetchone():
                    return False, f"Une caisse avec le code '{code}' existe déjà.", None

                cursor.execute(
                    """
                    INSERT INTO POS_Terminals (Terminal_Code, Terminal_Name, Is_Active)
                    VALUES (%s, %s, %s)
                    """,
                    (code[:100], name[:150], 1 if is_active else 0),
                )
                conn.commit()
                return True, "Caisse ajoutée avec succès.", cursor.lastrowid
        except Exception as e:
            logging.error(f"Could not add terminal: {e}", exc_info=True)
            return False, f"Erreur base de données : {e}", None

    def update_terminal(self, terminal_id: int, terminal_code: str, terminal_name: str, is_active: bool = True) -> Tuple[bool, str]:
        code = str(terminal_code).strip().upper()
        name = str(terminal_name).strip()
        if not code or not name:
            return False, "Le code et le nom de la caisse sont obligatoires."

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT Terminal_ID FROM POS_Terminals WHERE Terminal_Code = %s AND Terminal_ID <> %s",
                    (code, terminal_id),
                )
                if cursor.fetchone():
                    return False, f"Une autre caisse utilise déjà le code '{code}'."

                cursor.execute(
                    """
                    UPDATE POS_Terminals
                    SET Terminal_Code = %s, Terminal_Name = %s, Is_Active = %s
                    WHERE Terminal_ID = %s
                    """,
                    (code[:100], name[:150], 1 if is_active else 0, terminal_id),
                )
                conn.commit()
                return True, "Caisse mise à jour avec succès."
        except Exception as e:
            logging.error(f"Could not update terminal: {e}", exc_info=True)
            return False, f"Erreur base de données : {e}"

    def delete_terminal(self, terminal_id: int) -> Tuple[bool, str]:
        """Supprime la caisse si aucune session n'est enregistrée, sinon propose sa désactivation."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM POS_Cash_Sessions WHERE Terminal_ID = %s",
                    (terminal_id,),
                )
                count = (cursor.fetchone() or {}).get("cnt", 0)
                if count > 0:
                    # Ne pas supprimer définitivement pour garder l'intégrité historique
                    cursor.execute("UPDATE POS_Terminals SET Is_Active = 0 WHERE Terminal_ID = %s", (terminal_id,))
                    conn.commit()
                    return True, f"La caisse possède {count} session(s) dans l'historique et a été désactivée au lieu d'être supprimée."

                cursor.execute("DELETE FROM POS_Terminals WHERE Terminal_ID = %s", (terminal_id,))
                conn.commit()
                return True, "Caisse supprimée avec succès."
        except Exception as e:
            logging.error(f"Could not delete terminal: {e}", exc_info=True)
            return False, f"Erreur base de données : {e}"

    def toggle_terminal_active(self, terminal_id: int) -> Tuple[bool, str, bool]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Is_Active FROM POS_Terminals WHERE Terminal_ID = %s", (terminal_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "Caisse introuvable.", False
                new_state = 0 if row.get("Is_Active") else 1
                cursor.execute("UPDATE POS_Terminals SET Is_Active = %s WHERE Terminal_ID = %s", (new_state, terminal_id))
                conn.commit()
                state_label = "activée" if new_state else "désactivée"
                return True, f"Caisse {state_label} avec succès.", bool(new_state)
        except Exception as e:
            logging.error(f"Could not toggle terminal active state: {e}", exc_info=True)
            return False, f"Erreur : {e}", False

