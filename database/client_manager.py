# database/client_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientManager:
    """إدارة عمليات جدول العملاء (Clients)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_client(self, name, contact_person=None, phone=None, email=None, 
                   address=None, city=None, tax_id=None, commercial_reg=None,
                   price_tier='Prix_1', credit_limit=0.0):
        """
        إضافة عميل جديد مع تحديد الفئة السعرية وسقف الائتمان.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Clients 
                    (Client_Name, Contact_Person, Phone, Email, Address, City, Tax_ID_Number, Commercial_Reg_No, Price_Tier, Credit_Limit) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (name, contact_person, phone, email, address, city, tax_id, commercial_reg, price_tier or 'Prix_1', float(credit_limit or 0.0))
                cursor.execute(query, params)
                client_id = cursor.lastrowid
                logging.info(f"Client '{name}' added with ID {client_id}.")
                return client_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Client '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding client '{name}': {err}")
            return None

    def update_client(self, client_id, **kwargs):
        """
        تحديث معلومات العميل بشكل ديناميكي.
        الوسائط المتاحة: name, contact_person, phone, email, address, city, tax_id, commercial_reg, price_tier, credit_limit
        """
        field_map = {
            'name': 'Client_Name',
            'contact_person': 'Contact_Person',
            'phone': 'Phone',
            'email': 'Email',
            'address': 'Address',
            'city': 'City',
            'tax_id': 'Tax_ID_Number',
            'commercial_reg': 'Commercial_Reg_No',
            'price_tier': 'Price_Tier',
            'credit_limit': 'Credit_Limit'
        }
        
        updates = []
        params = []
        
        for kw, db_field in field_map.items():
            if kw in kwargs and kwargs[kw] is not None:
                updates.append(f"{db_field} = %s")
                params.append(kwargs[kw])
                
        if not updates:
            logging.warning(f"No fields provided for client update (ID: {client_id}).")
            return False

        params.append(client_id)
        query = f"UPDATE Clients SET {', '.join(updates)} WHERE Client_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} updated successfully.")
                    return True
                logging.warning(f"No active client found with ID {client_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating client {client_id}: {e}")
            raise

    def get_all_clients(self, include_deleted=False):
        """
        جلب جميع العملاء.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Clients"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Client_Name"
                
                cursor.execute(query)
                clients = cursor.fetchall()
                logging.info(f"Fetched {len(clients)} clients.")
                return clients
        except mysql.connector.Error as e:
            logging.error(f"Error fetching clients: {e}")
            raise

    def get_client_by_id(self, client_id):
        """
        جلب عميل محدد باستخدام ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Clients WHERE Client_ID = %s"
                cursor.execute(query, (client_id,))
                client = cursor.fetchone()
                return client
        except mysql.connector.Error as e:
            logging.error(f"Error fetching client {client_id}: {e}")
            raise

    def soft_delete_client(self, client_id):
        """
        حذف منطقي (Soft Delete) لعميل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق مما إذا كان العميل مرتبطاً بفواتير
                cursor.execute("SELECT COUNT(*) FROM Sales_Invoices WHERE Client_ID = %s", (client_id,))
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete client {client_id}. They have associated sales invoices.")
                    return False
                
                query = "UPDATE Clients SET Deleted_At = %s WHERE Client_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), client_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} soft deleted successfully.")
                    return True
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting client {client_id}: {e}")
            return False

    def get_client_balance(self, client_id: int) -> dict:
        """
        Calcule dynamiquement le solde financier d'un client :
        Solde = Total Factures - Total Paiements Reçus - Total Avoirs
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT Client_ID, Client_Name, Credit_Limit, Price_Tier FROM Clients WHERE Client_ID = %s", 
                    (client_id,)
                )
                client = cursor.fetchone()
                if not client:
                    return {
                        "client_id": client_id,
                        "client_name": "",
                        "credit_limit": 0.0,
                        "price_tier": "Prix_1",
                        "total_invoiced": 0.0,
                        "total_paid": 0.0,
                        "total_credit_notes": 0.0,
                        "current_balance": 0.0,
                        "available_credit": 0.0
                    }

                # 1. Total Facturé (hors factures annulées)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_invoiced
                    FROM Sales_Invoices
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """, (client_id,))
                total_invoiced = float(cursor.fetchone()['total_invoiced'] or 0.0)

                # 2. Total Payé au comptant lors des ventes (POS Sale Payments non-crédit)
                cursor.execute("""
                    SELECT COALESCE(SUM(p.Amount), 0) AS pos_paid
                    FROM POS_Sale_Payments p
                    JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                    WHERE i.Client_ID = %s AND i.Status != 'Cancelled' AND p.Payment_Method != 'Credit'
                """, (client_id,))
                pos_paid = float(cursor.fetchone()['pos_paid'] or 0.0)

                # 3. Total Paiements ultérieurs (Client_Payments)
                cursor.execute("""
                    SELECT COALESCE(SUM(Amount), 0) AS client_paid
                    FROM Client_Payments
                    WHERE Client_ID = %s
                """, (client_id,))
                client_paid = float(cursor.fetchone()['client_paid'] or 0.0)

                total_paid = pos_paid + client_paid

                # 4. Total Avoirs / Retours (Client_Credit_Notes)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_cn
                    FROM Client_Credit_Notes
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """, (client_id,))
                total_credit_notes = float(cursor.fetchone()['total_cn'] or 0.0)

                current_balance = round(total_invoiced - total_paid - total_credit_notes, 2)
                credit_limit = float(client.get('Credit_Limit') or 0.0)
                available_credit = max(0.0, round(credit_limit - current_balance, 2)) if credit_limit > 0 else 0.0

                return {
                    "client_id": client_id,
                    "client_name": client.get('Client_Name', ''),
                    "credit_limit": credit_limit,
                    "price_tier": client.get('Price_Tier', 'Prix_1'),
                    "total_invoiced": total_invoiced,
                    "total_paid": total_paid,
                    "total_credit_notes": total_credit_notes,
                    "current_balance": current_balance,
                    "available_credit": available_credit
                }
        except Exception as e:
            logging.error(f"Error computing balance for client {client_id}: {e}")
            return {
                "client_id": client_id,
                "current_balance": 0.0,
                "credit_limit": 0.0,
                "available_credit": 0.0,
                "price_tier": "Prix_1"
            }

    def get_all_clients_with_balances(self) -> list:
        """
        Récupère tous les clients actifs avec leurs soldes calculés dynamiquement en une seule requête optimisée.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        c.*,
                        COALESCE(c.Credit_Limit, 0.00) AS Credit_Limit,
                        COALESCE(c.Price_Tier, 'Prix_1') AS Price_Tier,
                        COALESCE(inv.total_invoiced, 0.00) AS total_invoiced,
                        COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00) AS total_paid,
                        COALESCE(cn.total_credit_notes, 0.00) AS total_credit_notes,
                        ROUND(
                            COALESCE(inv.total_invoiced, 0.00) 
                            - (COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00)) 
                            - COALESCE(cn.total_credit_notes, 0.00), 
                            2
                        ) AS Current_Balance
                    FROM Clients c
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_invoiced
                        FROM Sales_Invoices
                        WHERE Status != 'Cancelled' AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) inv ON c.Client_ID = inv.Client_ID
                    LEFT JOIN (
                        SELECT i.Client_ID, SUM(p.Amount) AS pos_paid
                        FROM POS_Sale_Payments p
                        JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                        WHERE i.Status != 'Cancelled' AND p.Payment_Method != 'Credit' AND i.Client_ID IS NOT NULL
                        GROUP BY i.Client_ID
                    ) pos_pay ON c.Client_ID = pos_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Amount) AS client_paid
                        FROM Client_Payments
                        WHERE Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) cl_pay ON c.Client_ID = cl_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_credit_notes
                        FROM Client_Credit_Notes
                        WHERE Status != 'Cancelled' AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) cn ON c.Client_ID = cn.Client_ID
                    WHERE c.Deleted_At IS NULL
                    ORDER BY c.Client_Name
                """
                cursor.execute(query)
                return cursor.fetchall() or []
        except Exception as e:
            logging.error(f"Error fetching clients with balances: {e}")
            return self.get_all_clients()

    def get_client_ledger(self, client_id: int, start_date=None, end_date=None) -> dict:
        """
        Extrait l'historique complet chronologique pour le Relevé de Compte Client.
        Calcule le solde initial avant start_date, la liste des opérations (Débit, Crédit, Solde),
        et le solde final.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Récupérer infos client
                cursor.execute("SELECT * FROM Clients WHERE Client_ID = %s", (client_id,))
                client = cursor.fetchone() or {}

                # Solde initial antérieur à start_date
                initial_balance = 0.0
                if start_date:
                    cursor.execute("""
                        SELECT 
                            (
                                SELECT COALESCE(SUM(Total_Amount_TTC), 0)
                                FROM Sales_Invoices
                                WHERE Client_ID = %s AND Status != 'Cancelled' AND Invoice_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(p.Amount), 0)
                                FROM POS_Sale_Payments p
                                JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                                WHERE i.Client_ID = %s AND i.Status != 'Cancelled' AND p.Payment_Method != 'Credit' AND i.Invoice_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(Amount), 0)
                                FROM Client_Payments
                                WHERE Client_ID = %s AND Payment_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(Total_Amount_TTC), 0)
                                FROM Client_Credit_Notes
                                WHERE Client_ID = %s AND Status != 'Cancelled' AND Return_Date < %s
                            ) AS prior_balance
                    """, (client_id, start_date, client_id, start_date, client_id, start_date, client_id, start_date))
                    row = cursor.fetchone()
                    initial_balance = float(row.get('prior_balance') or 0.0) if row else 0.0

                transactions = []

                # 1. Factures dans la période
                inv_query = """
                    SELECT Invoice_ID, Invoice_No, Invoice_Date AS op_date, Total_Amount_TTC, Sale_Type, Status
                    FROM Sales_Invoices
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """
                inv_params = [client_id]
                if start_date:
                    inv_query += " AND Invoice_Date >= %s"
                    inv_params.append(start_date)
                if end_date:
                    inv_query += " AND Invoice_Date <= %s"
                    inv_params.append(end_date)
                cursor.execute(inv_query, tuple(inv_params))
                for r in cursor.fetchall():
                    ref = r.get('Invoice_No') or f"FAC-{r['Invoice_ID']}"
                    if ref.startswith("BL-"):
                        label = "Bon de Livraison (BL)"
                    elif ref.startswith("DEV-"):
                        label = "Devis"
                    elif ref.startswith("BC-"):
                        label = "Bon de Commande (BC)"
                    elif r.get('Sale_Type') == 'Wholesale':
                        label = "Facture (Vente Gros)"
                    else:
                        label = "Facture (Vente POS)"
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': label,
                        'reference': ref,
                        'debit': float(r['Total_Amount_TTC'] or 0.0),
                        'credit': 0.0,
                        'notes': f"Statut: {r.get('Status')}"
                    })

                # 2. Paiements au comptant lors de la vente dans la période
                pos_pay_query = """
                    SELECT p.Payment_ID, p.Payment_Method, p.Amount, p.Reference, i.Invoice_No, i.Invoice_Date AS op_date
                    FROM POS_Sale_Payments p
                    JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                    WHERE i.Client_ID = %s AND i.Status != 'Cancelled' AND p.Payment_Method != 'Credit'
                """
                pos_pay_params = [client_id]
                if start_date:
                    pos_pay_query += " AND i.Invoice_Date >= %s"
                    pos_pay_params.append(start_date)
                if end_date:
                    pos_pay_query += " AND i.Invoice_Date <= %s"
                    pos_pay_params.append(end_date)
                cursor.execute(pos_pay_query, tuple(pos_pay_params))
                for r in cursor.fetchall():
                    ref = r.get('Reference') or r.get('Invoice_No') or f"PAY-{r['Payment_ID']}"
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': f"Paiement Caisse ({r['Payment_Method']})",
                        'reference': ref,
                        'debit': 0.0,
                        'credit': float(r['Amount'] or 0.0),
                        'notes': "Paiement direct à la vente"
                    })

                # 3. Règlements ultérieurs (Client_Payments)
                cl_pay_query = """
                    SELECT Payment_ID, Payment_Date AS op_date, Amount, Payment_Method, Reference, Notes
                    FROM Client_Payments
                    WHERE Client_ID = %s
                """
                cl_pay_params = [client_id]
                if start_date:
                    cl_pay_query += " AND Payment_Date >= %s"
                    cl_pay_params.append(start_date)
                if end_date:
                    cl_pay_query += " AND Payment_Date <= %s"
                    cl_pay_params.append(end_date)
                cursor.execute(cl_pay_query, tuple(cl_pay_params))
                for r in cursor.fetchall():
                    ref = r.get('Reference') or f"REG-{r['Payment_ID']}"
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': f"Règlement ({r.get('Payment_Method', 'Espèce')})",
                        'reference': ref,
                        'debit': 0.0,
                        'credit': float(r['Amount'] or 0.0),
                        'notes': r.get('Notes') or ''
                    })

                # 4. Avoirs / Retours (Client_Credit_Notes)
                cn_query = """
                    SELECT Credit_Note_ID, Return_Date AS op_date, Total_Amount_TTC, Notes
                    FROM Client_Credit_Notes
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """
                cn_params = [client_id]
                if start_date:
                    cn_query += " AND Return_Date >= %s"
                    cn_params.append(start_date)
                if end_date:
                    cn_query += " AND Return_Date <= %s"
                    cn_params.append(end_date)
                cursor.execute(cn_query, tuple(cn_params))
                for r in cursor.fetchall():
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': "Avoir / Retour Produit",
                        'reference': f"AVR-{r['Credit_Note_ID']}",
                        'debit': 0.0,
                        'credit': float(r['Total_Amount_TTC'] or 0.0),
                        'notes': r.get('Notes') or ''
                    })

                # Tri chronologique des transactions
                transactions.sort(key=lambda x: x['date'])

                # Calcul du solde progressif
                current_running = initial_balance
                for t in transactions:
                    current_running = round(current_running + t['debit'] - t['credit'], 2)
                    t['balance'] = current_running

                final_balance = current_running

                return {
                    'client': client,
                    'initial_balance': round(initial_balance, 2),
                    'transactions': transactions,
                    'final_balance': round(final_balance, 2),
                    'start_date': str(start_date) if start_date else None,
                    'end_date': str(end_date) if end_date else None
                }

        except Exception as e:
            logging.error(f"Error generating ledger for client {client_id}: {e}")
            return {
                'client': {},
                'initial_balance': 0.0,
                'transactions': [],
                'final_balance': 0.0
            }
