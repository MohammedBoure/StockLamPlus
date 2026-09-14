# ui/widgets/sales/return_dialog.py

import os
import logging
from decimal import Decimal
from datetime import datetime, date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QAbstractItemView, QFrame, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from ui.formatting import format_money, format_quantity

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def export_return_slip_to_pdf(data_manager, return_info: dict, parent_widget=None):
    """
    Génère un Bon de Retour / Avoir A4 professionnel pour le retour sans facture.
    """
    if not HAS_REPORTLAB:
        if parent_widget:
            QMessageBox.warning(parent_widget, "ReportLab manquant", "La bibliothèque ReportLab n'est pas disponible pour l'impression PDF.")
        return None

    return_no = return_info.get('return_no', 'RET-SF')
    safe_no = "".join(c for c in return_no if c.isalnum() or c in ('-', '_')).strip()
    default_filename = f"Bon_Retour_{safe_no}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, "Enregistrer le Bon de Retour (Avoir)", default_filename, "Fichiers PDF (*.pdf)"
    )
    if not file_path:
        return None

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
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#c2410c'),
            spaceAfter=6,
            alignment=1
        )
        header_meta_style = ParagraphStyle(
            'HeaderMeta',
            parent=normal_style,
            fontSize=9,
            textColor=colors.HexColor('#475569')
        )

        story = []

        # 1. En-tête Société
        company_settings = {}
        if hasattr(data_manager, 'company_settings'):
            company_settings = data_manager.company_settings.get_settings()

        comp_name = company_settings.get('Company_Name') or "ENTREPRISE COMMERCIALE"
        comp_phone = company_settings.get('Phone') or ""
        comp_addr = company_settings.get('Address') or ""
        header_text = f"<b>{comp_name}</b><br/>{comp_addr}<br/>Tél: {comp_phone}"
        story.append(Paragraph(header_text, header_meta_style))
        story.append(Spacer(1, 10))

        # 2. Titre du Document
        story.append(Paragraph("BON DE RETOUR SANS FACTURE (AVOIR)", title_style))
        doc_date = datetime.now().strftime('%d/%m/%Y %H:%M')
        story.append(Paragraph(f"N° de Retour : <b>{return_no}</b>  |  Date : <b>{doc_date}</b>", ParagraphStyle('C', parent=normal_style, alignment=1, fontSize=10)))
        story.append(Spacer(1, 12))

        # 3. Informations générales du retour
        info_data = [
            [Paragraph("<b>Type d'opération :</b> Retour Marchandise (Sans Facture)", normal_style),
             Paragraph(f"<b>Mode Remboursement :</b> {return_info.get('refund_method', '-')}", normal_style)],
            [Paragraph(f"<b>Motif du Retour :</b> {return_info.get('reason', '-')}", normal_style),
             Paragraph(f"<b>Emplacement Réception :</b> {return_info.get('location_name', '-')}", normal_style)],
            [Paragraph(f"<b>Client :</b> Client Comptoir", normal_style),
             Paragraph(f"<b>Opérateur / Manager :</b> Utilisateur #{return_info.get('user_id', 1)}", normal_style)]
        ]
        t_info = Table(info_data, colWidths=[9.5 * cm, 8.5 * cm])
        t_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff7ed')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#fdba74')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(t_info)
        story.append(Spacer(1, 14))

        # 4. Tableau des articles retournés
        headers = ["Désignation Produit", "N° Lot", "Code-barres", "Qté", "Prix U. HT", "TVA %", "Total TTC"]
        p_name = return_info.get('product_name', 'Article')
        lot_no = return_info.get('lot_number', '-')
        barcode = return_info.get('barcode', '-')
        qty_str = format_quantity(return_info.get('qty', 1))
        price_str = format_money(return_info.get('unit_price_ht', 0)) + " DA"
        tva_str = f"{return_info.get('tva_percent', 0)}%"
        total_ttc_str = format_money(return_info.get('total_ttc', 0)) + " DA"

        items_table_data = [
            headers,
            [p_name, lot_no, barcode, qty_str, price_str, tva_str, total_ttc_str]
        ]
        t_items = Table(items_table_data, colWidths=[5.5 * cm, 2.5 * cm, 2.5 * cm, 1.8 * cm, 2.2 * cm, 1.5 * cm, 2.0 * cm])
        t_items.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ea580c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(t_items)
        story.append(Spacer(1, 14))

        # 5. Totaux Financiers
        totals_data = [
            ["Total HT :", f"{format_money(return_info.get('total_ht', 0))} DA"],
            ["Total TVA :", f"{format_money(return_info.get('total_tva', 0))} DA"],
            ["NET À REMBOURSER TTC :", f"{total_ttc_str}"]
        ]
        t_totals = Table(totals_data, colWidths=[12.5 * cm, 5.5 * cm])
        t_totals.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ffedd5')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#9a3412')),
            ('FONTSIZE', (0, -1), (-1, -1), 11),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#ea580c'))
        ]))
        story.append(t_totals)
        story.append(Spacer(1, 25))

        # 6. Signatures
        sig_data = [
            ["Signature / Accord Client :", "Visa Responsable Stock / Caisse :"],
            ["\n\n\n___________________________", "\n\n\n___________________________"]
        ]
        t_sig = Table(sig_data, colWidths=[9.0 * cm, 9.0 * cm])
        t_sig.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(t_sig)

        doc.build(story)
        if os.name == 'nt':
            os.startfile(file_path)
        return file_path
    except Exception as exc:
        logging.error(f"Error generating return slip PDF: {exc}", exc_info=True)
        if parent_widget:
            QMessageBox.critical(parent_widget, "Erreur PDF", f"Échec de création du bon de retour PDF: {exc}")
        return None


class ReturnProductSelectionDialog(QDialog):
    """
    Dialogue moderne et ergonomique pour effectuer un retour d'article sans facture d'origine.
    Remplace les invites de saisie manuelle d'IDs bruts (getInt/QInputDialog) par :
    - Un champ de recherche auto-focus avec filtrage instantané et capture immédiate des scans code-barres.
    - Une grille des résultats claire présentant les articles et leurs lots/batches disponibles.
    - Une configuration complète du retour (Quantité, Emplacement de destination par défaut Quarantaine/Retour, Motif déroulant).
    - Un traitement transactionnel atomique incrémentant le stock du lot, journalisant dans Stock_Movement_Log,
      et générant le Bon de Retour / Avoir (avec possibilité d'impression PDF).
    """

    REASON_OPTIONS = [
        ("Défectueux / Avarié (Defective)", "Article défectueux ou avarié"),
        ("Changement d'avis du client (Customer Changed Mind)", "Changement d'avis du client"),
        ("Produit Périmé / Date courte (Expired)", "Produit périmé ou proche péremption"),
        ("Erreur de commande / Délivrance (Wrong Item)", "Erreur de délivrance ou référence"),
        ("Autre motif (Préciser ci-dessous)", "Autre motif")
    ]

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("↩️ Retour d'Article sans Facture — Sélection du Lot")
        self.resize(960, 720)
        self.setMinimumSize(850, 600)

        self.batches_cache = []
        self.locations = []
        self.selected_batch = None
        self.quarantine_location_id = None

        self._init_ui()
        self._load_base_data()

    def showEvent(self, event):
        super().showEvent(event)
        # Auto-focus the search bar immediately upon opening the modal
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return 1

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # 1. Header Information Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #fff7ed;
                border: 1px solid #fdba74;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(4, 2, 4, 2)
        lbl_head = QLabel(
            "<b>↩️ Module de Retour sans Facture (Manager)</b> — "
            "Recherchez l'article par code-barres ou texte, puis sélectionnez le lot exact pour réintégrer le stock."
        )
        lbl_head.setStyleSheet("color: #9a3412; font-size: 12px;")
        h_layout.addWidget(lbl_head)
        layout.addWidget(header_frame)

        # 2. Search Header with Auto-Focus and Scanner Capture
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        lbl_search = QLabel("🔍 Recherche / Scan :")
        lbl_search.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 13px;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scanner un code-barres ou saisir le nom, la référence ou le n° de lot...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                min-height: 36px;
                font-size: 13px;
                padding: 4px 10px;
                border: 2px solid #007572;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #ea580c;
            }
        """)
        self.search_input.textChanged.connect(self._filter_batches)
        self.search_input.returnPressed.connect(self._handle_instant_scan)

        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_input, stretch=1)
        layout.addLayout(search_layout)

        # 3. Results Grid: Comprehensive Batch & Product Grid
        grp_grid = QGroupBox("1. Sélectionner le Lot / Batch retourné par le client")
        grp_grid.setStyleSheet("QGroupBox { font-weight: bold; color: #0f172a; }")
        vbox_grid = QVBoxLayout(grp_grid)
        vbox_grid.setContentsMargins(8, 8, 8, 8)

        self.table_batches = QTableWidget()
        cols = [
            "ID Lot", "Désignation Produit", "Réf / Code-barres", "N° Lot",
            "Emplacement", "Stock Actuel", "Date Péremption",
            "Prix Vente HT", "TVA %", "Prix TTC"
        ]
        self.table_batches.setColumnCount(len(cols))
        self.table_batches.setHorizontalHeaderLabels(cols)
        self.table_batches.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_batches.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeToContents)

        self.table_batches.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_batches.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_batches.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_batches.setAlternatingRowColors(True)
        self.table_batches.verticalHeader().setDefaultSectionSize(32)
        self.table_batches.itemSelectionChanged.connect(self._on_batch_selected)
        self.table_batches.doubleClicked.connect(lambda: self.spin_qty.setFocus())

        vbox_grid.addWidget(self.table_batches)
        layout.addWidget(grp_grid, stretch=1)

        # 4. Return Configuration Form
        grp_config = QGroupBox("2. Configuration du Retour & Réintégration en Stock")
        grp_config.setStyleSheet("QGroupBox { font-weight: bold; color: #0f172a; }")
        config_layout = QVBoxLayout(grp_config)
        config_layout.setContentsMargins(10, 10, 10, 10)
        config_layout.setSpacing(8)

        # Row A: Quantity & Financial parameters
        row_qty_price = QHBoxLayout()
        row_qty_price.setSpacing(12)

        row_qty_price.addWidget(QLabel("<b>Quantité à retourner :</b>"))
        self.spin_qty = QDoubleSpinBox()
        self.spin_qty.setRange(0.01, 9999.0)
        self.spin_qty.setValue(1.0)
        self.spin_qty.setDecimals(2)
        self.spin_qty.setFixedWidth(110)
        self.spin_qty.setStyleSheet("min-height: 28px; font-weight: bold; font-size: 13px;")
        self.spin_qty.valueChanged.connect(self._recalc_totals)
        row_qty_price.addWidget(self.spin_qty)

        row_qty_price.addWidget(QLabel("<b>Prix U. HT :</b>"))
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0.0, 999999999.0)
        self.spin_price.setDecimals(2)
        self.spin_price.setSuffix(" DA")
        self.spin_price.setFixedWidth(140)
        self.spin_price.setStyleSheet("min-height: 28px; font-weight: bold;")
        self.spin_price.valueChanged.connect(self._recalc_totals)
        row_qty_price.addWidget(self.spin_price)

        row_qty_price.addWidget(QLabel("<b>TVA :</b>"))
        self.spin_tva = QDoubleSpinBox()
        self.spin_tva.setRange(0.0, 100.0)
        self.spin_tva.setValue(0.0)
        self.spin_tva.setSuffix(" %")
        self.spin_tva.setFixedWidth(85)
        self.spin_tva.setStyleSheet("min-height: 28px;")
        self.spin_tva.valueChanged.connect(self._recalc_totals)
        row_qty_price.addWidget(self.spin_tva)

        row_qty_price.addStretch(1)
        config_layout.addLayout(row_qty_price)

        # Row B: Destination location & Refund Method
        row_loc_refund = QHBoxLayout()
        row_loc_refund.setSpacing(12)

        row_loc_refund.addWidget(QLabel("<b>Emplacement de Réception :</b>"))
        self.cb_location = QComboBox()
        self.cb_location.setMinimumWidth(220)
        self.cb_location.setStyleSheet("min-height: 28px;")
        row_loc_refund.addWidget(self.cb_location)

        row_loc_refund.addWidget(QLabel("<b>Moyen Remboursement :</b>"))
        self.cb_refund = QComboBox()
        refund_methods = [
            ("Espèces (Cash)", "Cash"),
            ("Carte bancaire", "Card"),
            ("Virement bancaire", "Transfer"),
            ("Versement bancaire", "Versement"),
            ("Crédit client (Avoir)", "Credit"),
            ("Autre", "Other")
        ]
        for label, val in refund_methods:
            self.cb_refund.addItem(label, val)
        self.cb_refund.setStyleSheet("min-height: 28px;")
        row_loc_refund.addWidget(self.cb_refund)

        row_loc_refund.addStretch(1)
        config_layout.addLayout(row_loc_refund)

        # Row C: Reason Dropdown & Notes
        row_reason = QHBoxLayout()
        row_reason.setSpacing(10)

        row_reason.addWidget(QLabel("<b>Motif du Retour :</b>"))
        self.cb_reason = QComboBox()
        self.cb_reason.setMinimumWidth(260)
        for label, val in self.REASON_OPTIONS:
            self.cb_reason.addItem(label, val)
        self.cb_reason.setStyleSheet("min-height: 28px;")
        row_reason.addWidget(self.cb_reason)

        self.edit_reason_notes = QLineEdit()
        self.edit_reason_notes.setPlaceholderText("Précisions complémentaires optionnelles (détails du motif)...")
        self.edit_reason_notes.setStyleSheet("min-height: 28px; padding: 2px 8px; border: 1px solid #cbd5e1; border-radius: 4px;")
        row_reason.addWidget(self.edit_reason_notes, stretch=1)

        config_layout.addLayout(row_reason)
        layout.addWidget(grp_config)

        # 5. Financial Live Summary Banner
        self.lbl_totals_banner = QLabel("Total Ligne HT : 0.00 DA  |  TVA : 0.00 DA  |  <b>Total Remboursement TTC : 0.00 DA</b>")
        self.lbl_totals_banner.setStyleSheet("""
            QLabel {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                color: #0f172a;
            }
        """)
        self.lbl_totals_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_totals_banner)

        # 6. Bottom Actions
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("↩️ Valider le Retour & Réintégrer le Stock")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 24px;
                border-radius: 4px;
                min-height: 36px;
                border: none;
            }
            QPushButton:hover {
                background-color: #c2410c;
            }
            QPushButton:disabled {
                background-color: #fed7aa;
                color: #9a3412;
            }
        """)
        self.btn_submit.clicked.connect(self._submit_return)
        self.btn_submit.setEnabled(False)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_submit)
        layout.addLayout(btn_row)

    def _load_base_data(self):
        # 1. Locations
        try:
            self.locations = self.data_manager.locations.get_all_locations()
            self.cb_location.clear()

            # Detect return / quarantine location
            self.quarantine_location_id = None
            default_index = 0

            for idx, loc in enumerate(self.locations):
                loc_id = loc.get('Location_ID')
                loc_name = loc.get('Location_Name') or f"Emplacement #{loc_id}"
                self.cb_location.addItem(loc_name, loc_id)

                loc_lower = loc_name.lower()
                if any(kw in loc_lower for kw in ['retour', 'quarantine', 'quarantaine', 'sav', 'rebut']):
                    self.quarantine_location_id = loc_id
                    default_index = idx

            if self.locations:
                self.cb_location.setCurrentIndex(default_index)
        except Exception as e:
            logging.error(f"Error loading locations in return dialog: {e}")

        # 2. Batches
        try:
            self.batches_cache = self.data_manager.batches.get_all_batches_with_details(include_zero_stock=True) or []
        except Exception as e:
            logging.error(f"Error loading batches in return dialog: {e}")
            self.batches_cache = []

        self._populate_grid(self.batches_cache[:50])

    def _populate_grid(self, batches):
        self.table_batches.setRowCount(0)
        for r, b in enumerate(batches):
            self.table_batches.insertRow(r)

            it_id = QTableWidgetItem(str(b.get('Batch_ID')))
            it_id.setData(Qt.UserRole, b)
            it_id.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 0, it_id)

            # Product Name
            p_name = b.get('Product_Name') or f"Produit #{b.get('Product_ID')}"
            it_pname = QTableWidgetItem(p_name)
            it_pname.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_batches.setItem(r, 1, it_pname)

            # Barcode / SKU
            barcode = b.get('External_Barcode') or b.get('Internal_Barcode') or b.get('Manuf_Cat_No') or '-'
            it_bc = QTableWidgetItem(barcode)
            it_bc.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 2, it_bc)

            # Lot Number
            lot_no = b.get('Lot_Number') or 'Sans Lot'
            it_lot = QTableWidgetItem(lot_no)
            it_lot.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 3, it_lot)

            # Location
            loc = b.get('Location_Name') or '-'
            it_loc = QTableWidgetItem(loc)
            self.table_batches.setItem(r, 4, it_loc)

            # Current Stock
            qty = float(b.get('Quantity_Current') or 0.0)
            it_qty = QTableWidgetItem(format_quantity(qty))
            it_qty.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 5, it_qty)

            # Expiry Date
            exp = str(b.get('Expiry_Date') or '-')
            it_exp = QTableWidgetItem(exp)
            it_exp.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 6, it_exp)

            # Price HT
            price_ht = float(b.get('Selling_Price_HT') or b.get('Unit_Price_Received') or 0.0)
            it_price = QTableWidgetItem(format_money(price_ht))
            it_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_batches.setItem(r, 7, it_price)

            # TVA %
            tva = float(b.get('Selling_TVA_Percent') or b.get('Tax_Rate_Percent') or 0.0)
            it_tva = QTableWidgetItem(f"{tva:.1f}%")
            it_tva.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 8, it_tva)

            # Price TTC
            price_ttc = price_ht * (1.0 + tva / 100.0)
            it_ttc = QTableWidgetItem(format_money(price_ttc))
            it_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_ttc.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_batches.setItem(r, 9, it_ttc)

    def _filter_batches(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._populate_grid(self.batches_cache[:50])
            self.selected_batch = None
            self._check_ready()
            return

        matching = []
        for b in self.batches_cache:
            p_name = str(b.get('Product_Name') or '').lower()
            p_id = str(b.get('Product_ID') or '')
            lot_no = str(b.get('Lot_Number') or '').lower()
            int_bc = str(b.get('Internal_Barcode') or '').lower()
            ext_bc = str(b.get('External_Barcode') or '').lower()
            cat_no = str(b.get('Manuf_Cat_No') or '').lower()
            batch_id = str(b.get('Batch_ID') or '')

            if (query in p_name or query in p_id or query in lot_no or
                query in int_bc or query in ext_bc or query in cat_no or query in batch_id):
                matching.append(b)
                if len(matching) >= 60:
                    break

        self._populate_grid(matching)
        if len(matching) == 1:
            self.table_batches.selectRow(0)

    def _handle_instant_scan(self):
        query = self.search_input.text().strip()
        if not query:
            return

        found_batch = None
        for b in self.batches_cache:
            int_bc = str(b.get('Internal_Barcode') or '').strip()
            ext_bc = str(b.get('External_Barcode') or '').strip()
            lot_no = str(b.get('Lot_Number') or '').strip()
            cat_no = str(b.get('Manuf_Cat_No') or '').strip()
            if query in (int_bc, ext_bc, lot_no, cat_no):
                found_batch = b
                break

        if found_batch:
            self._populate_grid([found_batch])
            self.table_batches.selectRow(0)
            self.spin_qty.setFocus()
            self.spin_qty.selectAll()

    def _on_batch_selected(self):
        row = self.table_batches.currentRow()
        if row < 0:
            self.selected_batch = None
            self._check_ready()
            return

        id_item = self.table_batches.item(row, 0)
        if not id_item:
            return

        self.selected_batch = id_item.data(Qt.UserRole)

        # Prefill Price & TVA
        price = float(self.selected_batch.get('Selling_Price_HT') or self.selected_batch.get('Unit_Price_Received') or 0.0)
        tva = float(self.selected_batch.get('Selling_TVA_Percent') or self.selected_batch.get('Tax_Rate_Percent') or 0.0)
        self.spin_price.setValue(price)
        self.spin_tva.setValue(tva)

        # Destination Location: prioritize Quarantine/Return location if available, otherwise batch location
        if self.quarantine_location_id:
            idx = self.cb_location.findData(self.quarantine_location_id)
            if idx >= 0:
                self.cb_location.setCurrentIndex(idx)
        else:
            loc_id = self.selected_batch.get('Location_ID')
            if loc_id:
                idx = self.cb_location.findData(loc_id)
                if idx >= 0:
                    self.cb_location.setCurrentIndex(idx)

        self._recalc_totals()
        self._check_ready()

    def _recalc_totals(self):
        qty = self.spin_qty.value()
        price_ht = self.spin_price.value()
        tva = self.spin_tva.value()

        tot_ht = qty * price_ht
        tot_tva = tot_ht * (tva / 100.0)
        tot_ttc = tot_ht + tot_tva

        self.lbl_totals_banner.setText(
            f"Total Ligne HT : {format_money(tot_ht)} DA  |  "
            f"TVA : {format_money(tot_tva)} DA  |  "
            f"<b>Total Remboursement TTC : {format_money(tot_ttc)} DA</b>"
        )

    def _check_ready(self):
        ready = (self.selected_batch is not None)
        self.btn_submit.setEnabled(ready)

    def _submit_return(self):
        if not self.selected_batch:
            QMessageBox.warning(self, "Sélection requise", "Veuillez sélectionner le lot d'inventaire retourné.")
            return

        qty = self.spin_qty.value()
        if qty <= 0:
            QMessageBox.warning(self, "Quantité invalide", "La quantité à retourner doit être supérieure à zéro.")
            self.spin_qty.setFocus()
            return

        if qty > 200:
            reply_large = QMessageBox.question(
                self, "Quantité élevée",
                f"Attention : La quantité spécifiée ({format_quantity(qty)}) est inhabituellement élevée.\n"
                f"Confirmez-vous ce retour de stock volumineux ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply_large != QMessageBox.Yes:
                return

        reason_base = self.cb_reason.currentData() or self.cb_reason.currentText()
        notes = self.edit_reason_notes.text().strip()
        full_reason = f"{reason_base} - {notes}" if notes else reason_base

        price_ht = self.spin_price.value()
        tva = self.spin_tva.value()
        refund_method = self.cb_refund.currentData()
        user_id = self._current_user_id()
        dest_loc_id = self.cb_location.currentData()
        dest_loc_name = self.cb_location.currentText()

        tot_ht = qty * price_ht
        tot_tva = tot_ht * (tva / 100.0)
        tot_ttc = tot_ht + tot_tva

        p_name = self.selected_batch.get('Product_Name') or f"Produit #{self.selected_batch.get('Product_ID')}"
        lot_no = self.selected_batch.get('Lot_Number') or 'Sans Lot'

        confirm_msg = (
            f"Confirmez-vous l'enregistrement de ce retour d'article ?\n\n"
            f"• Produit : {p_name}\n"
            f"• Lot N° : {lot_no} (ID #{self.selected_batch.get('Batch_ID')})\n"
            f"• Quantité : {format_quantity(qty)}\n"
            f"• Emplacement Destination : {dest_loc_name}\n"
            f"• Montant TTC à rembourser : {format_money(tot_ttc)} DA ({self.cb_refund.currentText()})\n"
            f"• Motif : {full_reason}"
        )
        reply = QMessageBox.question(self, "Confirmation du Retour", confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            return

        try:
            success, result = self.data_manager.pos_features.create_no_invoice_return(
                product_id=self.selected_batch['Product_ID'],
                batch_id=self.selected_batch['Batch_ID'],
                qty_returned=qty,
                unit_price_ht=price_ht,
                tva_percent=tva,
                refund_method=refund_method,
                reason=full_reason,
                user_id=user_id
            )

            if success:
                return_no = result.get('return_no', 'RET-SF')

                # If destination location was altered, update batch location
                if dest_loc_id and dest_loc_id != self.selected_batch.get('Location_ID'):
                    try:
                        self.data_manager.batches.update_batch_location(self.selected_batch['Batch_ID'], dest_loc_id)
                    except Exception as e_loc:
                        logging.warning(f"Could not update batch location after return: {e_loc}")

                return_info = {
                    'return_no': return_no,
                    'product_name': p_name,
                    'lot_number': lot_no,
                    'barcode': self.selected_batch.get('External_Barcode') or self.selected_batch.get('Internal_Barcode') or '-',
                    'qty': qty,
                    'unit_price_ht': price_ht,
                    'tva_percent': tva,
                    'total_ht': tot_ht,
                    'total_tva': tot_tva,
                    'total_ttc': tot_ttc,
                    'location_name': dest_loc_name,
                    'refund_method': self.cb_refund.currentText(),
                    'reason': full_reason,
                    'user_id': user_id
                }

                # Ask user if they wish to print / export the PDF Return Slip
                ask_pdf = QMessageBox.question(
                    self, "Retour Enregistré avec Succès",
                    f"Le retour sans facture a été validé avec succès !\n\n"
                    f"• N° de Retour (Avoir) : {return_no}\n"
                    f"• Stock réintégré : {format_quantity(qty)} dans le lot #{self.selected_batch['Batch_ID']}.\n\n"
                    f"Souhaitez-vous générer et imprimer le Bon de Retour (Avoir) en PDF ?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )

                if ask_pdf == QMessageBox.Yes:
                    export_return_slip_to_pdf(self.data_manager, return_info, self)

                self.accept()
            else:
                QMessageBox.warning(self, "Échec du Retour", result.get('message', "Impossible d'enregistrer le retour."))
        except Exception as exc:
            logging.error(f"Error processing return without invoice: {exc}", exc_info=True)
            QMessageBox.critical(self, "Erreur Système", f"Une erreur est survenue lors de l'enregistrement du retour :\n{exc}")
