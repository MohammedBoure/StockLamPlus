# ui/widgets/sales/wholesale_sales_tab.py

import os
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QDoubleSpinBox, QDateEdit, QFrame,
    QCompleter, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QDate, QStringListModel
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut

from ui.formatting import format_money
from branding import get_logo_path
from .dialogs import ClientDialog
from ..master_data.client_statement_dialog import ClientStatementDialog

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class WholesaleSalesTab(QWidget):
    """
    Module de Vente en Gros et Demi-Gros (B2B).
    Fonctionne indépendamment des sessions de caisse POS (aucun terminal/session de caisse requis).
    Prend en charge :
    - Devis / Proforma (aucun mouvement de stock)
    - Bon de Commande (aucun mouvement de stock)
    - Bon de Livraison (déduction atomique du stock d'entrepôt)
    - Facture de Vente en Gros (déduction atomique du stock et comptabilisation)
    - Résolution dynamique de la grille tarifaire (Prix 1 à Prix 4) selon le client.
    """

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.cart_items = []
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}

        self.init_ui()
        self.load_initial_data()
        self._install_shortcuts()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Client & Credit Dashboard Header Card
        client_card = self._build_client_card()
        root_layout.addWidget(client_card)

        # 2. Document Meta Controls (Type, Dates, Échéances, Paiement)
        meta_card = self._build_meta_card()
        root_layout.addWidget(meta_card)

        # 3. Search & Quick Add Row
        search_row = self._build_search_row()
        root_layout.addLayout(search_row)

        # 4. Cart Grid Table
        self.cart_table = self._build_cart_table()
        root_layout.addWidget(self.cart_table, 1)

        # 5. Bottom Financial Summary & Actions
        bottom_bar = self._build_bottom_bar()
        root_layout.addLayout(bottom_bar)

    def _build_client_card(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(12)

        # Client Selector
        lbl_c = QLabel("Client B2B * :")
        lbl_c.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 12px;")
        self.cb_client = QComboBox()
        self.cb_client.setMinimumHeight(34)
        self.cb_client.setMinimumWidth(260)
        self.cb_client.setEditable(True)
        if self.cb_client.completer():
            self.cb_client.completer().setFilterMode(Qt.MatchContains)
            self.cb_client.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_client.currentIndexChanged.connect(self._on_client_changed)

        self.btn_new_client = QPushButton("➕ Nouveau")
        self.btn_new_client.setCursor(Qt.PointingHandCursor)
        self.btn_new_client.setFixedHeight(34)
        self.btn_new_client.clicked.connect(self._create_quick_client)

        self.btn_client_statement = QPushButton("📄 Relevé")
        self.btn_client_statement.setCursor(Qt.PointingHandCursor)
        self.btn_client_statement.setFixedHeight(34)
        self.btn_client_statement.setStyleSheet("background-color: #007572; color: white; font-weight: bold;")
        self.btn_client_statement.clicked.connect(self._open_client_statement)

        layout.addWidget(lbl_c)
        layout.addWidget(self.cb_client, 2)
        layout.addWidget(self.btn_new_client)
        layout.addWidget(self.btn_client_statement)

        # Badges Info Client
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #cbd5e1;")
        layout.addWidget(sep)

        self.lbl_price_tier = QLabel("Catégorie : Prix 1")
        self.lbl_price_tier.setStyleSheet("background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #007572;")

        self.lbl_credit_limit = QLabel("Plafond : 0.00 DA")
        self.lbl_credit_limit.setStyleSheet("background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; font-weight: 500; color: #475569;")

        self.lbl_current_balance = QLabel("Solde Dû : 0.00 DA")
        self.lbl_current_balance.setStyleSheet("background-color: #ecfdf5; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #16a34a;")

        self.lbl_available_credit = QLabel("Disponible : 0.00 DA")
        self.lbl_available_credit.setStyleSheet("background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; font-weight: 500; color: #0284c7;")

        layout.addWidget(self.lbl_price_tier)
        layout.addWidget(self.lbl_credit_limit)
        layout.addWidget(self.lbl_current_balance)
        layout.addWidget(self.lbl_available_credit)

        return card

    def _build_meta_card(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        # Document Type
        layout.addWidget(QLabel("Type Document :"))
        self.cb_doc_type = QComboBox()
        self.cb_doc_type.addItem("Facture de Vente", "Facture")
        self.cb_doc_type.addItem("Bon de Livraison (BL)", "Bon de Livraison")
        self.cb_doc_type.addItem("Bon de Commande (BC)", "Bon de Commande")
        self.cb_doc_type.addItem("Devis / Facture Proforma", "Devis")
        self.cb_doc_type.setMinimumHeight(32)
        self.cb_doc_type.currentIndexChanged.connect(self._on_doc_type_changed)
        layout.addWidget(self.cb_doc_type)

        # Date de Document
        layout.addWidget(QLabel("Date :"))
        self.date_order = QDateEdit()
        self.date_order.setCalendarPopup(True)
        self.date_order.setDate(QDate.currentDate())
        self.date_order.setMinimumHeight(32)
        layout.addWidget(self.date_order)

        # Date d'échéance
        layout.addWidget(QLabel("Échéance :"))
        self.date_due = QDateEdit()
        self.date_due.setCalendarPopup(True)
        self.date_due.setDate(QDate.currentDate().addDays(30))
        self.date_due.setMinimumHeight(32)
        layout.addWidget(self.date_due)

        # Raccourcis échéance
        btn_15 = QPushButton("+15j")
        btn_30 = QPushButton("+30j")
        btn_60 = QPushButton("+60j")
        btn_eom = QPushButton("Fin Mois")
        for b in (btn_15, btn_30, btn_60, btn_eom):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(30)
            b.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; font-size: 11px; padding: 2px 6px;")

        btn_15.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(15)))
        btn_30.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(30)))
        btn_60.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(60)))
        btn_eom.clicked.connect(self._set_end_of_month_due_date)

        layout.addWidget(btn_15)
        layout.addWidget(btn_30)
        layout.addWidget(btn_60)
        layout.addWidget(btn_eom)

        # Mode de Paiement
        layout.addWidget(QLabel("Paiement :"))
        self.cb_payment_method = QComboBox()
        self.cb_payment_method.addItem("À terme / Crédit Client", "Credit")
        self.cb_payment_method.addItem("Espèce", "Cash")
        self.cb_payment_method.addItem("Chèque Bancaire", "Card")
        self.cb_payment_method.addItem("Virement Bancaire", "Transfer")
        self.cb_payment_method.addItem("Versement", "Versement")
        self.cb_payment_method.setMinimumHeight(32)
        layout.addWidget(self.cb_payment_method)

        layout.addStretch(1)

        return card

    def _set_end_of_month_due_date(self):
        curr = self.date_order.date().toPython()
        # Find last day of current order month
        next_month = curr.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        self.date_due.setDate(QDate(last_day.year, last_day.month, last_day.day))

    def _build_search_row(self):
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un produit en stock, scanner un code-barres ou numéro de lot...")
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #007572;
                border-radius: 4px;
                padding: 0 10px;
                font-size: 13px;
                font-weight: 500;
            }
        """)

        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.search_input.setCompleter(self.completer)
        self.completer.activated.connect(self._on_search_selected)
        self.search_input.returnPressed.connect(self._on_search_return)

        self.spin_quick_qty = QDoubleSpinBox()
        self.spin_quick_qty.setRange(0.01, 999999.0)
        self.spin_quick_qty.setValue(1.0)
        self.spin_quick_qty.setDecimals(2)
        self.spin_quick_qty.setMinimumHeight(36)
        self.spin_quick_qty.setMinimumWidth(80)
        self.spin_quick_qty.setPrefix("Qté: ")

        self.btn_add_to_cart = QPushButton("➕ Ajouter")
        self.btn_add_to_cart.setCursor(Qt.PointingHandCursor)
        self.btn_add_to_cart.setMinimumHeight(36)
        self.btn_add_to_cart.setStyleSheet("background-color: #007572; color: white; font-weight: bold; padding: 0 16px;")
        self.btn_add_to_cart.clicked.connect(self._on_search_return)

        self.btn_refresh = QPushButton("🔄 Actualiser Stock")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setMinimumHeight(36)
        self.btn_refresh.clicked.connect(self.load_initial_data)

        layout.addWidget(self.search_input, 4)
        layout.addWidget(self.spin_quick_qty, 1)
        layout.addWidget(self.btn_add_to_cart)
        layout.addWidget(self.btn_refresh)

        return layout

    def _build_cart_table(self):
        table = QTableWidget()
        cols = [
            "", "Code-Barres", "Désignation Produit", "N° Lot", "Péremption",
            "Emplacement", "Stock Dispo", "Prix Unit. HT", "Quantité", "Remise %",
            "Total HT", "TVA %", "Total TTC"
        ]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setDefaultSectionSize(36)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 36)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(11, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(12, QHeaderView.ResizeToContents)

        return table

    def _build_bottom_bar(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Left Actions
        self.btn_clear = QPushButton("🗑️ Vider le Panier")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet("background-color: #ffffff; color: #dc2626; border: 1px solid #f87171; padding: 8px 14px; font-weight: bold;")
        self.btn_clear.clicked.connect(self.clear_cart)
        layout.addWidget(self.btn_clear)

        layout.addStretch(1)

        # Financial Summary Panel
        self.lbl_summary_ht = QLabel("Total HT : 0,00 DA")
        self.lbl_summary_ht.setStyleSheet("font-size: 12px; color: #475569; font-weight: bold;")

        self.lbl_summary_remise = QLabel("Remise : 0,00 DA")
        self.lbl_summary_remise.setStyleSheet("font-size: 12px; color: #d97706; font-weight: bold;")

        self.lbl_summary_tva = QLabel("TVA : 0,00 DA")
        self.lbl_summary_tva.setStyleSheet("font-size: 12px; color: #475569; font-weight: bold;")

        self.lbl_summary_net_ttc = QLabel("NET À PAYER : 0,00 DA")
        self.lbl_summary_net_ttc.setStyleSheet("""
            background-color: #007572;
            color: white;
            padding: 6px 14px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
        """)

        layout.addWidget(self.lbl_summary_ht)
        layout.addWidget(self.lbl_summary_remise)
        layout.addWidget(self.lbl_summary_tva)
        layout.addWidget(self.lbl_summary_net_ttc)

        # Commit Buttons
        self.btn_save_document = QPushButton("💾 Valider le Document (F10)")
        self.btn_save_document.setCursor(Qt.PointingHandCursor)
        self.btn_save_document.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 4px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_save_document.clicked.connect(self.validate_wholesale_sale)
        layout.addWidget(self.btn_save_document)

        return layout

    def _install_shortcuts(self):
        self._shortcut_f10 = QShortcut(QKeySequence("F10"), self)
        self._shortcut_f10.activated.connect(self.validate_wholesale_sale)

    def load_initial_data(self):
        # 1. Load Clients
        self.cb_client.blockSignals(True)
        self.cb_client.clear()
        try:
            if hasattr(self.data_manager.clients, 'get_all_clients_with_balances'):
                clients = self.data_manager.clients.get_all_clients_with_balances()
            else:
                clients = self.data_manager.clients.get_all_clients()

            for c in clients:
                cid = c.get('Client_ID')
                cname = c.get('Client_Name')
                city = c.get('City') or ''
                display_text = f"{cname} ({city})" if city else cname
                self.cb_client.addItem(display_text, c)
        except Exception as e:
            logging.error(f"Error loading clients for wholesale: {e}")
        self.cb_client.blockSignals(False)

        if self.cb_client.count() > 0:
            self._on_client_changed(0)

        # 2. Load Inventory Batches (Stock > 0 from all locations)
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        try:
            self.batches_cache = self.data_manager.batches.get_all_batches_with_details()
            suggestions = []
            for b in self.batches_cache:
                codes = self._extract_barcodes(b)
                code_str = " / ".join(codes) if codes else "-"
                lot = b.get("Lot_Number") or "---"
                qty = b.get("Quantity_Current") or 0
                sugg = f"[{code_str}] {b.get('Product_Name', '')} | Lot: {lot} | Stock: {qty} ({b.get('Location_Name', '-')})"
                suggestions.append(sugg)
                self.search_map[sugg] = b
                for c in codes:
                    norm = self._normalize_code(c)
                    if norm:
                        self.barcode_map[norm] = b

            self.completer.setModel(QStringListModel(suggestions))
        except Exception as e:
            logging.error(f"Error loading batches for wholesale: {e}")

    def _extract_barcodes(self, batch):
        codes = []
        for key in ("Internal_Barcode", "External_Barcode", "Barcode"):
            val = str(batch.get(key) or "").strip()
            if val and val.lower() not in {"none", "null", "---"} and val not in codes:
                codes.append(val)
        return codes

    def _normalize_code(self, val):
        return str(val or "").strip().lower().replace(" ", "").replace("-", "")

    def _get_current_client(self):
        idx = self.cb_client.currentIndex()
        if idx >= 0:
            return self.cb_client.itemData(idx)
        return None

    def _on_client_changed(self, index):
        client = self._get_current_client()
        if not client:
            return

        tier = client.get('Price_Tier') or 'Prix_1'
        tier_names = {
            'Prix_1': 'Prix 1 (Détail)',
            'Prix_2': 'Prix 2 (Demi-Gros)',
            'Prix_3': 'Prix 3 (Gros)',
            'Prix_4': 'Prix 4 (Super-Gros)'
        }
        self.lbl_price_tier.setText(f"Catégorie : {tier_names.get(tier, tier)}")

        limit = float(client.get('Credit_Limit') or 0.0)
        self.lbl_credit_limit.setText(f"Plafond : {format_money(limit)} DA")

        bal = float(client.get('Current_Balance') or 0.0)
        self.lbl_current_balance.setText(f"Solde Dû : {format_money(bal)} DA")

        if bal <= 0:
            self.lbl_current_balance.setStyleSheet("background-color: #ecfdf5; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #16a34a;")
        elif limit > 0 and bal <= limit:
            self.lbl_current_balance.setStyleSheet("background-color: #fefce8; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #d97706;")
        else:
            self.lbl_current_balance.setStyleSheet("background-color: #fef2f2; padding: 4px 8px; border-radius: 4px; font-weight: bold; color: #dc2626;")

        avail = max(0.0, limit - bal) if limit > 0 else 0.0
        self.lbl_available_credit.setText(f"Disponible : {format_money(avail)} DA")

        # Recalculate price tiers for existing cart rows if empty or desired
        self._reapply_client_prices_to_cart()

    def _on_doc_type_changed(self, index):
        doc_type = self.cb_doc_type.currentData()
        if doc_type in ('Devis', 'Bon de Commande'):
            self.btn_save_document.setText(f"💾 Enregistrer le {doc_type} (F10)")
            self.btn_save_document.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 18px;
                    border-radius: 4px;
                    min-height: 36px;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
        else:
            self.btn_save_document.setText("💾 Valider & Déduire le Stock (F10)")
            self.btn_save_document.setStyleSheet("""
                QPushButton {
                    background-color: #16a34a;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 18px;
                    border-radius: 4px;
                    min-height: 36px;
                }
                QPushButton:hover { background-color: #15803d; }
            """)

    def _resolve_price_tier(self, batch, price_tier: str) -> float:
        """Résout le prix unitaire HT selon le palier tarifaire du client."""
        p1 = float(batch.get('Selling_Price_HT') or 0.0)
        p2 = float(batch.get('Selling_Price_HT_2') or 0.0)
        p3 = float(batch.get('Selling_Price_HT_3') or 0.0)
        p4 = float(batch.get('Selling_Price_HT_4') or 0.0)

        if price_tier == 'Prix_4':
            return p4 or p3 or p2 or p1 or 0.0
        elif price_tier == 'Prix_3':
            return p3 or p2 or p1 or 0.0
        elif price_tier == 'Prix_2':
            return p2 or p1 or 0.0
        else:
            return p1 or 0.0

    def _reapply_client_prices_to_cart(self):
        client = self._get_current_client()
        tier = client.get('Price_Tier') if client else 'Prix_1'

        for row in range(self.cart_table.rowCount()):
            item_prod = self.cart_table.item(row, 2)
            if not item_prod:
                continue
            batch = item_prod.data(Qt.UserRole)
            if not batch:
                continue
            resolved_p = self._resolve_price_tier(batch, tier)
            spin_price = self.cart_table.cellWidget(row, 7)
            if spin_price:
                spin_price.setValue(resolved_p)
        self.calculate_totals()

    def _on_search_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            self.add_batch_to_cart(batch, qty=self.spin_quick_qty.value())
            self.search_input.clear()

    def _on_search_return(self):
        text = self.search_input.text().strip()
        if not text:
            return

        batch = self.search_map.get(text)
        if not batch:
            norm = self._normalize_code(text)
            batch = self.barcode_map.get(norm)

        if not batch:
            lowered = text.lower()
            matches = [
                b for b in self.batches_cache
                if lowered in str(b.get("Product_Name", "")).lower()
                or lowered in str(b.get("Lot_Number", "")).lower()
            ]
            if len(matches) == 1:
                batch = matches[0]

        if batch:
            self.add_batch_to_cart(batch, qty=self.spin_quick_qty.value())
            self.search_input.clear()
        else:
            QMessageBox.warning(self, "Recherche", "Aucun produit ou lot correspondant trouvé.")

    def add_batch_to_cart(self, batch, qty=1.0):
        # Check if already in cart
        batch_id = batch.get('Batch_ID')
        for r in range(self.cart_table.rowCount()):
            item_p = self.cart_table.item(r, 2)
            existing = item_p.data(Qt.UserRole) if item_p else None
            if existing and existing.get('Batch_ID') == batch_id:
                spin_q = self.cart_table.cellWidget(r, 8)
                if spin_q:
                    spin_q.setValue(spin_q.value() + qty)
                self.calculate_totals()
                return

        row = self.cart_table.rowCount()
        self.cart_table.insertRow(row)

        client = self._get_current_client()
        tier = client.get('Price_Tier') if client else 'Prix_1'
        unit_price = self._resolve_price_tier(batch, tier)
        max_stock = float(batch.get('Quantity_Current') or 0.0)

        # 0. Delete button
        btn_del = QPushButton("❌")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("border: none; background: transparent; color: #dc2626; font-size: 13px;")
        btn_del.clicked.connect(lambda _, r_btn=btn_del: self._remove_cart_row(r_btn))
        self.cart_table.setCellWidget(row, 0, btn_del)

        # 1. Barcode
        codes = self._extract_barcodes(batch)
        item_bc = QTableWidgetItem(codes[0] if codes else "-")
        item_bc.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row, 1, item_bc)

        # 2. Product Name
        item_name = QTableWidgetItem(batch.get('Product_Name', ''))
        item_name.setData(Qt.UserRole, batch)
        self.cart_table.setItem(row, 2, item_name)

        # 3. Lot
        item_lot = QTableWidgetItem(str(batch.get('Lot_Number') or '---'))
        item_lot.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row, 3, item_lot)

        # 4. Expiry
        exp = str(batch.get('Expiry_Date') or '')
        item_exp = QTableWidgetItem(exp)
        item_exp.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row, 4, item_exp)

        # 5. Location
        loc = batch.get('Location_Name') or '-'
        item_loc = QTableWidgetItem(loc)
        item_loc.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row, 5, item_loc)

        # 6. Stock Dispo
        item_stk = QTableWidgetItem(str(max_stock))
        item_stk.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cart_table.setItem(row, 6, item_stk)

        # 7. Unit Price HT (Editable SpinBox)
        spin_p = QDoubleSpinBox()
        spin_p.setRange(0.0, 99999999.0)
        spin_p.setValue(unit_price)
        spin_p.setDecimals(2)
        spin_p.setButtonSymbols(QDoubleSpinBox.NoButtons)
        spin_p.setAlignment(Qt.AlignRight)
        spin_p.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 7, spin_p)

        # 8. Qty Sold (SpinBox)
        spin_q = QDoubleSpinBox()
        spin_q.setRange(0.01, max_stock if max_stock > 0 else 999999.0)
        spin_q.setValue(min(qty, max_stock if max_stock > 0 else qty))
        spin_q.setDecimals(2)
        spin_q.setAlignment(Qt.AlignCenter)
        spin_q.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 8, spin_q)

        # 9. Discount % (SpinBox)
        spin_d = QDoubleSpinBox()
        spin_d.setRange(0.0, 100.0)
        spin_d.setValue(0.0)
        spin_d.setDecimals(2)
        spin_d.setAlignment(Qt.AlignCenter)
        spin_d.setSuffix(" %")
        spin_d.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 9, spin_d)

        # 10. Total HT
        item_tht = QTableWidgetItem("0.00")
        item_tht.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cart_table.setItem(row, 10, item_tht)

        # 11. TVA %
        tva_pct = float(batch.get('Selling_TVA_Percent') or 0.0)
        item_tva = QTableWidgetItem(f"{tva_pct:.1f}%")
        item_tva.setData(Qt.UserRole, tva_pct)
        item_tva.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row, 11, item_tva)

        # 12. Total TTC
        item_ttc = QTableWidgetItem("0.00")
        item_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item_ttc.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.cart_table.setItem(row, 12, item_ttc)

        self.calculate_totals()

    def _remove_cart_row(self, btn):
        for r in range(self.cart_table.rowCount()):
            if self.cart_table.cellWidget(r, 0) == btn:
                self.cart_table.removeRow(r)
                break
        self.calculate_totals()

    def clear_cart(self):
        self.cart_table.setRowCount(0)
        self.calculate_totals()

    def calculate_totals(self):
        grand_ht = 0.0
        grand_remise = 0.0
        grand_tva = 0.0
        grand_ttc = 0.0

        for r in range(self.cart_table.rowCount()):
            spin_p = self.cart_table.cellWidget(r, 7)
            spin_q = self.cart_table.cellWidget(r, 8)
            spin_d = self.cart_table.cellWidget(r, 9)
            item_tva = self.cart_table.item(r, 11)

            if not (spin_p and spin_q and spin_d):
                continue

            price = spin_p.value()
            qty = spin_q.value()
            remise_pct = spin_d.value()
            tva_pct = float(item_tva.data(Qt.UserRole) or 0.0) if item_tva else 0.0

            raw_ht = price * qty
            discount_amount = raw_ht * (remise_pct / 100.0)
            net_ht = raw_ht - discount_amount
            tva_amount = net_ht * (tva_pct / 100.0)
            line_ttc = net_ht + tva_amount

            grand_ht += net_ht
            grand_remise += discount_amount
            grand_tva += tva_amount
            grand_ttc += line_ttc

            # Update row cells
            item_tht = self.cart_table.item(r, 10)
            if item_tht:
                item_tht.setText(format_money(net_ht))
            item_ttc = self.cart_table.item(r, 12)
            if item_ttc:
                item_ttc.setText(format_money(line_ttc))

        self.lbl_summary_ht.setText(f"Total HT : {format_money(grand_ht)} DA")
        self.lbl_summary_remise.setText(f"Remise : {format_money(grand_remise)} DA")
        self.lbl_summary_tva.setText(f"TVA : {format_money(grand_tva)} DA")
        self.lbl_summary_net_ttc.setText(f"NET À PAYER : {format_money(grand_ttc)} DA")

    def _collect_cart_items(self):
        items = []
        for r in range(self.cart_table.rowCount()):
            item_p = self.cart_table.item(r, 2)
            if not item_p:
                continue
            batch = item_p.data(Qt.UserRole)
            if not batch:
                continue

            spin_p = self.cart_table.cellWidget(r, 7)
            spin_q = self.cart_table.cellWidget(r, 8)
            spin_d = self.cart_table.cellWidget(r, 9)
            item_tva = self.cart_table.item(r, 11)

            tva_pct = float(item_tva.data(Qt.UserRole) or 0.0) if item_tva else 0.0

            items.append({
                'batch_id': batch['Batch_ID'],
                'product_id': batch['Product_ID'],
                'product_name': batch.get('Product_Name', ''),
                'lot_number': batch.get('Lot_Number', ''),
                'expiry_date': str(batch.get('Expiry_Date') or ''),
                'qty_sold': spin_q.value(),
                'unit_price_ht': spin_p.value(),
                'discount_percent': spin_d.value(),
                'tva_percent': tva_pct
            })
        return items

    def _get_current_user_id(self):
        try:
            main_window = self.window()
            user = getattr(main_window, 'current_user', None)
            if isinstance(user, dict):
                return user.get('User_ID') or user.get('id')
        except Exception:
            pass
        return None

    def validate_wholesale_sale(self):
        client = self._get_current_client()
        if not client:
            QMessageBox.warning(self, "Client", "Veuillez sélectionner un client B2B.")
            return

        client_id = client['Client_ID']
        cart_items = self._collect_cart_items()
        if not cart_items:
            QMessageBox.warning(self, "Panier", "Le panier est vide. Veuillez ajouter des produits.")
            return

        doc_type = self.cb_doc_type.currentData()
        order_date_str = self.date_order.date().toString("yyyy-MM-dd")
        due_date_str = self.date_due.date().toString("yyyy-MM-dd")
        payment_method = self.cb_payment_method.currentData()

        # Check credit limit alert
        limit = float(client.get('Credit_Limit') or 0.0)
        curr_bal = float(client.get('Current_Balance') or 0.0)
        grand_ttc = sum(
            (it['qty_sold'] * it['unit_price_ht'] * (1 - it['discount_percent']/100.0)) * (1 + it['tva_percent']/100.0)
            for it in cart_items
        )

        if payment_method == 'Credit' and limit > 0 and (curr_bal + grand_ttc) > limit:
            diff = (curr_bal + grand_ttc) - limit
            res = QMessageBox.warning(
                self,
                "Dépassement de Plafond de Crédit",
                f"Attention : Cette vente porte l'encours du client à {format_money(curr_bal + grand_ttc)} DA,\n"
                f"dépassant le plafond autorisé de {format_money(limit)} DA (Excédent: {format_money(diff)} DA).\n\n"
                f"Souhaitez-vous quand même poursuivre la validation ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res != QMessageBox.Yes:
                return

        # Execute Document Creation
        success, result = self.data_manager.sales.create_wholesale_document(
            client_id=client_id,
            doc_type=doc_type,
            order_date=order_date_str,
            due_date=due_date_str,
            cart_items=cart_items,
            payment_method=payment_method,
            user_id=self._get_current_user_id()
        )

        if not success:
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement du document :\n{result.get('message')}")
            return

        doc_no = result.get('doc_no')
        invoice_id = result.get('invoice_id')
        deducted = result.get('stock_deducted')

        msg = f"Document '{doc_no}' ({doc_type}) enregistré avec succès !"
        if deducted:
            msg += "\n\n• Le stock correspondant a été déduit atomiquement."
        else:
            msg += "\n\n• Document enregistré en brouillon (aucun mouvement de stock)."

        # Prompt for PDF generation
        reply = QMessageBox.information(
            self,
            "Validation Réussie",
            f"{msg}\n\nSouhaitez-vous générer et imprimer le document PDF (A4) maintenant ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._export_document_pdf(invoice_id, doc_no, doc_type, client, cart_items, order_date_str, due_date_str)

        self.clear_cart()
        self.load_initial_data()

    def _export_document_pdf(self, invoice_id, doc_no, doc_type, client, cart_items, order_date_str, due_date_str):
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "PDF", "La bibliothèque ReportLab n'est pas installée.")
            return

        safe_doc_no = doc_no.replace('/', '_')
        default_filename = f"{doc_type.replace(' ', '_')}_{safe_doc_no}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Enregistrer le document {doc_type}", default_filename, "Fichiers PDF (*.pdf)"
        )
        if not file_path:
            return

        try:
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm
            )
            styles = getSampleStyleSheet()
            normal_style = styles['Normal']
            title_style = ParagraphStyle(
                'WholesaleTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#007572'),
                spaceAfter=6,
                alignment=1
            )
            story = []

            # Company Settings Header
            company_settings = {}
            if hasattr(self.data_manager, 'company_settings'):
                company_settings = self.data_manager.company_settings.get_settings()

            company_name = company_settings.get('Company_Name') or "ENTREPRISE GROS & DISTRIBUTION"
            company_phone = company_settings.get('Phone') or ""
            company_address = company_settings.get('Address') or ""

            header_html = f"<b>{company_name}</b><br/>{company_address}<br/>Tél: {company_phone}"
            story.append(Paragraph(header_html, ParagraphStyle('HeaderM', parent=normal_style, fontSize=9, textColor=colors.HexColor('#475569'))))
            story.append(Spacer(1, 10))

            # Document Title
            story.append(Paragraph(f"{doc_type.upper()} N° {doc_no}", title_style))
            story.append(Paragraph(f"Date : <b>{order_date_str}</b> | Échéance : <b>{due_date_str}</b>", ParagraphStyle('Sub', parent=normal_style, alignment=1, fontSize=10)))
            story.append(Spacer(1, 12))

            # Client Info Box
            c_info = [
                [Paragraph(f"<b>Client B2B :</b> {client.get('Client_Name')}", normal_style),
                 Paragraph(f"<b>Catégorie :</b> {client.get('Price_Tier', 'Prix_1')}", normal_style)],
                [Paragraph(f"<b>Contact :</b> {client.get('Contact_Person', '-')}", normal_style),
                 Paragraph(f"<b>Téléphone :</b> {client.get('Phone', '-')}", normal_style)],
                [Paragraph(f"<b>Ville :</b> {client.get('City', '-')}", normal_style),
                 Paragraph(f"<b>NIF / RC :</b> {client.get('Tax_ID_Number', '-')} / {client.get('Commercial_Reg_No', '-')}", normal_style)]
            ]
            t_c = Table(c_info, colWidths=[9.5 * cm, 8.5 * cm])
            t_c.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t_c)
            story.append(Spacer(1, 14))

            # Items Grid
            grid_data = [["Désignation Produit", "Lot", "Péremp.", "Prix Unit. HT", "Qté", "Remise", "Total HT", "TTC"]]
            tot_ht = 0.0
            tot_ttc = 0.0
            for it in cart_items:
                p = it['unit_price_ht']
                q = it['qty_sold']
                d = it['discount_percent']
                tva = it['tva_percent']
                l_ht = p * q * (1 - d/100.0)
                l_ttc = l_ht * (1 + tva/100.0)
                tot_ht += l_ht
                tot_ttc += l_ttc
                grid_data.append([
                    it['product_name'],
                    it['lot_number'],
                    it['expiry_date'],
                    f"{format_money(p)}",
                    f"{q:.2f}",
                    f"{d:.1f}%" if d > 0 else "-",
                    f"{format_money(l_ht)}",
                    f"{format_money(l_ttc)}"
                ])

            t_grid = Table(grid_data, colWidths=[5.5 * cm, 2.2 * cm, 2.0 * cm, 2.3 * cm, 1.5 * cm, 1.5 * cm, 2.3 * cm, 2.3 * cm], repeatRows=1)
            t_grid.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007572')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            story.append(t_grid)
            story.append(Spacer(1, 14))

            # Total Summary Table
            tot_data = [
                ["Total Brut HT :", f"{format_money(tot_ht)} DA"],
                ["Total TVA :", f"{format_money(tot_ttc - tot_ht)} DA"],
                ["NET À PAYER TTC :", f"{format_money(tot_ttc)} DA"]
            ]
            t_tot = Table(tot_data, colWidths=[5 * cm, 4 * cm])
            t_tot.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 2), (-1, 2), 10),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e6f4f1')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#007572')),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            
            # Align right
            t_wrap = Table([["", t_tot]], colWidths=[10 * cm, 9 * cm])
            t_wrap.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
            story.append(t_wrap)
            story.append(Spacer(1, 25))

            # Signatures
            sign_data = [
                [Paragraph("<b>Visa & Cachet de l'Entreprise :</b>", normal_style),
                 Paragraph("<b>Bon pour Accord & Réception Client :</b>", normal_style)]
            ]
            t_sign = Table(sign_data, colWidths=[9.5 * cm, 9.5 * cm])
            story.append(t_sign)

            doc.build(story)
            os.startfile(file_path)

        except Exception as e:
            logging.error(f"Wholesale PDF Error: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur PDF", f"Impossible d'exporter le document PDF :\n{e}")

    def _create_quick_client(self):
        dlg = ClientDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                cid = self.data_manager.clients.add_client(**data)
                if cid:
                    self.load_initial_data()
                    for idx in range(self.cb_client.count()):
                        c = self.cb_client.itemData(idx)
                        if isinstance(c, dict) and c.get('Client_ID') == cid:
                            self.cb_client.setCurrentIndex(idx)
                            break

    def _open_client_statement(self):
        client = self._get_current_client()
        if not client:
            QMessageBox.warning(self, "Client", "Veuillez sélectionner un client B2B.")
            return
        dlg = ClientStatementDialog(self.data_manager, client['Client_ID'], self)
        dlg.exec()
