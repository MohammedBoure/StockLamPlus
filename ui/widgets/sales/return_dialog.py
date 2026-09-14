# ui/widgets/sales/return_dialog.py

import logging
from decimal import Decimal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from ui.formatting import format_money, format_quantity


class ReturnProductSelectionDialog(QDialog):
    """
    Dialogue moderne et ergonomique pour effectuer un retour d'article sans facture d'origine.
    Remplace la saisie manuelle d'IDs bruts par une recherche textuelle/code-barres,
    une sélection de lot dans une grille, et le choix de l'emplacement de destination.
    """

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("↩️ Retour d'Article sans Facture (Manager)")
        self.resize(880, 700)

        self.products_cache = []
        self.all_batches_cache = []
        self.selected_product = None
        self.selected_batch = None

        self._init_ui()
        self._load_base_data()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #fff7ed; border: 1px solid #fdba74; border-radius: 6px; padding: 8px 12px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(0, 0, 0, 0)
        lbl_head = QLabel("<b>Module de Retour de Stock sans Facture</b> — Sélectionnez l'article et le lot concerné pour réintégrer le stock et rembourser le client.")
        lbl_head.setStyleSheet("color: #9a3412; font-size: 12px;")
        h_layout.addWidget(lbl_head)
        layout.addWidget(header_frame)

        # 2. Search Box
        search_layout = QHBoxLayout()
        lbl_search = QLabel("🔍 Rechercher :")
        lbl_search.setStyleSheet("font-weight: bold; color: #334155;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scanner un code-barres ou taper désignation, référence article...")
        self.search_input.setStyleSheet("min-height: 32px; font-size: 13px; padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.search_input.textChanged.connect(self._filter_products)
        self.search_input.returnPressed.connect(self._handle_instant_scan)
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_input, stretch=1)
        layout.addLayout(search_layout)

        # 3. Products Table
        grp_products = QGroupBox("1. Produits correspondants")
        grp_products.setStyleSheet("font-weight: bold; color: #1e293b;")
        vbox_p = QVBoxLayout(grp_products)
        vbox_p.setContentsMargins(8, 8, 8, 8)

        self.table_products = QTableWidget()
        cols_p = ["ID", "Désignation Produit", "Réf / Cat No", "Famille", "Unité", "Stock Total"]
        self.table_products.setColumnCount(len(cols_p))
        self.table_products.setHorizontalHeaderLabels(cols_p)
        self.table_products.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_products.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_products.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_products.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_products.setAlternatingRowColors(True)
        self.table_products.itemSelectionChanged.connect(self._on_product_selected)
        self.table_products.setMaximumHeight(150)
        vbox_p.addWidget(self.table_products)
        layout.addWidget(grp_products)

        # 4. Batches Grid
        grp_batches = QGroupBox("2. Lots d'inventaire disponibles pour l'article")
        grp_batches.setStyleSheet("font-weight: bold; color: #1e293b;")
        vbox_b = QVBoxLayout(grp_batches)
        vbox_b.setContentsMargins(8, 8, 8, 8)

        self.table_batches = QTableWidget()
        cols_b = ["Batch ID", "Lot N°", "Emplacement", "Code-barres", "Stock Actuel", "Date Péremption", "Prix Vente HT", "TVA %"]
        self.table_batches.setColumnCount(len(cols_b))
        self.table_batches.setHorizontalHeaderLabels(cols_b)
        self.table_batches.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_batches.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_batches.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_batches.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_batches.setAlternatingRowColors(True)
        self.table_batches.itemSelectionChanged.connect(self._on_batch_selected)
        self.table_batches.setMaximumHeight(140)
        vbox_b.addWidget(self.table_batches)
        layout.addWidget(grp_batches)

        # 5. Parameters & Form Grid
        grp_params = QGroupBox("3. Paramètres du retour & Remboursement")
        grp_params.setStyleSheet("font-weight: bold; color: #1e293b;")
        grid_params = QFormLayout(grp_params)
        grid_params.setContentsMargins(12, 12, 12, 12)
        grid_params.setSpacing(8)

        row_spin = QHBoxLayout()
        # Qty
        self.spin_qty = QDoubleSpinBox()
        self.spin_qty.setRange(0.01, 999999.0)
        self.spin_qty.setValue(1.0)
        self.spin_qty.setDecimals(2)
        self.spin_qty.setStyleSheet("min-height: 28px; font-weight: bold;")
        self.spin_qty.valueChanged.connect(self._recalc_totals)
        row_spin.addWidget(QLabel("<b>Quantité :</b>"))
        row_spin.addWidget(self.spin_qty)

        # Price HT
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setRange(0.0, 999999999.0)
        self.spin_price.setDecimals(2)
        self.spin_price.setSuffix(" DA")
        self.spin_price.setStyleSheet("min-height: 28px; font-weight: bold;")
        self.spin_price.valueChanged.connect(self._recalc_totals)
        row_spin.addWidget(QLabel("<b>Prix U. HT :</b>"))
        row_spin.addWidget(self.spin_price)

        # TVA
        self.spin_tva = QDoubleSpinBox()
        self.spin_tva.setRange(0.0, 100.0)
        self.spin_tva.setValue(0.0)
        self.spin_tva.setSuffix(" %")
        self.spin_tva.setStyleSheet("min-height: 28px; font-weight: bold;")
        self.spin_tva.valueChanged.connect(self._recalc_totals)
        row_spin.addWidget(QLabel("<b>TVA :</b>"))
        row_spin.addWidget(self.spin_tva)

        grid_params.addRow(row_spin)

        # Location & Refund Method
        row_loc = QHBoxLayout()
        self.cb_location = QComboBox()
        self.cb_location.setMinimumWidth(200)
        self.cb_location.setStyleSheet("min-height: 28px;")
        row_loc.addWidget(QLabel("<b>Emplacement Réception :</b>"))
        row_loc.addWidget(self.cb_location)

        self.cb_refund = QComboBox()
        refund_methods = [
            ("Espèces (Cash)", "Cash"),
            ("Carte bancaire", "Card"),
            ("Virement bancaire", "Transfer"),
            ("Versement bancaire", "Versement"),
            ("Crédit client", "Credit"),
            ("Autre", "Other")
        ]
        for label, val in refund_methods:
            self.cb_refund.addItem(label, val)
        self.cb_refund.setStyleSheet("min-height: 28px;")
        row_loc.addWidget(QLabel("<b>Moyen Remboursement :</b>"))
        row_loc.addWidget(self.cb_refund)

        grid_params.addRow(row_loc)

        # Mandatory Reason
        self.edit_reason = QLineEdit()
        self.edit_reason.setPlaceholderText("Motif obligatoire (ex: Défaut de fabrication, commande erronée...)")
        self.edit_reason.setStyleSheet("min-height: 28px; padding: 2px 6px;")
        grid_params.addRow("<b>Motif obligatoire :</b>", self.edit_reason)

        layout.addWidget(grp_params)

        # 6. Live Totals Banner
        self.lbl_totals_banner = QLabel("Total Ligne HT : 0.00 DA  |  TVA : 0.00 DA  |  <b>Total Remboursement TTC : 0.00 DA</b>")
        self.lbl_totals_banner.setStyleSheet("""
            QLabel {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                color: #0f172a;
            }
        """)
        self.lbl_totals_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_totals_banner)

        # 7. Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("↩️ Valider le Retour et Réintégrer le Stock")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 4px;
                min-height: 34px;
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
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_submit)
        layout.addLayout(btn_row)

    def _load_base_data(self):
        # 1. Locations
        try:
            locations = self.data_manager.locations.get_all_locations()
            self.cb_location.clear()
            for loc in locations:
                loc_name = loc.get('Location_Name') or f"Emplacement #{loc.get('Location_ID')}"
                self.cb_location.addItem(loc_name, loc.get('Location_ID'))
        except Exception as e:
            logging.error(f"Error loading locations: {e}")

        # 2. Products
        try:
            self.products_cache = self.data_manager.products.get_all_products()
        except Exception as e:
            logging.error(f"Error loading products: {e}")
            self.products_cache = []

        # 3. Batches
        try:
            self.all_batches_cache = self.data_manager.batches.get_all_batches_with_details(include_zero_stock=True)
        except Exception as e:
            logging.error(f"Error loading batches: {e}")
            self.all_batches_cache = []

        self._populate_products_table(self.products_cache[:50])

    def _populate_products_table(self, products):
        self.table_products.setRowCount(0)
        for r, p in enumerate(products):
            self.table_products.insertRow(r)
            
            it_id = QTableWidgetItem(str(p.get('Product_ID')))
            it_id.setData(Qt.UserRole, p)
            self.table_products.setItem(r, 0, it_id)
            self.table_products.setItem(r, 1, QTableWidgetItem(str(p.get('Product_Name') or '')))
            self.table_products.setItem(r, 2, QTableWidgetItem(str(p.get('Manuf_Cat_No') or '-')))
            self.table_products.setItem(r, 3, QTableWidgetItem(str(p.get('Family_Name') or '-')))
            self.table_products.setItem(r, 4, QTableWidgetItem(str(p.get('Stock_Unit') or 'Unit')))
            
            # Stock sum
            p_id = p.get('Product_ID')
            stock = sum(float(b.get('Quantity_Current') or 0) for b in self.all_batches_cache if b.get('Product_ID') == p_id)
            it_stock = QTableWidgetItem(format_quantity(stock))
            it_stock.setTextAlignment(Qt.AlignCenter)
            self.table_products.setItem(r, 5, it_stock)

    def _filter_products(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._populate_products_table(self.products_cache[:50])
            return

        matching = []
        for p in self.products_cache:
            p_id = str(p.get('Product_ID') or '')
            name = str(p.get('Product_Name') or '').lower()
            ref = str(p.get('Manuf_Cat_No') or '').lower()
            if query in p_id or query in name or query in ref:
                matching.append(p)
                if len(matching) >= 50:
                    break

        self._populate_products_table(matching)
        if len(matching) == 1:
            self.table_products.selectRow(0)

    def _handle_instant_scan(self):
        query = self.search_input.text().strip()
        if not query:
            return

        # Check in batches barcodes
        found_batch = None
        for b in self.all_batches_cache:
            int_bc = str(b.get('Internal_Barcode') or '').strip()
            ext_bc = str(b.get('External_Barcode') or '').strip()
            lot_no = str(b.get('Lot_Number') or '').strip()
            if query == int_bc or query == ext_bc or query == lot_no:
                found_batch = b
                break

        if found_batch:
            target_pid = found_batch.get('Product_ID')
            # Select product in table
            for p in self.products_cache:
                if p.get('Product_ID') == target_pid:
                    self._populate_products_table([p])
                    self.table_products.selectRow(0)
                    break

            # Select batch in batch table
            for r in range(self.table_batches.rowCount()):
                b_item = self.table_batches.item(r, 0)
                if b_item and b_item.data(Qt.UserRole).get('Batch_ID') == found_batch.get('Batch_ID'):
                    self.table_batches.selectRow(r)
                    break

    def _on_product_selected(self):
        row = self.table_products.currentRow()
        if row < 0:
            self.selected_product = None
            self.table_batches.setRowCount(0)
            self._check_ready()
            return

        p_item = self.table_products.item(row, 0)
        if not p_item:
            return

        self.selected_product = p_item.data(Qt.UserRole)
        p_id = self.selected_product.get('Product_ID')
        product_batches = [b for b in self.all_batches_cache if b.get('Product_ID') == p_id]

        self.table_batches.setRowCount(0)
        for r, b in enumerate(product_batches):
            self.table_batches.insertRow(r)
            it_id = QTableWidgetItem(str(b.get('Batch_ID')))
            it_id.setData(Qt.UserRole, b)
            self.table_batches.setItem(r, 0, it_id)
            self.table_batches.setItem(r, 1, QTableWidgetItem(str(b.get('Lot_Number') or 'Sans Lot')))
            self.table_batches.setItem(r, 2, QTableWidgetItem(str(b.get('Location_Name') or '-')))
            self.table_batches.setItem(r, 3, QTableWidgetItem(str(b.get('Internal_Barcode') or b.get('External_Barcode') or '-')))
            
            qty = float(b.get('Quantity_Current') or 0)
            it_qty = QTableWidgetItem(format_quantity(qty))
            it_qty.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(r, 4, it_qty)

            exp = str(b.get('Expiry_Date') or '-')
            self.table_batches.setItem(r, 5, QTableWidgetItem(exp))

            price_ht = float(b.get('Selling_Price_HT') or b.get('Unit_Price_Received') or 0)
            self.table_batches.setItem(r, 6, QTableWidgetItem(format_money(price_ht)))

            tva = float(b.get('Selling_TVA_Percent') or b.get('Tax_Rate_Percent') or 0)
            self.table_batches.setItem(r, 7, QTableWidgetItem(f"{tva}%"))

        if product_batches:
            self.table_batches.selectRow(0)
        else:
            self.selected_batch = None
            self._check_ready()

    def _on_batch_selected(self):
        row = self.table_batches.currentRow()
        if row < 0:
            self.selected_batch = None
            self._check_ready()
            return

        b_item = self.table_batches.item(row, 0)
        if not b_item:
            return

        self.selected_batch = b_item.data(Qt.UserRole)
        
        # Prefill Price & TVA
        price = float(self.selected_batch.get('Selling_Price_HT') or self.selected_batch.get('Unit_Price_Received') or 0)
        tva = float(self.selected_batch.get('Selling_TVA_Percent') or self.selected_batch.get('Tax_Rate_Percent') or 0)
        self.spin_price.setValue(price)
        self.spin_tva.setValue(tva)

        # Prefill Location
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
        ready = (self.selected_product is not None and self.selected_batch is not None)
        self.btn_submit.setEnabled(ready)

    def _submit_return(self):
        if not self.selected_product or not self.selected_batch:
            QMessageBox.warning(self, "Sélection requise", "Veuillez sélectionner un produit et un lot d'inventaire.")
            return

        reason = self.edit_reason.text().strip()
        if not reason:
            QMessageBox.warning(self, "Motif obligatoire", "Le motif du retour est obligatoire.")
            self.edit_reason.setFocus()
            return

        qty = self.spin_qty.value()
        price_ht = self.spin_price.value()
        tva = self.spin_tva.value()
        refund_method = self.cb_refund.currentData()
        user_id = self._current_user_id()
        dest_loc_id = self.cb_location.currentData()

        reply = QMessageBox.question(
            self, "Confirmation de Retour",
            f"Confirmez-vous le retour de {format_quantity(qty)} unité(s) de '{self.selected_product.get('Product_Name')}' ?\n"
            f"Lot : {self.selected_batch.get('Lot_Number') or 'Sans Lot'} (ID #{self.selected_batch.get('Batch_ID')})\n"
            f"Montant TTC à rembourser : {format_money(qty * price_ht * (1 + tva/100))} DA\n"
            f"Mode de remboursement : {self.cb_refund.currentText()}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        try:
            success, result = self.data_manager.pos_features.create_no_invoice_return(
                product_id=self.selected_product['Product_ID'],
                batch_id=self.selected_batch['Batch_ID'],
                qty_returned=qty,
                unit_price_ht=price_ht,
                tva_percent=tva,
                refund_method=refund_method,
                reason=reason,
                user_id=user_id
            )

            if success:
                # If a different destination location was selected, sync batch location
                if dest_loc_id and dest_loc_id != self.selected_batch.get('Location_ID'):
                    try:
                        self.data_manager.batches.update_batch_location(self.selected_batch['Batch_ID'], dest_loc_id)
                    except Exception as e_loc:
                        logging.warning(f"Could not update batch location after return: {e_loc}")

                QMessageBox.information(
                    self, "Succès",
                    f"Retour sans facture validé avec succès !\n"
                    f"N° de Retour : {result.get('return_no')}\n"
                    f"Stock réintégré dans le lot #{self.selected_batch['Batch_ID']}."
                )
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", result.get('message', "Échec de l'enregistrement du retour."))
        except Exception as e:
            logging.error(f"Exception creating no-invoice return: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors du retour : {e}")
