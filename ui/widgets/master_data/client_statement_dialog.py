# ui/widgets/master_data/client_statement_dialog.py

import os
import json
import logging
from datetime import datetime, date, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QComboBox, QFrame, QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from ui.formatting import format_money
from branding import get_logo_path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class ClientStatementDialog(QDialog):
    """
    Dialogue de Relevé de Compte Client (Customer Account Statement).
    Affiche l'historique financier complet (Factures, Règlements, Avoirs),
    calcule le solde initial, les mouvements et le solde progressif,
    et permet l'exportation PDF A4 formaté.
    """

    def __init__(self, data_manager, client_id: int, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_id = client_id
        self.client_manager = data_manager.clients
        self.ledger_data = {}

        self.setWindowTitle("📄 Relevé de Compte Client - Grand Livre Auxiliaire")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.resize(1200, 780)
        self.setMinimumSize(950, 600)

        self.init_ui()
        self.apply_preset("this_month")

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Header Card (Nom du client & Coordonnées & Risque Crédit)
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 10px 14px;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(6, 4, 6, 4)

        self.lbl_client_title = QLabel("Chargement du client...")
        self.lbl_client_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #007572;")
        header_layout.addWidget(self.lbl_client_title, 1)

        self.lbl_client_meta = QLabel("")
        self.lbl_client_meta.setStyleSheet("font-size: 12px; color: #475569; font-weight: 500;")
        header_layout.addWidget(self.lbl_client_meta)

        layout.addWidget(self.header_frame)

        # 2. Controls Toolbar (Dedicated Top Utility Bar)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        lbl_p = QLabel("Période :")
        lbl_p.setStyleSheet("font-weight: bold; font-size: 12px; color: #334155;")
        filter_layout.addWidget(lbl_p)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Ce mois",
            "Mois précédent",
            "Dernier trimestre",
            "30 derniers jours",
            "Cette année",
            "Tout l'historique",
            "Personnalisé"
        ])
        self.preset_combo.setMinimumHeight(34)
        self.preset_combo.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 8px; font-size: 12px;")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        filter_layout.addWidget(self.preset_combo)

        lbl_du = QLabel("Du :")
        lbl_du.setStyleSheet("font-weight: bold; font-size: 12px; color: #334155;")
        filter_layout.addWidget(lbl_du)

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-1))
        self.date_start.setMinimumHeight(34)
        self.date_start.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 6px; font-size: 12px;")
        self.date_start.dateChanged.connect(self._on_date_changed)
        filter_layout.addWidget(self.date_start)

        lbl_au = QLabel("Au :")
        lbl_au.setStyleSheet("font-weight: bold; font-size: 12px; color: #334155;")
        filter_layout.addWidget(lbl_au)

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setMinimumHeight(34)
        self.date_end.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 6px; font-size: 12px;")
        self.date_end.dateChanged.connect(self._on_date_changed)
        filter_layout.addWidget(self.date_end)

        self.btn_refresh = QPushButton("🔄 Actualiser")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_refresh.clicked.connect(self.load_ledger)
        filter_layout.addWidget(self.btn_refresh)

        filter_layout.addStretch(1)

        self.btn_print = QPushButton("🖨️ Imprimer")
        self.btn_print.setCursor(Qt.PointingHandCursor)
        self.btn_print.setMinimumHeight(34)
        self.btn_print.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #007572;
                border: 1.5px solid #007572;
                border-radius: 0px;
                padding: 4px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e6f4f1; }
        """)
        self.btn_print.clicked.connect(self.print_statement)
        filter_layout.addWidget(self.btn_print)

        self.btn_export_pdf = QPushButton("📑 Exporter en PDF (A4)")
        self.btn_export_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_export_pdf.setMinimumHeight(34)
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: white;
                font-weight: bold;
                padding: 4px 16px;
                border: none;
                border-radius: 0px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        filter_layout.addWidget(self.btn_export_pdf)

        self.btn_top_close = QPushButton("✕ Fermer")
        self.btn_top_close.setCursor(Qt.PointingHandCursor)
        self.btn_top_close.setMinimumHeight(34)
        self.btn_top_close.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #dc2626;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                padding: 4px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        self.btn_top_close.clicked.connect(self.accept)
        filter_layout.addWidget(self.btn_top_close)

        layout.addLayout(filter_layout)

        # 3. KPI Summary Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.card_initial = self._create_kpi_card("Solde Initial", "0.00 DA", "#64748b")
        self.card_debit = self._create_kpi_card("Total Débit (Factures & BL)", "0.00 DA", "#0284c7")
        self.card_credit = self._create_kpi_card("Total Crédit (Règlements & Avoirs)", "0.00 DA", "#16a34a")
        self.card_final = self._create_kpi_card("Nouveau Solde Dû", "0.00 DA", "#dc2626")

        kpi_layout.addWidget(self.card_initial)
        kpi_layout.addWidget(self.card_debit)
        kpi_layout.addWidget(self.card_credit)
        kpi_layout.addWidget(self.card_final)
        layout.addLayout(kpi_layout)

        # 4. Table du Grand Livre (Transactions Ledger)
        self.table = QTableWidget()
        cols = ["Date", "Type de Document", "Référence", "Débit (+)", "Crédit (-)", "Solde Progressif", "Notes"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                gridline-color: #f1f5f9;
                font-size: 12px;
                color: #1e293b;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #1e293b;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #007572;
                border-right: 1px solid #e2e8f0;
                padding: 6px 8px;
            }
            QTableWidget::item:selected {
                background-color: #e6f4f1;
                color: #004d40;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.table, 1)

        # 5. Bottom Status and Close
        bottom_layout = QHBoxLayout()
        lbl_legend = QLabel("💡 * Note : Les Devis et Bons de Commande brouillon sont répertoriés [Hors bilan] avec Débit 0,00 DA sans affecter le solde exigible.")
        lbl_legend.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic;")
        bottom_layout.addWidget(lbl_legend)
        bottom_layout.addStretch(1)

        self.btn_close = QPushButton("Fermer (Echap)")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedWidth(120)
        self.btn_close.setMinimumHeight(34)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)
        layout.addLayout(bottom_layout)

    def _create_kpi_card(self, title, default_val, text_color):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        lbl_v = QLabel(default_val)
        lbl_v.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {text_color};")
        lbl_v.setObjectName("val")

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return frame

    def _update_card_val(self, frame, text):
        val_lbl = frame.findChild(QLabel, "val")
        if val_lbl:
            val_lbl.setText(text)

    def _on_date_changed(self):
        idx = self.preset_combo.findText("Personnalisé")
        if idx >= 0 and self.preset_combo.currentIndex() != idx:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(idx)
            self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, index):
        presets = ["this_month", "last_month", "last_quarter", "last_30_days", "this_year", "all", "custom"]
        if 0 <= index < len(presets):
            self.apply_preset(presets[index])

    def apply_preset(self, preset_key):
        if preset_key == "custom":
            self.load_ledger()
            return

        today = date.today()
        if preset_key == "this_month":
            start = date(today.year, today.month, 1)
            end = today
        elif preset_key == "last_month":
            first_this_month = date(today.year, today.month, 1)
            last_day_prev = first_this_month - timedelta(days=1)
            start = date(last_day_prev.year, last_day_prev.month, 1)
            end = last_day_prev
        elif preset_key == "last_quarter":
            curr_quarter = (today.month - 1) // 3 + 1
            if curr_quarter == 1:
                prev_quarter = 4
                year = today.year - 1
            else:
                prev_quarter = curr_quarter - 1
                year = today.year
            start_month = (prev_quarter - 1) * 3 + 1
            start = date(year, start_month, 1)
            end_month = start_month + 2
            if end_month in (1, 3, 5, 7, 8, 10, 12):
                end_day = 31
            elif end_month == 2:
                end_day = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            else:
                end_day = 30
            end = date(year, end_month, end_day)
        elif preset_key == "last_30_days":
            start = today - timedelta(days=30)
            end = today
        elif preset_key == "this_year":
            start = date(today.year, 1, 1)
            end = today
        elif preset_key == "all":
            start = date(2020, 1, 1)
            end = today
        else:
            start = date(today.year, today.month, 1)
            end = today

        self.date_start.blockSignals(True)
        self.date_end.blockSignals(True)
        self.date_start.setDate(QDate(start.year, start.month, start.day))
        self.date_end.setDate(QDate(end.year, end.month, end.day))
        self.date_start.blockSignals(False)
        self.date_end.blockSignals(False)
        self.load_ledger()

    def load_ledger(self):
        start_str = self.date_start.date().toString("yyyy-MM-dd")
        end_str = self.date_end.date().toString("yyyy-MM-dd")

        self.ledger_data = self.client_manager.get_client_ledger(
            self.client_id, start_date=start_str, end_date=end_str
        )

        client = self.ledger_data.get('client', {})
        name = client.get('Client_Name') or "Client inconnu"
        contact = client.get('Phone') or client.get('Contact_Person') or ""
        city = client.get('City') or ""
        tier = client.get('Price_Tier') or "Prix_1"
        limit = float(client.get('Credit_Limit') or 0.0)

        self.lbl_client_title.setText(f"👤 {name}")
        self.lbl_client_meta.setText(
            f"Tél: {contact} | Ville: {city} | Catégorie: {tier} | Plafond Crédit: {format_money(limit)} DA"
        )

        initial = float(self.ledger_data.get('initial_balance', 0.0))
        final = float(self.ledger_data.get('final_balance', 0.0))
        txs = self.ledger_data.get('transactions', [])

        total_debit = sum(t.get('debit', 0.0) for t in txs)
        total_credit = sum(t.get('credit', 0.0) for t in txs)

        self._update_card_val(self.card_initial, f"{format_money(initial)} DA")
        self._update_card_val(self.card_debit, f"{format_money(total_debit)} DA")
        self._update_card_val(self.card_credit, f"{format_money(total_credit)} DA")
        self._update_card_val(self.card_final, f"{format_money(final)} DA")

        # Color final balance
        val_lbl = self.card_final.findChild(QLabel, "val")
        if val_lbl:
            if final <= 0:
                val_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #16a34a;")
            elif limit > 0 and final > limit:
                val_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #dc2626;")
            else:
                val_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #d97706;")

        # Populate table
        self.table.setRowCount(0)
        for row_idx, t in enumerate(txs):
            self.table.insertRow(row_idx)

            date_item = QTableWidgetItem(t['date'])
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, date_item)

            type_label = t['type']
            is_non_binding = t.get('is_non_binding', False)
            if is_non_binding and "[Hors bilan]" not in type_label:
                type_label += " [Hors bilan]"

            type_item = QTableWidgetItem(type_label)
            type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if is_non_binding:
                type_item.setForeground(QColor("#64748b"))
                font = type_item.font()
                font.setItalic(True)
                type_item.setFont(font)
            self.table.setItem(row_idx, 1, type_item)

            ref_item = QTableWidgetItem(t['reference'])
            ref_item.setTextAlignment(Qt.AlignCenter)
            if is_non_binding:
                ref_item.setForeground(QColor("#64748b"))
            self.table.setItem(row_idx, 2, ref_item)

            # Débit (+)
            debit_val = t['debit']
            if is_non_binding:
                raw_amt = t.get('raw_amount', 0.0)
                debit_item = QTableWidgetItem("0,00 DA")
                debit_item.setToolTip(f"Montant indicatif : {format_money(raw_amt)} DA\nDevis / Commande proforma (Aucun impact financier sur le compte).")
                debit_item.setForeground(QColor("#94a3b8"))
                font = debit_item.font()
                font.setItalic(True)
                debit_item.setFont(font)
            else:
                debit_item = QTableWidgetItem(f"{format_money(debit_val)} DA" if debit_val > 0 else "-")
                if debit_val > 0:
                    debit_item.setForeground(QColor("#0284c7"))
                    debit_item.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 3, debit_item)

            # Crédit (-)
            credit_val = t['credit']
            credit_item = QTableWidgetItem(f"{format_money(credit_val)} DA" if credit_val > 0 else "-")
            credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if credit_val > 0:
                credit_item.setForeground(QColor("#16a34a"))
                credit_item.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            self.table.setItem(row_idx, 4, credit_item)

            # Solde Progressif
            bal_val = t['balance']
            bal_item = QTableWidgetItem(f"{format_money(bal_val)} DA")
            bal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bal_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if bal_val > 0:
                bal_item.setForeground(QColor("#dc2626"))
            elif bal_val < 0:
                bal_item.setForeground(QColor("#16a34a"))
            else:
                bal_item.setForeground(QColor("#475569"))
            self.table.setItem(row_idx, 5, bal_item)

            # Notes
            note_str = t.get('notes') or ""
            if is_non_binding and "Hors bilan" not in note_str:
                note_str = f"Document proforma (Non exigible) | {note_str}".strip(" |")
            note_item = QTableWidgetItem(note_str)
            note_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if is_non_binding:
                note_item.setForeground(QColor("#64748b"))
            self.table.setItem(row_idx, 6, note_item)

    def print_statement(self):
        """Génère un PDF temporaire et l'ouvre directement pour impression."""
        import tempfile
        client = self.ledger_data.get('client', {})
        client_name = client.get('Client_Name') or "Client"
        safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).strip()
        temp_dir = tempfile.gettempdir()
        temp_pdf = os.path.join(temp_dir, f"Releve_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if self._generate_pdf_file(temp_pdf):
            try:
                os.startfile(temp_pdf)
            except Exception as e:
                logging.error(f"Error opening statement PDF for printing: {e}")

    def export_pdf(self):
        client = self.ledger_data.get('client', {})
        client_name = client.get('Client_Name') or "Client"
        safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).strip()
        default_filename = f"Releve_Compte_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le relevé de compte PDF", default_filename, "Fichiers PDF (*.pdf)"
        )
        if not file_path:
            return

        if self._generate_pdf_file(file_path):
            reply = QMessageBox.information(
                self,
                "Export Réussi",
                f"Le relevé de compte a été exporté avec succès :\n{file_path}\n\nSouhaitez-vous l'ouvrir maintenant ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    os.startfile(file_path)
                except Exception as e:
                    logging.error(f"Error opening exported statement PDF: {e}")

    def _generate_pdf_file(self, file_path: str) -> bool:
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Bibliothèque manquante", "La bibliothèque ReportLab n'est pas installée.")
            return False

        try:
            client = self.ledger_data.get('client', {})
            client_name = client.get('Client_Name') or "Client"

            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#007572'),
                spaceAfter=6,
                alignment=1
            )
            normal_style = styles['Normal']
            header_meta_style = ParagraphStyle(
                'HeaderMeta',
                parent=normal_style,
                fontSize=9,
                textColor=colors.HexColor('#475569')
            )

            story = []

            # 1. En-tête de l'entreprise
            company_settings = {}
            if hasattr(self.data_manager, 'company_settings'):
                company_settings = self.data_manager.company_settings.get_settings()

            company_name = company_settings.get('Company_Name') or "ENTREPRISE COMMERCIALE"
            company_phone = company_settings.get('Phone') or ""
            company_email = company_settings.get('Email') or ""
            company_address = company_settings.get('Address') or ""

            header_text = f"<b>{company_name}</b><br/>{company_address}<br/>Tél: {company_phone} | Email: {company_email}"
            
            story.append(Paragraph(header_text, header_meta_style))
            story.append(Spacer(1, 10))

            # 2. Titre du Relevé
            story.append(Paragraph("RELEVÉ DE COMPTE CLIENT (GRAND LIVRE AUXILIAIRE)", title_style))
            period_str = f"Période du <b>{self.date_start.date().toString('dd/MM/yyyy')}</b> au <b>{self.date_end.date().toString('dd/MM/yyyy')}</b>"
            story.append(Paragraph(period_str, ParagraphStyle('Center', parent=normal_style, alignment=1, fontSize=10)))
            story.append(Spacer(1, 12))

            # 3. Informations Client
            tax_id = client.get('Tax_ID_Number') or client.get('Tax_ID') or '-'
            rc = client.get('Commercial_Reg_No') or client.get('Commercial_Register') or '-'
            client_info = [
                [Paragraph(f"<b>Client :</b> {client_name}", normal_style),
                 Paragraph(f"<b>Catégorie Tarifaire :</b> {client.get('Price_Tier', 'Prix_1')}", normal_style)],
                [Paragraph(f"<b>Contact :</b> {client.get('Contact_Person', '-')}", normal_style),
                 Paragraph(f"<b>Téléphone :</b> {client.get('Phone', '-')}", normal_style)],
                [Paragraph(f"<b>NIF :</b> {tax_id}", normal_style),
                 Paragraph(f"<b>RC :</b> {rc}", normal_style)],
                [Paragraph(f"<b>Ville / Adresse :</b> {client.get('City') or client.get('Address') or '-'}", normal_style),
                 Paragraph(f"<b>Plafond de Crédit :</b> {format_money(float(client.get('Credit_Limit') or 0.0))} DA", normal_style)]
            ]
            t_client = Table(client_info, colWidths=[9.5 * cm, 8.5 * cm])
            t_client.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ]))
            story.append(t_client)
            story.append(Spacer(1, 12))

            # 4. Tableau Récapitulatif KPI
            initial = float(self.ledger_data.get('initial_balance', 0.0))
            final = float(self.ledger_data.get('final_balance', 0.0))
            txs = self.ledger_data.get('transactions', [])
            total_debit = sum(t.get('debit', 0.0) for t in txs)
            total_credit = sum(t.get('credit', 0.0) for t in txs)

            kpi_data = [
                ["Solde Antérieur", "Total Débit (Factures & BL)", "Total Crédit (Règlements & Avoirs)", "Nouveau Solde Dû"],
                [f"{format_money(initial)} DA", f"{format_money(total_debit)} DA", f"{format_money(total_credit)} DA", f"{format_money(final)} DA"]
            ]
            t_kpi = Table(kpi_data, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
            t_kpi.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007572')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, 1), 10),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f1f5f9')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0, 0), (-1, -1), 5)
            ]))
            story.append(t_kpi)
            story.append(Spacer(1, 14))

            # 5. Détail des Écritures (Ledger Grid)
            ledger_header = ["Date", "Type Document", "Réf.", "Débit (DA)", "Crédit (DA)", "Solde Progressif (DA)"]
            ledger_table_data = [ledger_header]

            for t in txs:
                is_nb = t.get('is_non_binding', False)
                type_display = t['type'] + (" [Hors bilan]" if is_nb and "[Hors bilan]" not in t['type'] else "")
                d_str = "0.00" if is_nb else (format_money(t['debit']) if t['debit'] > 0 else "-")
                c_str = format_money(t['credit']) if t['credit'] > 0 else "-"
                b_str = format_money(t['balance'])
                ledger_table_data.append([
                    t['date'],
                    type_display,
                    t['reference'],
                    d_str,
                    c_str,
                    b_str
                ])

            t_ledger = Table(
                ledger_table_data, 
                colWidths=[2.3 * cm, 4.7 * cm, 2.8 * cm, 2.7 * cm, 2.7 * cm, 2.8 * cm],
                repeatRows=1
            )
            t_ledger.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (2, -1), 'CENTER'),
                ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            story.append(t_ledger)
            story.append(Spacer(1, 20))

            # 6. Mentions de clôture & Signatures
            sign_data = [
                [Paragraph("<b>Visa & Cachet de l'Entreprise :</b>", normal_style),
                 Paragraph("<b>Accusé de Réception Client :</b>", normal_style)]
            ]
            t_sign = Table(sign_data, colWidths=[9 * cm, 9 * cm])
            t_sign.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 0)
            ]))
            story.append(t_sign)

            doc.build(story)
            return True

        except Exception as e:
            logging.error(f"Error generating statement PDF: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur PDF", f"Impossible de générer le document PDF :\n{str(e)}")
            return False
