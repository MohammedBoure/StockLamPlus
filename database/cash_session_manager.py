# database/cash_session_manager.py

import logging
from datetime import date
from typing import Dict, Optional, Tuple


class CashSessionManager:
    """Open/close POS cash sessions and summarize session takings."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_schema()

    def _ensure_schema(self):
        if CashSessionManager._schema_checked:
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
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Cash_Sessions (
                Cash_Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Session_No VARCHAR(100) NOT NULL UNIQUE,
                Terminal_ID INT UNSIGNED NOT NULL,
                Opened_By INT UNSIGNED NULL,
                Closed_By INT UNSIGNED NULL,
                Status ENUM('Open', 'Closed', 'Cancelled') NOT NULL DEFAULT 'Open',
                Opening_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Cash DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Card DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Transfer DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Counted_Cash DECIMAL(15, 2) NULL,
                Cash_Difference DECIMAL(15, 2) NULL,
                Notes TEXT NULL,
                Opened_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                Closed_At DATETIME NULL,
                Next_Invoice_Seq INT UNSIGNED NOT NULL DEFAULT 1,
                FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Opened_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
                FOREIGN KEY (Closed_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    cursor.execute(query)
                CashSessionManager._schema_checked = True
        except Exception as e:
            logging.error(f"Cash session schema check failed: {e}", exc_info=True)

    def get_open_session(self, terminal_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT s.*, t.Terminal_Code, t.Terminal_Name
                    FROM POS_Cash_Sessions s
                    JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    WHERE s.Terminal_ID = %s AND s.Status = 'Open'
                    ORDER BY s.Opened_At DESC
                    LIMIT 1
                    """,
                    (terminal_id,),
                )
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Could not fetch open cash session: {e}", exc_info=True)
            return None

    def get_terminals(self) -> list:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM POS_Terminals WHERE Is_Active = 1 ORDER BY Terminal_ID ASC")
                rows = cursor.fetchall()
                if not rows:
                    cursor.execute("INSERT INTO POS_Terminals (Terminal_Code, Terminal_Name, Is_Active) VALUES ('CAISSE-01', 'Caisse Principale', 1)")
                    conn.commit()
                    cursor.execute("SELECT * FROM POS_Terminals WHERE Is_Active = 1 ORDER BY Terminal_ID ASC")
                    rows = cursor.fetchall()
                return rows
        except Exception as e:
            logging.error(f"Could not fetch terminals: {e}", exc_info=True)
            return []

    def get_any_open_session(self, user_id=None) -> Optional[Dict]:
        """Récupère la session ouverte la plus récente, optionnellement pour cet utilisateur."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if user_id:
                    cursor.execute(
                        """
                        SELECT s.*, t.Terminal_Code, t.Terminal_Name
                        FROM POS_Cash_Sessions s
                        JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                        WHERE s.Status = 'Open' AND s.Opened_By = %s
                        ORDER BY s.Opened_At DESC
                        LIMIT 1
                        """,
                        (user_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        return row

                cursor.execute(
                    """
                    SELECT s.*, t.Terminal_Code, t.Terminal_Name
                    FROM POS_Cash_Sessions s
                    JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    WHERE s.Status = 'Open'
                    ORDER BY s.Opened_At DESC
                    LIMIT 1
                    """
                )
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Could not fetch any open cash session: {e}", exc_info=True)
            return None

    def open_session(self, terminal_id: int, user_id: Optional[int], opening_amount=0.0, notes=None) -> Tuple[bool, Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT * FROM POS_Cash_Sessions
                    WHERE Terminal_ID = %s AND Status = 'Open'
                    ORDER BY Opened_At DESC
                    LIMIT 1
                    """,
                    (terminal_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    return True, existing

                today = date.today().strftime("%Y%m%d")
                cursor.execute(
                    """
                    SELECT COUNT(*) AS Cnt
                    FROM POS_Cash_Sessions
                    WHERE Terminal_ID = %s AND DATE(Opened_At) = CURDATE()
                    """,
                    (terminal_id,),
                )
                count_row = cursor.fetchone() or {}
                seq = int(count_row.get("Cnt") or 0) + 1
                session_no = f"CS-{int(terminal_id):02d}-{today}-{seq:02d}"

                if not user_id:
                    try:
                        from database.system_logger import active_user_id
                        user_id = active_user_id.get()
                    except Exception:
                        pass
                if not user_id:
                    try:
                        cursor.execute("SELECT User_ID FROM Users ORDER BY User_ID ASC LIMIT 1")
                        first_user = cursor.fetchone()
                        if first_user:
                            user_id = first_user.get("User_ID")
                    except Exception:
                        pass

                cursor.execute(
                    """
                    INSERT INTO POS_Cash_Sessions
                    (Session_No, Terminal_ID, Opened_By, Opening_Amount, Notes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_no, terminal_id, user_id, opening_amount, notes),
                )
                session_id = cursor.lastrowid
                return True, {
                    "Cash_Session_ID": session_id,
                    "Session_No": session_no,
                    "Terminal_ID": terminal_id,
                    "Opened_By": user_id,
                    "Opening_Amount": opening_amount,
                    "Status": "Open",
                    "Next_Invoice_Seq": 1,
                }
        except Exception as e:
            logging.error(f"Could not open cash session: {e}", exc_info=True)
            return False, {"message": str(e)}

    def get_session_summary(self, cash_session_id: int) -> Dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Cash' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Cash,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Card' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Card,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Transfer' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Transfer,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Versement' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Versement,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Other' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Other,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Credit' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Credit,
                        COALESCE(SUM(COALESCE(p.Amount, i.Total_Amount_TTC)), 0) AS Expected_Total,
                        COUNT(DISTINCT i.Invoice_ID) AS Invoice_Count
                    FROM Sales_Invoices i
                    LEFT JOIN POS_Sale_Payments p ON p.Invoice_ID = i.Invoice_ID
                    WHERE i.Cash_Session_ID = %s AND i.Status <> 'Cancelled'
                    """,
                    (cash_session_id,),
                )
                summary = cursor.fetchone() or {}
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN Movement_Type = 'Cash_In' THEN Amount ELSE 0 END), 0) AS Cash_In,
                        COALESCE(SUM(CASE WHEN Movement_Type IN ('Cash_Out', 'Refund') THEN Amount ELSE 0 END), 0) AS Cash_Out
                    FROM POS_Cash_Movements
                    WHERE Cash_Session_ID = %s
                    """,
                    (cash_session_id,),
                )
                movements = cursor.fetchone() or {}
                summary['Cash_In'] = movements.get('Cash_In') or 0
                summary['Cash_Out'] = movements.get('Cash_Out') or 0
                summary['Expected_Cash'] = float(summary.get('Expected_Cash') or 0) + float(summary['Cash_In']) - float(summary['Cash_Out'])
                return summary
        except Exception as e:
            logging.error(f"Could not summarize cash session: {e}", exc_info=True)
            return {}

    def close_session(self, cash_session_id: int, user_id: Optional[int], counted_cash=0.0, notes=None, counted_card=None, counted_transfer=None, counted_versement=None, counted_other=None, counted_credit=None) -> Tuple[bool, Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                conn.start_transaction()
                cursor.execute(
                    """
                    SELECT * FROM POS_Cash_Sessions
                    WHERE Cash_Session_ID = %s AND Status = 'Open'
                    FOR UPDATE
                    """,
                    (cash_session_id,),
                )
                session = cursor.fetchone()
                if not session:
                    conn.rollback()
                    return False, {"message": "Aucune session ouverte a cloturer."}

                summary = self.get_session_summary(cash_session_id)
                expected_cash = float(summary.get("Expected_Cash") or 0)
                expected_card = float(summary.get("Expected_Card") or 0)
                expected_transfer = float(summary.get("Expected_Transfer") or 0)
                expected_versement = float(summary.get("Expected_Versement") or 0)
                expected_other = float(summary.get("Expected_Other") or 0)
                expected_credit = float(summary.get("Expected_Credit") or 0)
                opening_amount = float(session.get("Opening_Amount") or 0)
                counted_card = float(counted_card if counted_card is not None else expected_card)
                counted_transfer = float(counted_transfer if counted_transfer is not None else expected_transfer)
                counted_versement = float(counted_versement if counted_versement is not None else expected_versement)
                counted_other = float(counted_other if counted_other is not None else expected_other)
                counted_credit = float(counted_credit if counted_credit is not None else expected_credit)
                cash_difference = float(counted_cash) - (opening_amount + expected_cash)
                card_difference = counted_card - expected_card
                transfer_difference = counted_transfer - expected_transfer
                versement_difference = counted_versement - expected_versement
                other_difference = counted_other - expected_other
                credit_difference = counted_credit - expected_credit

                if not user_id:
                    try:
                        from database.system_logger import active_user_id
                        user_id = active_user_id.get()
                    except Exception:
                        pass
                if not user_id:
                    user_id = session.get("Opened_By")

                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Status = 'Closed',
                        Closed_By = %s,
                        Closed_At = NOW(),
                        Expected_Cash = %s,
                        Expected_Card = %s,
                        Expected_Transfer = %s,
                        Expected_Versement = %s,
                        Expected_Other = %s,
                        Expected_Credit = %s,
                        Counted_Cash = %s,
                        Counted_Card = %s,
                        Counted_Transfer = %s,
                        Counted_Versement = %s,
                        Counted_Other = %s,
                        Counted_Credit = %s,
                        Cash_Difference = %s,
                        Card_Difference = %s,
                        Transfer_Difference = %s,
                        Versement_Difference = %s,
                        Other_Difference = %s,
                        Credit_Difference = %s,
                        Notes = %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (
                        user_id, expected_cash, expected_card, expected_transfer, expected_versement, expected_other, expected_credit,
                        counted_cash, counted_card, counted_transfer, counted_versement, counted_other, counted_credit,
                        cash_difference, card_difference, transfer_difference, versement_difference, other_difference, credit_difference,
                        notes, cash_session_id,
                    ),
                )
                conn.commit()
                summary.update({
                    "Opening_Amount": opening_amount,
                    "Counted_Cash": float(counted_cash),
                    "Counted_Card": counted_card,
                    "Counted_Transfer": counted_transfer,
                    "Counted_Versement": counted_versement,
                    "Counted_Other": counted_other,
                    "Counted_Credit": counted_credit,
                    "Cash_Difference": cash_difference,
                    "Card_Difference": card_difference,
                    "Transfer_Difference": transfer_difference,
                    "Versement_Difference": versement_difference,
                    "Other_Difference": other_difference,
                    "Credit_Difference": credit_difference,
                })
                return True, summary
        except Exception as e:
            logging.error(f"Could not close cash session: {e}", exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False, {"message": str(e)}

    def get_session_details_full(self, cash_session_id: int) -> Optional[Dict]:
        """Retourne les informations complètes d'une session : caisse, ouvertures, fermetures, écarts, et factures associées."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT s.*, 
                           t.Terminal_Code, t.Terminal_Name,
                           COALESCE(u_open.Full_Name, u_open.Username) AS Opened_By_Name,
                           COALESCE(u_close.Full_Name, u_close.Username) AS Closed_By_Name
                    FROM POS_Cash_Sessions s
                    JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    LEFT JOIN Users u_open ON s.Opened_By = u_open.User_ID
                    LEFT JOIN Users u_close ON s.Closed_By = u_close.User_ID
                    WHERE s.Cash_Session_ID = %s
                    """,
                    (cash_session_id,),
                )
                session = cursor.fetchone()
                if not session:
                    return None

                # Récapitulatif financier
                summary = self.get_session_summary(cash_session_id)
                session["summary"] = summary

                # Factures de vente de la session
                cursor.execute(
                    """
                    SELECT i.Invoice_ID, i.Invoice_No, i.Invoice_Date, i.Total_Amount_TTC,
                           i.Status, i.Payment_Method,
                           COALESCE(c.Client_Name, 'Vente comptoir') AS Client_Name,
                           COALESCE(u.Full_Name, u.Username) AS Cashier_Name
                    FROM Sales_Invoices i
                    LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                    LEFT JOIN Users u ON i.Created_By = u.User_ID
                    WHERE i.Cash_Session_ID = %s
                    ORDER BY i.Invoice_Date DESC, i.Invoice_ID DESC
                    """,
                    (cash_session_id,),
                )
                session["invoices"] = cursor.fetchall()
                return session
        except Exception as e:
            logging.error(f"Could not fetch full session details: {e}", exc_info=True)
            return None

    def get_cash_sessions_report(self, start_date=None, end_date=None, terminal_id=None) -> list:
        """Rapport synthétique et détaillé de toutes les sessions de caisse pour une période/caisse donnée."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT s.*,
                           t.Terminal_Code, t.Terminal_Name,
                           COALESCE(u_open.Full_Name, u_open.Username) AS Opened_By_Name,
                           COALESCE(u_close.Full_Name, u_close.Username) AS Closed_By_Name,
                           COALESCE(inv_agg.Invoice_Count, 0) AS Total_Invoices,
                           COALESCE(inv_agg.Total_Sales_TTC, 0) AS Total_Sales_TTC
                    FROM POS_Cash_Sessions s
                    JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    LEFT JOIN Users u_open ON s.Opened_By = u_open.User_ID
                    LEFT JOIN Users u_close ON s.Closed_By = u_close.User_ID
                    LEFT JOIN (
                        SELECT Cash_Session_ID,
                               COUNT(Invoice_ID) AS Invoice_Count,
                               SUM(CASE WHEN Status <> 'Cancelled' THEN Total_Amount_TTC ELSE 0 END) AS Total_Sales_TTC
                        FROM Sales_Invoices
                        GROUP BY Cash_Session_ID
                    ) inv_agg ON s.Cash_Session_ID = inv_agg.Cash_Session_ID
                    WHERE 1=1
                """
                params = []
                if start_date:
                    query += " AND (DATE(s.Opened_At) >= %s OR DATE(s.Closed_At) >= %s)"
                    params.extend([start_date, start_date])
                if end_date:
                    query += " AND (DATE(s.Opened_At) <= %s OR DATE(s.Closed_At) <= %s)"
                    params.extend([end_date, end_date])
                if terminal_id:
                    query += " AND s.Terminal_ID = %s"
                    params.append(terminal_id)

                query += " ORDER BY s.Opened_At DESC"
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Could not fetch cash sessions report: {e}", exc_info=True)
            return []

