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

        self.setWindowTitle("📄 Relevé de Compte Client")
        self.resize(950, 680)
        self.setMinimumSize(800, 550)

        self.init_ui()
        self.apply_preset("this_month")

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. Header Card (Nom du client & Coordonnées)
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.lbl_client_title = QLabel("Chargement du client...")
        self.lbl_client_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        header_layout.addWidget(self.lbl_client_title, 1)

        self.lbl_client_meta = QLabel("")
        self.lbl_client_meta.setStyleSheet("font-size: 12px; color: #64748b;")
        header_layout.addWidget(self.lbl_client_meta)

        layout.addWidget(self.header_frame)

        # 2. Controls Toolbar (Date Filters & Presets)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        filter_layout.addWidget(QLabel("Période :"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Ce mois",
            "Mois précédent",
            "30 derniers jours",
            "Cette année",
            "Tout l'historique"
        ])
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        filter_layout.addWidget(self.preset_combo)

        filter_layout.addWidget(QLabel("Du :"))
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.date_start)

        filter_layout.addWidget(QLabel("Au :"))
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_end)

        self.btn_refresh = QPushButton("🔄 Actualiser")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.load_ledger)
        filter_layout.addWidget(self.btn_refresh)

        filter_layout.addStretch(1)

        self.btn_export_pdf = QPushButton("📑 Exporter en PDF (A4)")
        self.btn_export_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        filter_layout.addWidget(self.btn_export_pdf)

        layout.addLayout(filter_layout)

        # 3. KPI Summary Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.card_initial = self._create_kpi_card("Solde Initial", "0.00 DA", "#64748b")
        self.card_debit = self._create_kpi_card("Total Débit (Factures)", "0.00 DA", "#0284c7")
        self.card_credit = self._create_kpi_card("Total Crédit (Règlements)", "0.00 DA", "#16a34a")
        self.card_final = self._create_kpi_card("Nouveau Solde Dû", "0.00 DA", "#dc2626")

        kpi_layout.addWidget(self.card_initial)
        kpi_layout.addWidget(self.card_debit)
        kpi_layout.addWidget(self.card_credit)
        kpi_layout.addWidget(self.card_final)
        layout.addLayout(kpi_layout)

        # 4. Table du Grand Livre (Transactions Ledger)
        self.table = QTableWidget()
        cols = ["Date", "Type d'Opération", "Référence", "Débit (+ Facture)", "Crédit (- Paiement)", "Solde Cumulé", "Notes"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(34)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.table, 1)

        # 5. Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        self.btn_close = QPushButton("Fermer")
        self.btn_close.setFixedWidth(100)
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

    def _on_preset_changed(self, index):
        presets = ["this_month", "last_month", "last_30_days", "this_year", "all"]
        if 0 <= index < len(presets):
            self.apply_preset(presets[index])

    def apply_preset(self, preset_key):
        today = date.today()
        if preset_key == "this_month":
            start = date(today.year, today.month, 1)
            end = today
        elif preset_key == "last_month":
            first_this_month = date(today.year, today.month, 1)
            last_day_prev = first_this_month - timedelta(days=1)
            start = date(last_day_prev.year, last_day_prev.month, 1)
            end = last_day_prev
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

            type_item = QTableWidgetItem(t['type'])
            type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row_idx, 1, type_item)

            ref_item = QTableWidgetItem(t['reference'])
            ref_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, ref_item)

            debit_val = t['debit']
            debit_item = QTableWidgetItem(format_money(debit_val) if debit_val > 0 else "-")
            debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if debit_val > 0:
                debit_item.setForeground(QColor("#0284c7"))
            self.table.setItem(row_idx, 3, debit_item)

            credit_val = t['credit']
            credit_item = QTableWidgetItem(format_money(credit_val) if credit_val > 0 else "-")
            credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if credit_val > 0:
                credit_item.setForeground(QColor("#16a34a"))
            self.table.setItem(row_idx, 4, credit_item)

            bal_val = t['balance']
            bal_item = QTableWidgetItem(f"{format_money(bal_val)} DA")
            bal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bal_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if bal_val > 0:
                bal_item.setForeground(QColor("#dc2626"))
            elif bal_val < 0:
                bal_item.setForeground(QColor("#16a34a"))
            self.table.setItem(row_idx, 5, bal_item)

            note_item = QTableWidgetItem(t.get('notes') or "")
            self.table.setItem(row_idx, 6, note_item)

    def export_pdf(self):
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Bibliothèque manquante", "La bibliothèque ReportLab n'est pas installée.")
            return

        client = self.ledger_data.get('client', {})
        client_name = client.get('Client_Name') or "Client"
        safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).strip()
        default_filename = f"Releve_Compte_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le relevé de compte PDF", default_filename, "Fichiers PDF (*.pdf)"
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
            story.append(Paragraph("RELEVÉ DE COMPTE CLIENT", title_style))
            period_str = f"Période du <b>{self.date_start.date().toString('dd/MM/yyyy')}</b> au <b>{self.date_end.date().toString('dd/MM/yyyy')}</b>"
            story.append(Paragraph(period_str, ParagraphStyle('Center', parent=normal_style, alignment=1, fontSize=10)))
            story.append(Spacer(1, 12))

            # 3. Informations Client
            client_info = [
                [Paragraph(f"<b>Client :</b> {client_name}", normal_style),
                 Paragraph(f"<b>Catégorie :</b> {client.get('Price_Tier', 'Prix_1')}", normal_style)],
                [Paragraph(f"<b>Contact :</b> {client.get('Contact_Person', '-')}", normal_style),
                 Paragraph(f"<b>Téléphone :</b> {client.get('Phone', '-')}", normal_style)],
                [Paragraph(f"<b>Ville / Adresse :</b> {client.get('City', '-')}", normal_style),
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
                ["Solde Antérieur", "Total Débit (Factures)", "Total Crédit (Règlements)", "Nouveau Solde Dû"],
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
            ledger_header = ["Date", "Opération", "Réf.", "Débit (DA)", "Crédit (DA)", "Solde Cumulé (DA)"]
            ledger_table_data = [ledger_header]

            for t in txs:
                d_str = format_money(t['debit']) if t['debit'] > 0 else "-"
                c_str = format_money(t['credit']) if t['credit'] > 0 else "-"
                b_str = format_money(t['balance'])
                ledger_table_data.append([
                    t['date'],
                    t['type'],
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

            reply = QMessageBox.information(
                self,
                "Export Réussi",
                f"Le relevé de compte a été exporté avec succès :\n{file_path}\n\nSouhaitez-vous l'ouvrir maintenant ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                os.startfile(file_path)

        except Exception as e:
            logging.error(f"Error exporting PDF statement: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur PDF", f"Impossible de générer le document PDF :\n{str(e)}")
