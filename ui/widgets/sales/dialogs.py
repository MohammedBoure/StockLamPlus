# ui/widgets/sales/dialogs.py

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QWidget, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDoubleSpinBox,
    QPushButton, QFrame, QGridLayout, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush
from ui.formatting import format_money
from ui.widgets.master_data.dialogs import BaseDialog

class ClientDialog(BaseDialog):
    """Fenêtre pour ajouter ou modifier un client."""
    def __init__(self, parent=None, data=None):
        title = "Modifier le Client" if data else "Ajouter un Client"
        super().__init__(title, parent)
        self.resize(500, 450)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nom de l'entreprise ou du client *")
        
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Personne à contacter")
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Numéro de téléphone")
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Adresse Email")
        
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Adresse")
        
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Ville")
        
        self.tax_id_input = QLineEdit()
        self.tax_id_input.setPlaceholderText("NIF / N° d'identification fiscale")
        
        self.commercial_reg_input = QLineEdit()
        self.commercial_reg_input.setPlaceholderText("RC / Registre de Commerce")

        layout.addRow("Nom du Client * :", self.name_input)
        layout.addRow("Contact :", self.contact_input)
        layout.addRow("Téléphone :", self.phone_input)
        layout.addRow("Email :", self.email_input)
        layout.addRow("Adresse :", self.address_input)
        layout.addRow("Ville :", self.city_input)
        layout.addRow("NIF :", self.tax_id_input)
        layout.addRow("RC :", self.commercial_reg_input)

        if self.data:
            self.name_input.setText(self.data.get('Client_Name', ''))
            self.contact_input.setText(self.data.get('Contact_Person', ''))
            self.phone_input.setText(self.data.get('Phone', ''))
            self.email_input.setText(self.data.get('Email', ''))
            self.address_input.setText(self.data.get('Address', ''))
            self.city_input.setText(self.data.get('City', ''))
            self.tax_id_input.setText(self.data.get('Tax_ID_Number', ''))
            self.commercial_reg_input.setText(self.data.get('Commercial_Reg_No', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du client est obligatoire.")
            return None
            
        return {
            'name': name,
            'contact_person': self.contact_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'address': self.address_input.text().strip(),
            'city': self.city_input.text().strip(),
            'tax_id': self.tax_id_input.text().strip(),
            'commercial_reg': self.commercial_reg_input.text().strip()
        }


class OpenSessionDialog(QDialog):
    """Dialogue d'ouverture d'une session de caisse avec sélection de la caisse et fond initial."""

    def __init__(self, terminals, parent=None):
        super().__init__(parent)
        self.terminals = terminals
        self.setWindowTitle("💼 Ouverture de Session Caisse")
        self.setModal(True)
        self.resize(460, 270)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 12px; color: #2c3e50; }
            QComboBox, QDoubleSpinBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 0px;
                padding: 6px 10px;
                font-size: 13px;
                color: #2c3e50;
                min-height: 32px;
            }
            QComboBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1.5px solid #007572;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QLabel("🟢 <b>Démarrer une Nouvelle Session de Vente</b>")
        header.setStyleSheet("font-size: 14px; color: #007572;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)

        self.combo_terminal = QComboBox()
        for t in self.terminals:
            display_name = f"{t.get('Terminal_Name', 'Caisse')} ({t.get('Terminal_Code', '')})"
            self.combo_terminal.addItem(display_name, t.get('Terminal_ID'))
        form.addRow("<b>Sélectionner la Caisse * :</b>", self.combo_terminal)

        self.spin_opening = QDoubleSpinBox()
        self.spin_opening.setRange(0.0, 10000000.0)
        self.spin_opening.setDecimals(2)
        self.spin_opening.setValue(0.0)
        self.spin_opening.setSuffix(" DA")
        form.addRow("<b>Fond de Caisse Initial (DA) :</b>", self.spin_opening)

        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Observations d'ouverture (optionnel)...")
        form.addRow("Observations :", self.inp_notes)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("background: #ffffff; color: #495057; border: 1px solid #ced4da; border-radius: 0px; padding: 6px 16px; min-height: 32px;")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_open = QPushButton("🚀 Ouvrir la Caisse")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet("background: #007572; color: #ffffff; font-weight: bold; border-radius: 0px; padding: 6px 20px; min-height: 32px; border: none;")
        btn_open.clicked.connect(self.accept)
        btn_box.addWidget(btn_open)

        layout.addLayout(btn_box)

    def get_data(self):
        return {
            'terminal_id': self.combo_terminal.currentData(),
            'terminal_name': self.combo_terminal.currentText(),
            'opening_amount': self.spin_opening.value(),
            'notes': self.inp_notes.text().strip()
        }


class CloseSessionDialog(QDialog):
    """Dialogue de clôture de caisse avec comptage réel et calcul d'écart."""

    def __init__(self, session_data, summary_data, parent=None):
        super().__init__(parent)
        self.session = session_data
        self.summary = summary_data
        self.setWindowTitle(f"🔒 Clôture de Session - {self.session.get('Terminal_Name', 'Caisse')}")
        self.setModal(True)
        self.resize(500, 420)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 12px; color: #2c3e50; }
            QDoubleSpinBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 0px;
                padding: 6px 10px;
                font-size: 13px;
                color: #2c3e50;
                min-height: 32px;
            }
            QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1.5px solid #007572;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QLabel(f"🔒 <b>Clôture de Caisse : {self.session.get('Terminal_Name', '')} ({self.session.get('Session_No', '')})</b>")
        header.setStyleSheet("font-size: 13px; color: #c0392b;")
        layout.addWidget(header)

        card = QFrame()
        card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0px; padding: 10px;")
        card_layout = QGridLayout(card)
        card_layout.setSpacing(6)

        opening_amt = float(self.session.get('Opening_Amount') or 0.0)
        cash_sales = float(self.summary.get('Expected_Cash') or 0.0)
        self.theoretical_cash = opening_amt + cash_sales

        card_layout.addWidget(QLabel("<b>Fond Initial :</b>"), 0, 0)
        card_layout.addWidget(QLabel(f"{format_money(opening_amt)} DA"), 0, 1)

        card_layout.addWidget(QLabel("<b>Total Ventes Espèces :</b>"), 1, 0)
        card_layout.addWidget(QLabel(f"{format_money(cash_sales)} DA"), 1, 1)

        card_layout.addWidget(QLabel("<b>Nombre de Tickets :</b>"), 2, 0)
        card_layout.addWidget(QLabel(str(self.summary.get('Invoice_Count') or 0)), 2, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        card_layout.addWidget(sep, 3, 0, 1, 2)

        lbl_theo_title = QLabel("<b>Montant Théorique en Caisse :</b>")
        lbl_theo_title.setStyleSheet("font-size: 13px; color: #007572;")
        lbl_theo_val = QLabel(f"<b>{format_money(self.theoretical_cash)} DA</b>")
        lbl_theo_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #007572;")
        card_layout.addWidget(lbl_theo_title, 4, 0)
        card_layout.addWidget(lbl_theo_val, 4, 1)

        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(8)

        self.spin_counted = QDoubleSpinBox()
        self.spin_counted.setRange(0.0, 10000000.0)
        self.spin_counted.setDecimals(2)
        self.spin_counted.setValue(self.theoretical_cash)
        self.spin_counted.setSuffix(" DA")
        self.spin_counted.valueChanged.connect(self._recalculate_diff)
        form.addRow("<b>Montant Réel Compté (DA) * :</b>", self.spin_counted)

        self.lbl_diff = QLabel()
        self.lbl_diff.setStyleSheet("font-size: 13px; font-weight: bold;")
        form.addRow("<b>Écart de Caisse :</b>", self.lbl_diff)

        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Justification d'écart ou remarques...")
        form.addRow("Observations :", self.inp_notes)

        layout.addLayout(form)
        self._recalculate_diff()

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("background: #ffffff; color: #495057; border: 1px solid #ced4da; border-radius: 0px; padding: 6px 16px; min-height: 32px;")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_close = QPushButton("🔒 Confirmer Clôture")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background: #c0392b; color: #ffffff; font-weight: bold; border-radius: 0px; padding: 6px 20px; min-height: 32px; border: none;")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _recalculate_diff(self):
        counted = self.spin_counted.value()
        diff = counted - self.theoretical_cash
        sign = "+" if diff > 0 else ""
        color = "#27ae60" if abs(diff) < 0.01 else ("#2980b9" if diff > 0 else "#c0392b")
        status = "Équilibrée" if abs(diff) < 0.01 else ("Excédent" if diff > 0 else "Déficit")
        self.lbl_diff.setText(f"{sign}{format_money(diff)} DA ({status})")
        self.lbl_diff.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

    def get_data(self):
        counted = self.spin_counted.value()
        return {
            'counted_cash': counted,
            'cash_difference': counted - self.theoretical_cash,
            'notes': self.inp_notes.text().strip()
        }


class CashSessionDetailsDialog(QDialog):
    """Fiche détaillée d'une session de caisse : Caisse, Ouverture, Clôture, Écarts et Ventes associées."""

    def __init__(self, data_manager, session_id: int, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.session_id = session_id
        self.session_data = self.data_manager.cash_sessions.get_session_details_full(session_id) or {}
        
        caisse_name = self.session_data.get('Terminal_Name') or self.session_data.get('Terminal_Code') or "Caisse"
        session_no = self.session_data.get('Session_No') or f"#{session_id}"
        
        self.setWindowTitle(f"📋 Détails de la Session : {session_no} - {caisse_name}")
        self.resize(850, 620)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 13px; color: #2c3e50; }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- En-tête Caisse & Session ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 4, 8, 4)

        caisse_name = self.session_data.get('Terminal_Name') or "Caisse"
        caisse_code = self.session_data.get('Terminal_Code') or "-"
        session_no = self.session_data.get('Session_No') or f"#{self.session_id}"
        status = self.session_data.get('Status', 'Open')
        is_open = (status == 'Open')

        lbl_caisse = QLabel(f"🏦 <b>{caisse_name}</b> <span style='color: #64748b;'>({caisse_code})</span><br>"
                            f"<span style='font-size: 15px; font-weight: bold; color: #007572;'>Session N° {session_no}</span>")
        h_layout.addWidget(lbl_caisse)
        h_layout.addStretch()

        status_text = "🟢 SESSION OUVERTE (En cours)" if is_open else "🔒 SESSION CLÔTURÉE"
        status_bg = "#e8f8f5" if is_open else "#fdf2f1"
        status_color = "#007572" if is_open else "#c0392b"
        status_border = "#a3e4d7" if is_open else "#fecaca"

        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"background: {status_bg}; color: {status_color}; border: 1px solid {status_border};"
                                 f"font-weight: bold; font-size: 12px; padding: 6px 14px; border-radius: 4px;")
        h_layout.addWidget(lbl_status)

        layout.addWidget(header_frame)

        # --- Cartes Comparatives : Ouverture vs Clôture ---
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # 1. Carte Ouverture
        card_open = QFrame()
        card_open.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")
        l_open = QVBoxLayout(card_open)
        l_open.setSpacing(6)

        title_open = QLabel("🟢 <b>Détails de l'Ouverture</b>")
        title_open.setStyleSheet("color: #007572; font-size: 14px; border-bottom: 2px solid #007572; padding-bottom: 4px;")
        l_open.addWidget(title_open)

        opened_by = self.session_data.get('Opened_By_Name') or "-"
        opened_at = str(self.session_data.get('Opened_At', '---'))[:19]
        opening_amt = float(self.session_data.get('Opening_Amount') or 0.0)

        l_open.addWidget(QLabel(f"<b>Ouvert par :</b> {opened_by}"))
        l_open.addWidget(QLabel(f"<b>Date & Heure :</b> {opened_at}"))
        
        lbl_open_money = QLabel(f"<b>Fond Initial Présent :</b><br>"
                                f"<span style='font-size: 18px; font-weight: bold; color: #27ae60;'>{format_money(opening_amt)} DA</span>")
        l_open.addWidget(lbl_open_money)
        l_open.addStretch()
        cards_layout.addWidget(card_open, stretch=1)

        # 2. Carte Clôture / Sortie
        card_close = QFrame()
        card_close.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")
        l_close = QVBoxLayout(card_close)
        l_close.setSpacing(6)

        title_close = QLabel("🔒 <b>Détails de la Sortie / Clôture</b>")
        title_close.setStyleSheet("color: #c0392b; font-size: 14px; border-bottom: 2px solid #c0392b; padding-bottom: 4px;")
        l_close.addWidget(title_close)

        if not is_open:
            closed_by = self.session_data.get('Closed_By_Name') or "-"
            closed_at = str(self.session_data.get('Closed_At', '---'))[:19]
            counted_cash = float(self.session_data.get('Counted_Cash') or 0.0)
            diff = float(self.session_data.get('Cash_Difference') or 0.0)
            diff_color = "#27ae60" if abs(diff) < 0.01 else ("#2980b9" if diff > 0 else "#c0392b")
            diff_status = "Équilibrée" if abs(diff) < 0.01 else ("Excédent (+)" if diff > 0 else "Déficit (-)")
            diff_sign = "+" if diff > 0 else ""

            l_close.addWidget(QLabel(f"<b>Clôturé par :</b> {closed_by}"))
            l_close.addWidget(QLabel(f"<b>Date & Heure :</b> {closed_at}"))
            l_close.addWidget(QLabel(f"<b>Montant Réel à la Sortie :</b><br>"
                                     f"<span style='font-size: 18px; font-weight: bold; color: #2c3e50;'>{format_money(counted_cash)} DA</span>"))
            
            lbl_diff = QLabel(f"<b>Écart de caisse constaté :</b> "
                              f"<span style='color: {diff_color}; font-weight: bold;'>{diff_sign}{format_money(diff)} DA ({diff_status})</span>")
            l_close.addWidget(lbl_diff)
        else:
            summary = self.session_data.get('summary', {})
            exp_cash = float(summary.get('Expected_Cash') or 0.0)
            theo_total = opening_amt + exp_cash
            l_close.addWidget(QLabel("<i>La session est actuellement active.</i>"))
            l_close.addWidget(QLabel(f"<b>Montant Espèces théorique actuel :</b><br>"
                                     f"<span style='font-size: 16px; font-weight: bold; color: #007572;'>{format_money(theo_total)} DA</span>"))
            l_close.addWidget(QLabel("<span style='font-size: 12px; color: #64748b;'>(Fond initial + Encaissements espèces)</span>"))

        l_close.addStretch()
        cards_layout.addWidget(card_close, stretch=1)

        layout.addLayout(cards_layout)

        # --- Récapitulatif par mode de paiement et tableau des transactions ---
        lbl_table_title = QLabel("🧾 <b>Transactions et Ventes Réalisées Durant la Session :</b>")
        lbl_table_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b; margin-top: 4px;")
        layout.addWidget(lbl_table_title)

        table_invoices = QTableWidget()
        cols = ["N° Facture", "Date", "Client", "Statut", "Mode Règlement", "Total TTC"]
        table_invoices.setColumnCount(len(cols))
        table_invoices.setHorizontalHeaderLabels(cols)
        table_invoices.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_invoices.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table_invoices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table_invoices.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table_invoices.setAlternatingRowColors(True)
        table_invoices.setSelectionBehavior(QAbstractItemView.SelectRows)
        table_invoices.setEditTriggers(QAbstractItemView.NoEditTriggers)

        invoices = self.session_data.get('invoices', [])
        table_invoices.setRowCount(len(invoices))
        total_session_sales = 0.0

        for r, inv in enumerate(invoices):
            ref = str(inv.get('Invoice_No') or f"#{inv.get('Invoice_ID')}")
            dt = str(inv.get('Invoice_Date') or '---')
            cl = str(inv.get('Client_Name') or 'Vente comptoir')
            st = str(inv.get('Status') or '-')
            pm = str(inv.get('Payment_Method') or '-')
            amt = float(inv.get('Total_Amount_TTC') or 0.0)

            if st != 'Cancelled':
                total_session_sales += amt

            table_invoices.setItem(r, 0, QTableWidgetItem(ref))
            table_invoices.setItem(r, 1, QTableWidgetItem(dt))
            table_invoices.setItem(r, 2, QTableWidgetItem(cl))
            
            st_item = QTableWidgetItem(st)
            if st == 'Cancelled':
                st_item.setForeground(QBrush(QColor("#c0392b")))
            table_invoices.setItem(r, 3, st_item)

            table_invoices.setItem(r, 4, QTableWidgetItem(pm))
            
            amt_item = QTableWidgetItem(f"{format_money(amt)} DA")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            table_invoices.setItem(r, 5, amt_item)

        layout.addWidget(table_invoices)

        # --- Total Ventes et Remarques ---
        bottom_row = QHBoxLayout()
        notes = self.session_data.get('Notes')
        notes_text = f"<b>Remarques :</b> {notes}" if notes else "<i>Aucune remarque particulière.</i>"
        lbl_notes = QLabel(notes_text)
        lbl_notes.setStyleSheet("color: #64748b; font-size: 12px;")
        bottom_row.addWidget(lbl_notes)
        bottom_row.addStretch()

        lbl_total_sales = QLabel(f"<b>Total Ventes Session ({len(invoices)} tickets) : </b>"
                                 f"<span style='font-size: 15px; font-weight: bold; color: #007572;'>{format_money(total_session_sales)} DA</span>")
        bottom_row.addWidget(lbl_total_sales)
        layout.addLayout(bottom_row)

        # Bouton Fermer
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close_dlg = QPushButton("Fermer")
        btn_close_dlg.setCursor(Qt.PointingHandCursor)
        btn_close_dlg.setStyleSheet("""
            QPushButton {
                background: #007572; color: white; font-weight: bold;
                border-radius: 4px; padding: 6px 24px; min-height: 32px; border: none;
            }
            QPushButton:hover { background: #005a57; }
        """)
        btn_close_dlg.clicked.connect(self.accept)
        btn_box.addWidget(btn_close_dlg)
        layout.addLayout(btn_box)



class QuickCashPaymentDialog(QDialog):
    """Dialogue de règlement direct en Dinars uniquement (Espèces) avec rendu de monnaie."""

    def __init__(self, total_ttc: float, parent=None):
        super().__init__(parent)
        self.total_ttc = float(total_ttc)
        self.setWindowTitle("💵 Règlement en Dinars (Espèces)")
        self.setModal(True)
        self.resize(440, 370)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #2c3e50; }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        card_total = QFrame()
        card_total.setStyleSheet("background: #007572; border-radius: 0px; padding: 12px;")
        card_layout = QVBoxLayout(card_total)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(4)

        lbl_caption = QLabel("TOTAL À PAYER")
        lbl_caption.setAlignment(Qt.AlignCenter)
        lbl_caption.setStyleSheet("color: #e6f4f1; font-size: 12px; font-weight: 600; letter-spacing: 1px;")

        self.lbl_net = QLabel(f"{format_money(self.total_ttc)} DA")
        self.lbl_net.setAlignment(Qt.AlignCenter)
        self.lbl_net.setStyleSheet("color: #ffffff; font-size: 26px; font-weight: 800;")

        card_layout.addWidget(lbl_caption)
        card_layout.addWidget(self.lbl_net)
        layout.addWidget(card_total)

        lbl_rec = QLabel("<b>Montant Reçu du Client (DA) :</b>")
        lbl_rec.setStyleSheet("font-size: 13px;")
        layout.addWidget(lbl_rec)

        self.spin_received = QDoubleSpinBox()
        self.spin_received.setRange(0.0, 10000000.0)
        self.spin_received.setDecimals(2)
        self.spin_received.setValue(self.total_ttc)
        self.spin_received.setSuffix(" DA")
        self.spin_received.setStyleSheet("""
            QDoubleSpinBox {
                background: #ffffff;
                border: 2px solid #007572;
                border-radius: 0px;
                padding: 6px 12px;
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                min-height: 38px;
            }
        """)
        self.spin_received.valueChanged.connect(self._recalculate_change)
        layout.addWidget(self.spin_received)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)

        def _add_quick_btn(label, add_amount, is_exact=False):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("background: #f1f5f9; color: #2c3e50; font-weight: bold; font-size: 11px; border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 6px; min-height: 28px;")
            if is_exact:
                b.clicked.connect(lambda: self.spin_received.setValue(self.total_ttc))
            else:
                b.clicked.connect(lambda: self.spin_received.setValue(self.spin_received.value() + add_amount))
            quick_layout.addWidget(b)

        _add_quick_btn("Exact", 0, is_exact=True)
        _add_quick_btn("+500 DA", 500)
        _add_quick_btn("+1 000 DA", 1000)
        _add_quick_btn("+2 000 DA", 2000)
        layout.addLayout(quick_layout)

        self.lbl_change = QLabel("Monnaie à rendre : 0,00 DA")
        self.lbl_change.setAlignment(Qt.AlignCenter)
        self.lbl_change.setStyleSheet("font-size: 15px; font-weight: bold; color: #27ae60; padding: 6px 0;")
        layout.addWidget(self.lbl_change)

        self.chk_print = QCheckBox("🖨️ Imprimer le ticket de caisse")
        self.chk_print.setChecked(True)
        self.chk_print.setStyleSheet("font-size: 12px; color: #2c3e50; font-weight: 500;")
        layout.addWidget(self.chk_print)

        self._recalculate_change()

        self.btn_confirm = QPushButton("✔️ Valider la Vente (Entrée)")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background: #007572;
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                border-radius: 0px;
                min-height: 44px;
                border: none;
            }
            QPushButton:hover { background: #005a57; }
        """)
        self.btn_confirm.clicked.connect(self._on_confirm)
        layout.addWidget(self.btn_confirm)

    def _recalculate_change(self):
        rec = self.spin_received.value()
        change = rec - self.total_ttc
        if change >= 0:
            self.lbl_change.setText(f"Monnaie à rendre : {format_money(change)} DA")
            self.lbl_change.setStyleSheet("font-size: 15px; font-weight: bold; color: #27ae60; padding: 4px 0;")
        else:
            self.lbl_change.setText(f"Reste dû : {format_money(abs(change))} DA")
            self.lbl_change.setStyleSheet("font-size: 15px; font-weight: bold; color: #c0392b; padding: 4px 0;")

    def _on_confirm(self):
        if self.spin_received.value() < self.total_ttc - 0.001:
            res = QMessageBox.question(
                self, "Montant insuffisant",
                "Le montant reçu est inférieur au montant total de la vente.\nVoulez-vous quand même valider en vente avec reste à payer ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if res != QMessageBox.Yes:
                return
        self.accept()

    def get_data(self):
        return {
            'received': self.spin_received.value(),
            'change': max(0.0, self.spin_received.value() - self.total_ttc),
            'print_receipt': self.chk_print.isChecked()
        }


class SelectBatchBarcodeDialog(QDialog):
    """Dialogue tactile permettant de choisir l'emplacement (lieu de retrait) et le lot pour un produit."""
    def __init__(self, batches, parent=None):
        super().__init__(parent)
        self.batches = batches or []
        self.selected_batch = None
        self.setWindowTitle("📍 Choix de l'Emplacement (Lieu de Retrait) / Lot")
        self.setMinimumSize(680, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
            }
            QLabel {
                color: #1e293b;
            }
            QLineEdit, QComboBox {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #007572;
                background-color: #ffffff;
            }
            QPushButton {
                border-radius: 0px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        p_name = self.batches[0].get('Product_Name', 'Produit') if self.batches else 'Produit'
        header = QLabel(f"<b>{p_name}</b>")
        header.setStyleSheet("font-size: 16px; color: #007572; font-weight: bold;")
        layout.addWidget(header)

        sub = QLabel("Ce produit est disponible dans <b>plusieurs emplacements ou lots</b>.<br>Choisissez le <b>lieu de retrait</b> souhaité ou scannez le code-barres :")
        sub.setStyleSheet("font-size: 12px; color: #475569; line-height: 140%;")
        layout.addWidget(sub)

        # Barre de filtres (Recherche code/lot + Filtre par Emplacement)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔎 Scannez un code-barres ou recherchez un lot...")
        self.search_input.textChanged.connect(self._apply_local_filter)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        filter_layout.addWidget(self.search_input, stretch=3)

        self.combo_loc = QComboBox()
        self.combo_loc.addItem("📍 Tous les Lieux", None)
        # Extraire les emplacements uniques disponibles
        seen_locs = set()
        for b in self.batches:
            l_id = b.get('Location_ID')
            l_name = b.get('Location_Name') or "Emplacement non spécifié"
            if l_id and l_id not in seen_locs:
                seen_locs.add(l_id)
                self.combo_loc.addItem(f"📍 {l_name}", l_id)
        self.combo_loc.currentIndexChanged.connect(self._apply_local_filter)
        filter_layout.addWidget(self.combo_loc, stretch=2)

        layout.addLayout(filter_layout)

        from PySide6.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Emplacement (Lieu de Retrait)", "Stock Dispo", "Code-Barres", "N° Lot", "Date Exp.", "Prix TTC"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item:selected {
                background-color: #007572;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                padding: 6px;
            }
        """)
        self.table.doubleClicked.connect(self._on_select)
        layout.addWidget(self.table)

        self._populate_table(self.batches)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setStyleSheet("background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_select = QPushButton("Valider le Retrait depuis cet Emplacement")
        self.btn_select.setStyleSheet("background-color: #007572; color: #ffffff; border: 1px solid #005a57; font-weight: bold;")
        self.btn_select.clicked.connect(self._on_select)
        btn_layout.addWidget(self.btn_select)

        layout.addLayout(btn_layout)

    def _get_batch_codes(self, b):
        codes = []
        for key in ('Internal_Barcode', 'External_Barcode', 'Barcode'):
            val = str(b.get(key) or '').strip()
            if val and val.lower() not in ('none', 'null', '---'):
                import re
                for p in re.split(r'[,;/|\r\n]+', val):
                    pc = p.strip()
                    if pc and pc not in codes:
                        codes.append(pc)
        return codes

    def _populate_table(self, batches):
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor, QFont
        self.table.setRowCount(len(batches))
        for r, b in enumerate(batches):
            loc_str = f"📍 {b.get('Location_Name') or 'Lieu non spécifié'}"
            codes = self._get_batch_codes(b)
            code_str = " / ".join(codes) if codes else "---"
            lot_str = str(b.get('Lot_Number') or '---')
            stock_str = str(b.get('Quantity_Current') or 0)
            exp_str = str(b.get('Expiry_Date') or '---')[:10]
            price_ht = float(b.get('Selling_Price_HT') or 0)
            tva = float(b.get('Selling_TVA_Percent') or b.get('Tax_Rate_Percent') or 0)
            price_ttc = price_ht * (1 + tva / 100.0)
            price_str = f"{format_money(price_ttc)} DA"

            # 0. Emplacement
            loc_item = QTableWidgetItem(loc_str)
            loc_item.setData(Qt.UserRole, b)
            loc_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            loc_item.setFont(QFont("", -1, QFont.Bold))
            loc_item.setForeground(QColor("#007572"))

            # 1. Stock Dispo
            s_item = QTableWidgetItem(stock_str)
            s_item.setTextAlignment(Qt.AlignCenter)
            s_item.setFont(QFont("", -1, QFont.Bold))

            # 2. Code-Barres
            c_item = QTableWidgetItem(code_str)
            c_item.setTextAlignment(Qt.AlignCenter)
            c_item.setForeground(QColor("#0f5f8f"))

            # 3. N° Lot
            l_item = QTableWidgetItem(lot_str)
            l_item.setTextAlignment(Qt.AlignCenter)

            # 4. Date Exp.
            e_item = QTableWidgetItem(exp_str)
            e_item.setTextAlignment(Qt.AlignCenter)

            # 5. Prix TTC
            p_item = QTableWidgetItem(price_str)
            p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            p_item.setFont(QFont("", -1, QFont.Bold))

            self.table.setItem(r, 0, loc_item)
            self.table.setItem(r, 1, s_item)
            self.table.setItem(r, 2, c_item)
            self.table.setItem(r, 3, l_item)
            self.table.setItem(r, 4, e_item)
            self.table.setItem(r, 5, p_item)

        if len(batches) > 0:
            self.table.selectRow(0)

    def _apply_local_filter(self):
        clean = self.search_input.text().strip().lower()
        loc_id = self.combo_loc.currentData()

        filtered = []
        for b in self.batches:
            if loc_id is not None and b.get('Location_ID') != loc_id:
                continue
            if clean:
                codes = [c.lower() for c in self._get_batch_codes(b)]
                lot = str(b.get('Lot_Number') or '').lower()
                loc = str(b.get('Location_Name') or '').lower()
                if not (any(clean in c for c in codes) or clean in lot or clean in loc):
                    continue
            filtered.append(b)
        self._populate_table(filtered)

    def _on_return_pressed(self):
        clean = self.search_input.text().strip().lower()
        for b in self.batches:
            codes = [c.lower() for c in self._get_batch_codes(b)]
            if clean in codes:
                self.selected_batch = b
                self.accept()
                return
        self._on_select()

    def _on_select(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.selected_batch = item.data(Qt.UserRole)
                self.accept()
                return
        QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un lot.")

    def get_selected_batch(self):
        return self.selected_batch


class EnterProductBarcodeDialog(QDialog):
    """Dialogue permettant de saisir ou d'associer un code-barres directement depuis la caisse."""
    def __init__(self, data_manager, batch, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.batch = batch or {}
        self.setWindowTitle("🏷️ Saisie / Association de Code-Barres")
        self.setMinimumSize(500, 340)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
            }
            QLabel {
                color: #1e293b;
            }
            QLineEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #007572;
                background-color: #ffffff;
            }
            QPushButton {
                border-radius: 0px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QRadioButton {
                color: #334155;
                font-size: 12px;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        p_name = self.batch.get('Product_Name', 'Produit')
        header = QLabel(f"<b>{p_name}</b>")
        header.setStyleSheet("font-size: 15px; color: #007572; font-weight: bold;")
        layout.addWidget(header)

        # Informations actuelles
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0px; padding: 6px;")
        info_layout = QGridLayout(info_frame)
        info_layout.setSpacing(4)

        info_layout.addWidget(QLabel("<b>N° Lot :</b>"), 0, 0)
        info_layout.addWidget(QLabel(str(self.batch.get('Lot_Number') or '---')), 0, 1)

        info_layout.addWidget(QLabel("<b>Code Interne :</b>"), 1, 0)
        info_layout.addWidget(QLabel(str(self.batch.get('Internal_Barcode') or '---')), 1, 1)

        info_layout.addWidget(QLabel("<b>Code Externe :</b>"), 2, 0)
        self.lbl_ext_barcode = QLabel(str(self.batch.get('External_Barcode') or '---'))
        info_layout.addWidget(self.lbl_ext_barcode, 2, 1)

        info_layout.addWidget(QLabel("<b>Codes Multiples :</b>"), 3, 0)
        self.lbl_prod_barcode = QLabel(str(self.batch.get('Barcode') or '---'))
        info_layout.addWidget(self.lbl_prod_barcode, 3, 1)

        layout.addWidget(info_frame)

        layout.addWidget(QLabel("<b>Nouveau code-barres à saisir ou scanner :</b>"))
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Ex: 6131234567890 (douchette ou clavier)")
        self.barcode_input.returnPressed.connect(self._on_save)
        layout.addWidget(self.barcode_input)

        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self.bg = QButtonGroup(self)
        self.rb_product = QRadioButton("Ajouter aux codes-barres multiples du produit (recommandé)")
        self.rb_product.setChecked(True)
        self.rb_batch = QRadioButton("Définir comme code-barres externe de ce lot spécifique")
        self.bg.addButton(self.rb_product)
        self.bg.addButton(self.rb_batch)

        layout.addWidget(self.rb_product)
        layout.addWidget(self.rb_batch)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setStyleSheet("background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Enregistrer le Code-Barres")
        self.btn_save.setStyleSheet("background-color: #007572; color: #ffffff; border: 1px solid #005a57;")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _on_save(self):
        new_code = self.barcode_input.text().strip()
        if not new_code:
            QMessageBox.warning(self, "Champ vide", "Veuillez scanner ou saisir un code-barres.")
            return

        p_id = self.batch.get('Product_ID')
        b_id = self.batch.get('Batch_ID')

        try:
            if self.rb_product.isChecked():
                success, msg = self.data_manager.products.add_product_barcode(p_id, new_code)
                if success:
                    self.batch['Barcode'] = msg
                    QMessageBox.information(self, "Succès", f"Code-barres '{new_code}' associé avec succès au produit !")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Erreur", f"Échec de l'association : {msg}")
            else:
                success, msg = self.data_manager.batches.update_batch_external_barcode(b_id, new_code)
                if success:
                    self.batch['External_Barcode'] = new_code
                    QMessageBox.information(self, "Succès", f"Code-barres externe '{new_code}' associé avec succès à ce lot !")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Erreur", f"Échec de la mise à jour : {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Une exception s'est produite : {e}")

    def get_entered_barcode(self):
        return self.barcode_input.text().strip()


