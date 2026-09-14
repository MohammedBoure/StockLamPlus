# ui/widgets/sales/debts_management_tab.py

import csv
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter, QGroupBox,
    QMessageBox, QFileDialog, QDoubleSpinBox, QComboBox, QDialog,
    QFormLayout, QDateEdit, QLineEdit, QRadioButton, QButtonGroup, QMenu
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont, QAction

from ui.formatting import format_money
from ui.widgets.sales.searchable_client_combo import SearchableClientComboBox
from ui.widgets.sales.invoice_payment_dialog import InvoicePaymentDialog
from ui.widgets.master_data.client_statement_dialog import ClientStatementDialog
from ui.widgets.sales_history.pdf_export import export_invoice_to_pdf


class GlobalPaymentDialog(QDialog):
    """
    Dialogue de règlement global / acompte client.
    Permet de solder la dette globale ou d'effectuer une avance libre,
    avec option de ventilation automatique FIFO sur les factures impayées.
    """

    def __init__(self, data_manager, client_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_data = client_data
        self.client_id = client_data.get('Client_ID')
        self.client_name = client_data.get('Client_Name') or f"Client #{self.client_id}"
        self.current_balance = float(client_data.get('Current_Balance') or 0.0)
        self.credit_limit = float(client_data.get('Credit_Limit') or 0.0)

        self.setWindowTitle(f"💳 Règlement Global / Acompte - {self.client_name}")
        self.resize(540, 520)
        self._init_ui()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Title
        lbl_title = QLabel("💳 Enregistrement d'un Règlement Global ou Acompte")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #007572;")
        layout.addWidget(lbl_title)

        # Client Summary Card
        summary_group = QGroupBox("Situation Financière du Client")
        summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #f8fafc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
        """)
        summary_layout = QFormLayout(summary_group)
        summary_layout.setSpacing(8)

        lbl_client = QLabel(self.client_name)
        lbl_client.setStyleSheet("font-size: 13px; font-weight: bold;")
        summary_layout.addRow("Client :", lbl_client)

        lbl_bal = QLabel(f"{format_money(self.current_balance)} DA")
        lbl_bal.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;" if self.current_balance > 0 else "font-size: 14px; font-weight: bold; color: #059669;")
        summary_layout.addRow("Solde Dû Actuel :", lbl_bal)

        lbl_limit = QLabel(f"{format_money(self.credit_limit)} DA" if self.credit_limit > 0 else "Illimité")
        summary_layout.addRow("Plafond de Crédit :", lbl_limit)

        layout.addWidget(summary_group)

        # Form Parameters
        form_group = QGroupBox("Paramètres de Règlement")
        form_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
        """)
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)

        # Payment Date
        self.edit_date = QDateEdit(QDate.currentDate())
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        self.edit_date.setMinimumHeight(30)
        form_layout.addRow("Date de règlement :", self.edit_date)

        # Amount
        amt_container = QHBoxLayout()
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999999.0)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSingleStep(500.0)
        self.spin_amount.setSuffix(" DA")
        initial_val = self.current_balance if self.current_balance > 0 else 1000.0
        self.spin_amount.setValue(initial_val)
        self.spin_amount.setMinimumHeight(32)
        self.spin_amount.setStyleSheet("font-size: 14px; font-weight: bold; color: #007572;")
        amt_container.addWidget(self.spin_amount, 1)

        btn_full = QPushButton("Solder Tout")
        btn_full.setCursor(Qt.PointingHandCursor)
        btn_full.setStyleSheet("padding: 4px 8px; font-size: 11px; background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; border-radius: 3px;")
        btn_full.clicked.connect(lambda: self.spin_amount.setValue(max(0.01, self.current_balance)))
        amt_container.addWidget(btn_full)

        form_layout.addRow("Montant versé :", amt_container)

        # Payment Method
        self.cb_method = QComboBox()
        methods = [
            ("Espèces", "Espèce"),
            ("Chèque", "Chèque"),
            ("Virement bancaire", "Virement"),
            ("Versement bancaire", "Versement"),
            ("Carte bancaire", "Carte")
        ]
        for label, val in methods:
            self.cb_method.addItem(label, val)
        self.cb_method.setMinimumHeight(30)
        form_layout.addRow("Mode de paiement :", self.cb_method)

        # Allocation Mode
        alloc_vbox = QVBoxLayout()
        self.rb_fifo = QRadioButton("Ventilation automatique FIFO (imputer sur factures les plus anciennes)")
        self.rb_fifo.setChecked(True)
        self.rb_fifo.setStyleSheet("font-size: 12px; color: #0f766e; font-weight: 600;")

        self.rb_free = QRadioButton("Acompte libre non lettré (déduit directement du solde global)")
        self.rb_free.setStyleSheet("font-size: 12px; color: #475569;")

        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.rb_fifo, 1)
        self.btn_group_mode.addButton(self.rb_free, 2)

        alloc_vbox.addWidget(self.rb_fifo)
        alloc_vbox.addWidget(self.rb_free)
        form_layout.addRow("Mode d'imputation :", alloc_vbox)

        # Reference
        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Ex: N° Chèque, Référence virement...")
        self.edit_ref.setMinimumHeight(30)
        form_layout.addRow("Référence / N° Pièce :", self.edit_ref)

        # Notes
        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Observations ou remarques...")
        self.edit_notes.setMinimumHeight(30)
        form_layout.addRow("Observations :", self.edit_notes)

        layout.addWidget(form_group)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setMinimumHeight(34)
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("💾 Valider le Règlement")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setMinimumHeight(34)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        self.btn_submit.clicked.connect(self._validate_and_submit)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_submit)
        layout.addLayout(btn_layout)

    def _validate_and_submit(self):
        amount = self.spin_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Veuillez saisir un montant supérieur à zéro.")
            return

        pay_date = self.edit_date.date().toString("yyyy-MM-dd")
        method = self.cb_method.currentData()
        ref = self.edit_ref.text().strip() or None
        notes = self.edit_notes.text().strip() or None
        auto_fifo = self.rb_fifo.isChecked()
        user_id = self._current_user_id()

        try:
            res = self.data_manager.client_payments.add_global_payment(
                client_id=self.client_id,
                payment_date=pay_date,
                amount=amount,
                payment_method=method,
                reference=ref,
                notes=notes,
                auto_allocate_fifo=auto_fifo,
                user_id=user_id
            )

            if res and res.get('success'):
                inv_count = len(res.get('invoices_affected') or [])
                alloc_amt = res.get('allocated_to_invoices', 0.0)
                free_amt = res.get('free_advance', 0.0)

                msg = f"Règlement de {format_money(amount)} DA validé avec succès !\n\n"
                if auto_fifo:
                    msg += f"• Montant lettré : {format_money(alloc_amt)} DA ({inv_count} factures affectées)\n"
                    if free_amt > 0:
                        msg += f"• Surplus en acompte libre : {format_money(free_amt)} DA\n"
                else:
                    msg += f"• Enregistré intégralement en acompte libre : {format_money(amount)} DA\n"

                QMessageBox.information(self, "Règlement Enregistré", msg)
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'enregistrement du règlement.")
        except Exception as e:
            logging.error(f"Error submitting global payment: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement : {e}")


class ClientDebtAuditDialog(QDialog):
    """
    Modal affichant l'audit d'intégrité comptable du solde d'un client.
    """

    def __init__(self, audit_result, parent=None):
        super().__init__(parent)
        self.audit = audit_result
        self.setWindowTitle(f"🔍 Audit Comptable - {self.audit.get('client_name', '')}")
        self.resize(500, 420)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        is_balanced = self.audit.get('is_balanced', False)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #dcfce7; border: 1px solid #86efac; border-radius: 4px; padding: 12px;"
            if is_balanced else
            "background-color: #fee2e2; border: 1px solid #fca5a5; border-radius: 4px; padding: 12px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(0, 0, 0, 0)
        title_text = "✅ INTÉGRITÉ COMPTABLE CONFORME" if is_balanced else "⚠️ ÉCART DE SOLDE DÉTECTÉ"
        lbl_status = QLabel(title_text)
        lbl_status.setStyleSheet("font-size: 14px; font-weight: bold; color: #166534;" if is_balanced else "font-size: 14px; font-weight: bold; color: #991b1b;")
        h_layout.addWidget(lbl_status)

        layout.addWidget(header_frame)

        form_group = QGroupBox("Détail de la Réconciliation")
        form_group.setStyleSheet("font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px; margin-top: 6px; padding-top: 8px;")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)

        form_layout.addRow("Client :", QLabel(str(self.audit.get('client_name', ''))))
        form_layout.addRow("Solde Actuel Enregistré :", QLabel(f"{format_money(self.audit.get('current_balance', 0.0))} DA"))
        form_layout.addRow("Solde Théorique Reconstitué :", QLabel(f"{format_money(self.audit.get('expected_balance', 0.0))} DA"))

        discrepancy = self.audit.get('discrepancy', 0.0)
        lbl_disc = QLabel(f"{format_money(discrepancy)} DA")
        lbl_disc.setStyleSheet("font-weight: bold; color: #16a34a;" if abs(discrepancy) < 0.01 else "font-weight: bold; color: #dc2626;")
        form_layout.addRow("Écart Net :", lbl_disc)

        form_layout.addRow("Total Facturé & BL (+) :", QLabel(f"{format_money(self.audit.get('total_invoiced', 0.0))} DA ({self.audit.get('count_invoices', 0)} pièces)"))
        form_layout.addRow("Total Encaissé & Règlements (-) :", QLabel(f"{format_money(self.audit.get('total_paid', 0.0))} DA ({self.audit.get('count_payments', 0)} paiements)"))
        form_layout.addRow("Total Avoirs / Retours (-) :", QLabel(f"{format_money(self.audit.get('total_credit_notes', 0.0))} DA ({self.audit.get('count_credit_notes', 0)} avoirs)"))

        layout.addWidget(form_group)

        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #007572; color: white; font-weight: bold; padding: 6px 18px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)

        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn_close)
        layout.addLayout(h_btn)


class DebtsManagementTab(QWidget):
    """
    Interface dédiée à la Gestion des Créances et Suivi des Dettes Clients.
    Fournit des KPIs en temps réel, un filtrage avancé, un tableau maître des débiteurs,
    un panneau de détail (drill-down) des factures impayées et des actions rapides
    (règlement global FIFO, relevé de compte, impression de facture, audit).
    """

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.clients_summary = []
        self.selected_client_id = None
        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Top KPI / Analytics Cards
        self._build_kpi_cards(main_layout)

        # 2. Filter Bar
        self._build_filter_bar(main_layout)

        # 3. Master-Detail Splitter
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)

        # Master Table (Clients débiteurs)
        self.master_container = QFrame()
        master_layout = QVBoxLayout(self.master_container)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(4)

        lbl_master_header = QLabel("📋 Répertoire des Clients Débiteurs")
        lbl_master_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b; padding-left: 2px;")
        master_layout.addWidget(lbl_master_header)

        self.table_clients = QTableWidget()
        cols = [
            "ID", "Nom du Client", "Téléphone", "Plafond Crédit",
            "Total Facturé", "Total Encaissé", "Solde Dû Actuel",
            "Dernier Règlement", "Statut / Alerte", "Actions"
        ]
        self.table_clients.setColumnCount(len(cols))
        self.table_clients.setHorizontalHeaderLabels(cols)
        self.table_clients.setColumnHidden(0, True)
        self.table_clients.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col_idx in [2, 3, 4, 5, 6, 7, 8, 9]:
            self.table_clients.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)

        self.table_clients.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_clients.setSelectionMode(QTableWidget.SingleSelection)
        self.table_clients.setAlternatingRowColors(True)
        self.table_clients.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_clients.itemSelectionChanged.connect(self._on_client_selection_changed)
        self.table_clients.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_clients.customContextMenuRequested.connect(self._show_client_context_menu)

        master_layout.addWidget(self.table_clients)
        self.splitter.addWidget(self.master_container)

        # Detail Panel (Factures impayées du client sélectionné)
        self.detail_container = QFrame()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 6, 0, 0)
        detail_layout.setSpacing(6)

        detail_header_layout = QHBoxLayout()
        self.lbl_detail_title = QLabel("📦 Factures & Pièces Impayées : (Sélectionnez un client)")
        self.lbl_detail_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #007572;")
        detail_header_layout.addWidget(self.lbl_detail_title)
        detail_header_layout.addStretch()

        self.btn_detail_global_pay = QPushButton("💳 Règlement Global / Acompte")
        self.btn_detail_global_pay.setCursor(Qt.PointingHandCursor)
        self.btn_detail_global_pay.setStyleSheet("""
            QPushButton {
                background-color: #007572; color: white; font-weight: bold;
                padding: 4px 14px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background-color: #005a57; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.btn_detail_global_pay.setEnabled(False)
        self.btn_detail_global_pay.clicked.connect(self._open_global_payment_dialog)
        detail_header_layout.addWidget(self.btn_detail_global_pay)

        self.btn_detail_statement = QPushButton("📄 Relevé de Compte")
        self.btn_detail_statement.setCursor(Qt.PointingHandCursor)
        self.btn_detail_statement.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #007572; border: 1.5px solid #007572;
                font-weight: bold; padding: 4px 14px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background-color: #e6f4f1; }
            QPushButton:disabled { border-color: #cbd5e1; color: #94a3b8; }
        """)
        self.btn_detail_statement.setEnabled(False)
        self.btn_detail_statement.clicked.connect(self._open_client_statement_dialog)
        detail_header_layout.addWidget(self.btn_detail_statement)

        detail_layout.addLayout(detail_header_layout)

        self.table_invoices = QTableWidget()
        inv_cols = [
            "Facture N°", "Date", "Date d'Échéance", "Retard (Jours)",
            "Total TTC", "Déjà Payé", "Reste à Payer", "Statut", "Actions"
        ]
        self.table_invoices.setColumnCount(len(inv_cols))
        self.table_invoices.setHorizontalHeaderLabels(inv_cols)
        self.table_invoices.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c_idx in [1, 2, 3, 4, 5, 6, 7, 8]:
            self.table_invoices.horizontalHeader().setSectionResizeMode(c_idx, QHeaderView.ResizeToContents)
        self.table_invoices.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_invoices.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_invoices.setAlternatingRowColors(True)

        detail_layout.addWidget(self.table_invoices)
        self.splitter.addWidget(self.detail_container)

        self.splitter.setSizes([380, 260])
        main_layout.addWidget(self.splitter, 1)

    def _build_kpi_cards(self, parent_layout):
        kpi_frame = QFrame()
        kpi_frame.setStyleSheet("""
            QFrame#KpiCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 10px 14px;
            }
        """)
        kpi_layout = QHBoxLayout(kpi_frame)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(12)

        def make_card(title, value_attr, color_hex, bg_color):
            card = QFrame()
            card.setObjectName("KpiCard")
            card.setStyleSheet(f"""
                QFrame#KpiCard {{
                    background-color: {bg_color};
                    border: 1px solid #cbd5e1;
                    border-left: 4px solid {color_hex};
                    border-radius: 4px;
                    padding: 8px 12px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(0, 0, 0, 0)
            c_lay.setSpacing(3)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; text-transform: uppercase;")
            lbl_v = QLabel("0.00 DA")
            lbl_v.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color_hex};")
            c_lay.addWidget(lbl_t)
            c_lay.addWidget(lbl_v)
            setattr(self, value_attr, lbl_v)
            return card

        kpi_layout.addWidget(make_card("Total Créances Clients", "lbl_kpi_total_receivables", "#007572", "#f0fdfa"), 1)
        kpi_layout.addWidget(make_card("Créances Échues (En Retard)", "lbl_kpi_overdue_receivables", "#dc2626", "#fef2f2"), 1)
        kpi_layout.addWidget(make_card("Clients Débiteurs", "lbl_kpi_debtor_count", "#d97706", "#fffbeb"), 1)
        kpi_layout.addWidget(make_card("Règlements ce Mois", "lbl_kpi_month_recovered", "#16a34a", "#f0fdf4"), 1)

        parent_layout.addWidget(kpi_frame)

    def _build_filter_bar(self, parent_layout):
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QLabel {
                font-weight: 600;
                font-size: 12px;
                color: #334155;
            }
        """)
        f_layout = QHBoxLayout(filter_frame)
        f_layout.setContentsMargins(6, 6, 6, 6)
        f_layout.setSpacing(10)

        # Searchable Client Filter
        f_layout.addWidget(QLabel("👤 Client :"))
        self.cb_client_filter = SearchableClientComboBox(self, placeholder="🔍 Nom ou Téléphone...")
        self.cb_client_filter.setMinimumWidth(220)
        self.cb_client_filter.client_changed.connect(self._on_client_filter_changed)
        f_layout.addWidget(self.cb_client_filter)

        # Status Filter
        f_layout.addWidget(QLabel("Statut :"))
        self.cb_status_filter = QComboBox()
        self.cb_status_filter.addItems([
            "Tous",
            "Dépassant le Plafond",
            "En Retard / Échues",
            "Actifs",
            "Soldés"
        ])
        self.cb_status_filter.setMinimumWidth(150)
        self.cb_status_filter.currentIndexChanged.connect(self.load_debtors_table)
        f_layout.addWidget(self.cb_status_filter)

        # Minimum Debt Threshold
        f_layout.addWidget(QLabel("Dette Min :"))
        self.spin_min_debt = QDoubleSpinBox()
        self.spin_min_debt.setRange(0.0, 99999999.0)
        self.spin_min_debt.setSingleStep(500.0)
        self.spin_min_debt.setDecimals(2)
        self.spin_min_debt.setSuffix(" DA")
        self.spin_min_debt.setValue(0.0)
        self.spin_min_debt.setMinimumWidth(110)
        self.spin_min_debt.valueChanged.connect(self.load_debtors_table)
        f_layout.addWidget(self.spin_min_debt)

        f_layout.addStretch(1)

        # Refresh Button
        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #007572; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 4px 12px; min-height: 28px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #e6f4f1; border-color: #007572; }
        """)
        btn_refresh.clicked.connect(self.refresh_all)
        f_layout.addWidget(btn_refresh)

        # Export CSV Button
        btn_export = QPushButton("📥 Exporter CSV")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1;
                border-radius: 4px; padding: 4px 12px; min-height: 28px; font-weight: 600; font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_export.clicked.connect(self.export_csv)
        f_layout.addWidget(btn_export)

        parent_layout.addWidget(filter_frame)

    def refresh_all(self):
        """Recharge l'intégralité des données : KPIs, clients débiteurs et détail."""
        self.load_kpis()
        self._reload_client_combo_list()
        self.load_debtors_table()

    def load_kpis(self):
        try:
            analytics = self.data_manager.clients.get_debts_analytics()
            total_rec = analytics.get('total_receivables', 0.0)
            overdue_rec = analytics.get('overdue_receivables', 0.0)
            debtor_cnt = analytics.get('debtor_clients_count', 0)
            rec_month = analytics.get('recovered_this_month', 0.0)

            self.lbl_kpi_total_receivables.setText(f"{format_money(total_rec)} DA")
            self.lbl_kpi_overdue_receivables.setText(f"{format_money(overdue_rec)} DA")
            self.lbl_kpi_debtor_count.setText(f"{debtor_cnt} client(s)")
            self.lbl_kpi_month_recovered.setText(f"{format_money(rec_month)} DA")
        except Exception as e:
            logging.error(f"Error loading debts KPIs: {e}")

    def _reload_client_combo_list(self):
        try:
            clients = self.data_manager.clients.get_all_clients()
            self.cb_client_filter.set_clients(clients)
        except Exception as e:
            logging.error(f"Error reloading clients combo list: {e}")

    def load_debtors_table(self):
        try:
            min_debt = self.spin_min_debt.value()
            filter_status = self.cb_status_filter.currentText()
            client_id = self.cb_client_filter.get_selected_client_id()

            summary = self.data_manager.clients.get_debtor_clients_summary(
                min_debt=min_debt,
                filter_status=filter_status
            )

            if client_id:
                summary = [c for c in summary if c.get('Client_ID') == client_id]

            self.clients_summary = summary
            self.table_clients.setSortingEnabled(False)
            self.table_clients.setRowCount(0)

            for row_idx, c in enumerate(summary):
                self.table_clients.insertRow(row_idx)

                # 0: ID
                c_id = c.get('Client_ID')
                it_id = QTableWidgetItem(str(c_id))
                it_id.setData(Qt.UserRole, c)
                self.table_clients.setItem(row_idx, 0, it_id)

                # 1: Nom du Client
                it_name = QTableWidgetItem(str(c.get('Client_Name') or ''))
                it_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_clients.setItem(row_idx, 1, it_name)

                # 2: Téléphone
                self.table_clients.setItem(row_idx, 2, QTableWidgetItem(str(c.get('Phone') or '-')))

                # 3: Plafond Crédit
                limit = float(c.get('Credit_Limit') or 0.0)
                it_limit = QTableWidgetItem(f"{format_money(limit)} DA" if limit > 0 else "Illimité")
                it_limit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 3, it_limit)

                # 4: Total Facturé
                invoiced = float(c.get('total_invoiced') or 0.0)
                it_inv = QTableWidgetItem(f"{format_money(invoiced)} DA")
                it_inv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 4, it_inv)

                # 5: Total Encaissé
                paid = float(c.get('total_paid') or 0.0)
                it_paid = QTableWidgetItem(f"{format_money(paid)} DA")
                it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 5, it_paid)

                # 6: Solde Dû Actuel
                bal = float(c.get('Current_Balance') or 0.0)
                it_bal = QTableWidgetItem(f"{format_money(bal)} DA")
                it_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_bal.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if bal > (limit if limit > 0 else 0):
                    it_bal.setForeground(QBrush(QColor("#b91c1c")))
                    it_bal.setBackground(QBrush(QColor("#fee2e2")))
                elif bal > 0:
                    it_bal.setForeground(QBrush(QColor("#b45309")))
                else:
                    it_bal.setForeground(QBrush(QColor("#15803d")))
                self.table_clients.setItem(row_idx, 6, it_bal)

                # 7: Dernier Règlement
                last_pay = str(c.get('Last_Payment_Date') or '-')
                self.table_clients.setItem(row_idx, 7, QTableWidgetItem(last_pay))

                # 8: Statut / Badge
                badge = c.get('Status_Badge', 'Normal')
                it_badge = QTableWidgetItem(badge)
                it_badge.setTextAlignment(Qt.AlignCenter)
                it_badge.setFont(QFont("Segoe UI", 8, QFont.Bold))
                if badge == "Plafond Dépassé":
                    it_badge.setBackground(QBrush(QColor("#fee2e2")))
                    it_badge.setForeground(QBrush(QColor("#b91c1c")))
                elif badge == "Alerte Retard":
                    it_badge.setBackground(QBrush(QColor("#ffedd5")))
                    it_badge.setForeground(QBrush(QColor("#c2410c")))
                elif badge == "Normal":
                    it_badge.setBackground(QBrush(QColor("#dcfce7")))
                    it_badge.setForeground(QBrush(QColor("#15803d")))
                else:
                    it_badge.setBackground(QBrush(QColor("#f1f5f9")))
                    it_badge.setForeground(QBrush(QColor("#64748b")))
                self.table_clients.setItem(row_idx, 8, it_badge)

                # 9: Actions container
                act_container = QWidget()
                act_container.setStyleSheet("background: transparent;")
                act_layout = QHBoxLayout(act_container)
                act_layout.setContentsMargins(2, 2, 2, 2)
                act_layout.setSpacing(4)

                btn_pay = QPushButton("💳 Solder")
                btn_pay.setCursor(Qt.PointingHandCursor)
                btn_pay.setStyleSheet("background-color: #007572; color: white; font-size: 11px; font-weight: bold; border-radius: 3px; padding: 3px 8px; border: none;")
                btn_pay.clicked.connect(lambda _, client_row=c: self._open_global_payment_dialog(client_row))
                act_layout.addWidget(btn_pay)

                btn_stmt = QPushButton("📄 Relevé")
                btn_stmt.setCursor(Qt.PointingHandCursor)
                btn_stmt.setStyleSheet("background-color: #f1f5f9; color: #0f766e; font-size: 11px; font-weight: bold; border-radius: 3px; padding: 3px 8px; border: 1px solid #cbd5e1;")
                btn_stmt.clicked.connect(lambda _, client_row=c: self._open_client_statement_dialog(client_row))
                act_layout.addWidget(btn_stmt)

                self.table_clients.setCellWidget(row_idx, 9, act_container)

            self.table_clients.setSortingEnabled(True)

            # Re-select previously selected or first
            if summary:
                self.table_clients.selectRow(0)
            else:
                self._clear_detail_table()

        except Exception as e:
            logging.error(f"Error loading debtors table: {e}", exc_info=True)

    def _on_client_filter_changed(self, client_id):
        self.load_debtors_table()

    def _on_client_selection_changed(self):
        row = self.table_clients.currentRow()
        if row < 0:
            self._clear_detail_table()
            return

        it = self.table_clients.item(row, 0)
        if not it:
            self._clear_detail_table()
            return

        client_data = it.data(Qt.UserRole)
        if not client_data:
            self._clear_detail_table()
            return

        self.selected_client_id = client_data.get('Client_ID')
        self._load_detail_invoices(client_data)

    def _clear_detail_table(self):
        self.selected_client_id = None
        self.lbl_detail_title.setText("📦 Factures & Pièces Impayées : (Sélectionnez un client)")
        self.btn_detail_global_pay.setEnabled(False)
        self.btn_detail_statement.setEnabled(False)
        self.table_invoices.setRowCount(0)

    def _load_detail_invoices(self, client_data):
        c_id = client_data.get('Client_ID')
        c_name = client_data.get('Client_Name') or f"Client #{c_id}"
        bal = float(client_data.get('Current_Balance') or 0.0)

        self.lbl_detail_title.setText(f"📦 Factures & Créances Impayées : {c_name} (Solde Total : {format_money(bal)} DA)")
        self.btn_detail_global_pay.setEnabled(True)
        self.btn_detail_statement.setEnabled(True)

        try:
            invoices = self.data_manager.clients.get_client_unpaid_invoices(c_id)
            self.table_invoices.setRowCount(0)

            for r_idx, inv in enumerate(invoices):
                self.table_invoices.insertRow(r_idx)

                # 0: Facture N°
                inv_no = inv.get('Invoice_No') or f"#{inv.get('Invoice_ID')}"
                it_no = QTableWidgetItem(inv_no)
                it_no.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_invoices.setItem(r_idx, 0, it_no)

                # 1: Date
                inv_date = str(inv.get('Invoice_Date') or '-')[:10]
                self.table_invoices.setItem(r_idx, 1, QTableWidgetItem(inv_date))

                # 2: Date d'Échéance
                due_date = str(inv.get('Due_Date') or '-')[:10]
                self.table_invoices.setItem(r_idx, 2, QTableWidgetItem(due_date))

                # 3: Retard (Jours)
                days = inv.get('Days_Overdue', 0)
                is_overdue = inv.get('Is_Overdue', False)
                it_retard = QTableWidgetItem(f"+{days} j" if days > 0 else "0 j")
                it_retard.setTextAlignment(Qt.AlignCenter)
                if is_overdue:
                    it_retard.setForeground(QBrush(QColor("#b91c1c")))
                    it_retard.setBackground(QBrush(QColor("#fee2e2")))
                    it_retard.setFont(QFont("Segoe UI", 9, QFont.Bold))
                else:
                    it_retard.setForeground(QBrush(QColor("#0284c7")))
                self.table_invoices.setItem(r_idx, 3, it_retard)

                # 4: Total TTC
                ttc = float(inv.get('Total_Amount_TTC') or 0.0)
                it_ttc = QTableWidgetItem(f"{format_money(ttc)} DA")
                it_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_invoices.setItem(r_idx, 4, it_ttc)

                # 5: Déjà Payé
                paid = float(inv.get('Paid_Amount') or 0.0)
                it_paid = QTableWidgetItem(f"{format_money(paid)} DA")
                it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_invoices.setItem(r_idx, 5, it_paid)

                # 6: Reste à Payer
                rem = float(inv.get('Remaining_Balance') or (ttc - paid))
                it_rem = QTableWidgetItem(f"{format_money(rem)} DA")
                it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_rem.setFont(QFont("Segoe UI", 9, QFont.Bold))
                it_rem.setForeground(QBrush(QColor("#dc2626")))
                self.table_invoices.setItem(r_idx, 6, it_rem)

                # 7: Statut
                self.table_invoices.setItem(r_idx, 7, QTableWidgetItem(str(inv.get('Status') or 'Validated')))

                # 8: Actions Container
                act_box = QWidget()
                act_box.setStyleSheet("background: transparent;")
                act_lay = QHBoxLayout(act_box)
                act_lay.setContentsMargins(2, 2, 2, 2)
                act_lay.setSpacing(4)

                btn_pay_inv = QPushButton("💳 Encaisser")
                btn_pay_inv.setCursor(Qt.PointingHandCursor)
                btn_pay_inv.setStyleSheet("""
                    QPushButton {
                        background-color: #0f766e; color: white; font-weight: bold;
                        font-size: 11px; border-radius: 3px; padding: 3px 8px; border: none;
                    }
                    QPushButton:hover { background-color: #115e59; }
                """)
                # Prepare invoice data dict for InvoicePaymentDialog
                inv_dict = {
                    'Invoice_ID': inv.get('Invoice_ID'),
                    'Invoice_No': inv_no,
                    'Client_ID': c_id,
                    'Client_Name': c_name,
                    'Total_Amount_TTC': ttc,
                    'Paid_Amount': paid,
                    'Invoice_Date': inv_date,
                    'Due_Date': due_date
                }
                btn_pay_inv.clicked.connect(lambda _, iv=inv_dict: self._open_invoice_payment(iv))
                act_lay.addWidget(btn_pay_inv)

                btn_print_inv = QPushButton("🖨️ Imprimer")
                btn_print_inv.setCursor(Qt.PointingHandCursor)
                btn_print_inv.setStyleSheet("""
                    QPushButton {
                        background-color: #f1f5f9; color: #334155; font-weight: 600;
                        font-size: 11px; border-radius: 3px; padding: 3px 8px; border: 1px solid #cbd5e1;
                    }
                    QPushButton:hover { background-color: #e2e8f0; }
                """)
                btn_print_inv.clicked.connect(lambda _, iv=inv_dict: self._print_invoice(iv))
                act_lay.addWidget(btn_print_inv)

                self.table_invoices.setCellWidget(r_idx, 8, act_box)

        except Exception as e:
            logging.error(f"Error loading detail invoices: {e}", exc_info=True)

    def _open_global_payment_dialog(self, client_row=None):
        if not client_row:
            row = self.table_clients.currentRow()
            if row >= 0 and self.table_clients.item(row, 0):
                client_row = self.table_clients.item(row, 0).data(Qt.UserRole)

        if not client_row:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client.")
            return

        dlg = GlobalPaymentDialog(self.data_manager, client_row, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()

    def _open_client_statement_dialog(self, client_row=None):
        if not client_row:
            row = self.table_clients.currentRow()
            if row >= 0 and self.table_clients.item(row, 0):
                client_row = self.table_clients.item(row, 0).data(Qt.UserRole)

        if not client_row:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client.")
            return

        c_id = client_row.get('Client_ID')
        dlg = ClientStatementDialog(self.data_manager, c_id, self)
        dlg.exec()

    def _open_invoice_payment(self, invoice_data):
        dlg = InvoicePaymentDialog(self.data_manager, invoice_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()

    def _print_invoice(self, invoice_data):
        try:
            export_invoice_to_pdf(self.data_manager, invoice_data, self)
        except Exception as e:
            logging.error(f"Error printing invoice: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec de l'impression de la facture : {e}")

    def _audit_client(self, client_row):
        c_id = client_row.get('Client_ID')
        audit_res = self.data_manager.clients.audit_client_debt_balance(c_id)
        dlg = ClientDebtAuditDialog(audit_res, self)
        dlg.exec()

    def _show_client_context_menu(self, pos):
        item = self.table_clients.itemAt(pos)
        if not item:
            return
        row = item.row()
        id_item = self.table_clients.item(row, 0)
        if not id_item:
            return
        client_data = id_item.data(Qt.UserRole)
        if not client_data:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #007572;
                color: white;
            }
        """)

        act_pay = menu.addAction("💳 Règlement Global / Acompte")
        act_pay.triggered.connect(lambda: self._open_global_payment_dialog(client_data))

        act_stmt = menu.addAction("📄 Relevé de Compte Détaillé")
        act_stmt.triggered.connect(lambda: self._open_client_statement_dialog(client_data))

        act_audit = menu.addAction("🔍 Audit Intégrité Comptable")
        act_audit.triggered.connect(lambda: self._audit_client(client_data))

        menu.exec(self.table_clients.viewport().mapToGlobal(pos))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter les Créances Clients", "creances_clients.csv", "CSV (*.csv)")
        if not path:
            return
        headers = [
            "ID Client", "Nom du Client", "Telephone", "Plafond Credit (DA)",
            "Total Facture (DA)", "Total Encaisse (DA)", "Solde Du Actuel (DA)",
            "Dernier Reglement", "Statut"
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for c in self.clients_summary:
                    writer.writerow([
                        c.get("Client_ID"),
                        c.get("Client_Name") or "-",
                        c.get("Phone") or "-",
                        c.get("Credit_Limit") or 0.0,
                        c.get("total_invoiced") or 0.0,
                        c.get("total_paid") or 0.0,
                        c.get("Current_Balance") or 0.0,
                        c.get("Last_Payment_Date") or "-",
                        c.get("Status_Badge") or "-"
                    ])
            QMessageBox.information(self, "Export", "Données des créances exportées avec succès.")
        except OSError as exc:
            QMessageBox.warning(self, "Export", f"Échec de l'exportation CSV : {exc}")
