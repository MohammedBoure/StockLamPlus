# ui/widgets/inventory/dialogs.py

import datetime
from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QComboBox, 
    QSpinBox, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QMessageBox, QFrame, QTableWidget, QTableWidgetItem, 
    QHeaderView, QGroupBox, QAbstractItemView, QCheckBox, QDoubleSpinBox
)
from PySide6.QtCore import QDate, Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont

# استيراد BaseDialog
from ui.widgets.master_data.dialogs import BaseDialog
from ui.formatting import format_money, format_quantity, quantity_to_int

# استيراد LocationTreeComboBox
try:
    from .location_tree_combo import LocationTreeComboBox
except ImportError:
    from PySide6.QtWidgets import QComboBox as LocationTreeComboBox

# ==============================================================================
# Classes Utilitaires (أدوات مساعدة لحقول الإدخال)
# ==============================================================================

class BarcodeLineEdit(QLineEdit):
    """حقل إدخال يعالج أرقام لوحة المفاتيح الفرنسية (AZERTY)"""
    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1", Qt.Key_Eacute: "2", Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4", Qt.Key_ParenLeft: "5", Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7", Qt.Key_Underscore: "8", Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0"
        }
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

class NumericSpinBox(QSpinBox):
    """SpinBox يحدد النص تلقائياً عند التركيز عليه"""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

# ==============================================================================
# 1. Open Pack Dialog
# ==============================================================================
class OpenPackDialog(BaseDialog):
    def __init__(self, batch_data, location_manager, parent=None):
        super().__init__(f"Ouvrir un Nouveau Paquet - {batch_data.get('Product_Name')}", parent)
        self.batch = batch_data
        self.location_manager = location_manager
        
        self.selected_location_id = self.batch.get('Location_ID') 
        self.selected_location_name = self.batch.get('Location_Name', 'Inconnu')
        
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.lbl_batch = QLabel(str(self.batch.get('Lot_Number')))
        self.lbl_expiry = QLabel(str(self.batch.get('Expiry_Date')))
        
        stability_days = self.batch.get('Open_Vial_Stability_Days') or 30
        self.lbl_stability = QLabel(f"{stability_days} jours")
        
        expiry_raw = self.batch.get('Expiry_Date')
        original_expiry = QDate()
        if expiry_raw:
            if isinstance(expiry_raw, (datetime.date, datetime.datetime)):
                original_expiry = QDate(expiry_raw.year, expiry_raw.month, expiry_raw.day)
            elif isinstance(expiry_raw, str):
                try: original_expiry = QDate.fromString(expiry_raw[:10], "yyyy-MM-dd")
                except: pass

        calc_open_expiry = QDate.currentDate().addDays(int(stability_days))
        if original_expiry.isValid() and original_expiry < calc_open_expiry:
            calc_open_expiry = original_expiry
            
        self.lbl_open_expiry = QLabel(calc_open_expiry.toString("yyyy-MM-dd"))
        self.lbl_open_expiry.setStyleSheet("color: blue; font-weight: bold; font-size: 14px;")

        self.qty_spin = QSpinBox()
        max_qty = quantity_to_int(self.batch.get('Quantity_Current', 0))
        if max_qty == 0: max_qty = 1 
        self.qty_spin.setRange(1, max_qty)
        self.qty_spin.setValue(1)
        
        loc_container = QWidget()
        loc_layout = QHBoxLayout(loc_container)
        loc_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loc_display = QLineEdit()
        self.loc_display.setReadOnly(True)
        self.loc_display.setText(self.selected_location_name) 
        self.loc_display.setPlaceholderText("Aucun emplacement sélectionné")
        
        self.btn_select_loc = QPushButton("Choisir...")
        self.btn_select_loc.setFixedWidth(80)
        self.btn_select_loc.clicked.connect(self.open_location_picker)
        
        loc_layout.addWidget(self.loc_display)
        loc_layout.addWidget(self.btn_select_loc)

        layout.addRow("N° de Lot (Lot):", self.lbl_batch)
        layout.addRow("Date d'Expiration Originale:", self.lbl_expiry)
        layout.addRow("Période de Stabilité:", self.lbl_stability)
        layout.addRow("Date d'Expiration Calculée:", self.lbl_open_expiry)
        layout.addRow("----------", QLabel())
        layout.addRow(f"Nombre à ouvrir (Max: {max_qty}):", self.qty_spin)
        layout.addRow("📍 Emplacement d'Utilisation:", loc_container)

    def open_location_picker(self):
        dlg = LocationTreeComboBox(self.location_manager, self)
        if dlg.exec():
            loc_id, loc_name = dlg.get_selected_location()
            if loc_id:
                self.selected_location_id = loc_id
                self.selected_location_name = loc_name
                self.loc_display.setText(loc_name)

    def get_data(self):
        return {
            "Batch_ID": self.batch.get('Batch_ID'),
            "Product_ID": self.batch.get('Product_ID'),
            "Qty_To_Open": self.qty_spin.value(),
            "Current_Location_ID": self.selected_location_id,
            "Calculated_Open_Expiry": self.lbl_open_expiry.text() 
        }

# ==============================================================================
# 2. Consumption Dialog 
# ==============================================================================
class ConsumptionDialog(BaseDialog):
    def __init__(self, container_data, parent=None):
        super().__init__("Enregistrement de Consommation (Test/QC)", parent)
        self.container = container_data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        current_rem = quantity_to_int(self.container.get('Remaining_Usage_Qty', 0))
        unit = self.container.get('Usage_Unit', 'Test')
        
        self.lbl_info = QLabel(f"{self.container.get('Product_Name')} (Lot: {self.container.get('Lot_Number')})")
        
        self.usage_spin = QSpinBox()
        self.usage_spin.setRange(1, max(1, current_rem))
        self.usage_spin.setSuffix(f" {unit}")
        self.usage_spin.setValue(1)
        
        layout.addRow("Produit:", self.lbl_info)
        layout.addRow(f"Quantité Restante ({current_rem} {unit}):", self.usage_spin)

    def get_data(self):
        return {
            "Container_ID": self.container.get('Container_ID'),
            "Qty_Used": self.usage_spin.value()
        }

# ==============================================================================
# 3. Waste Dialog
# ==============================================================================
class WasteDialog(BaseDialog):
    def __init__(self, item_data, reasons_list, source_type='Batch', parent=None):
        super().__init__("Enregistrement de Mise au Rebut (Waste Report)", parent)
        self.item = item_data
        self.reasons = reasons_list
        self.source_type = source_type
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        if self.source_type == 'Batch':
            max_qty = quantity_to_int(self.item.get('Quantity_Current', 0))
            if max_qty == 0: max_qty = quantity_to_int(self.item.get('Current_Stock_Qty', 0))
            unit = "Boîte/Kit"
        else:
            max_qty = quantity_to_int(self.item.get('Remaining_Usage_Qty', 0))
            unit = self.item.get('Usage_Unit', 'Test')

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, max(1, max_qty))
        self.qty_spin.setSuffix(f" {unit}")
        self.qty_spin.setValue(max_qty)
        
        self.reason_combo = QComboBox()
        for r in self.reasons:
            self.reason_combo.addItem(r.get('Reason_Name'), r.get('Reason_ID'))
            
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Notes additionnelles...")
        
        layout.addRow(f"Produit: {self.item.get('Product_Name')}", QLabel())
        layout.addRow(f"Quantité disponible ({max_qty}):", self.qty_spin)
        layout.addRow("Raison de la Mise au Rebut:", self.reason_combo)
        layout.addRow("Notes:", self.notes)

    def get_data(self):
        return {
            "Source_ID": self.item.get('Batch_ID') if self.source_type == 'Batch' else self.item.get('Container_ID'),
            "Source_Type": self.source_type,
            "Qty_Wasted": self.qty_spin.value(),
            "Reason_ID": self.reason_combo.currentData(),
            "Notes": self.notes.text()
        }
    
# ==============================================================================
# 4. Adjustment Dialog
# ==============================================================================
class AdjustmentDialog(BaseDialog):
    def __init__(self, batch_data, reasons_list, parent=None):
        super().__init__(f"Ajustement d'Inventaire (Correction) - {batch_data.get('Product_Name')}", parent)
        self.batch = batch_data
        self.reasons = reasons_list
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        current_qty = quantity_to_int(self.batch.get('Quantity_Current', 0))
        
        self.lbl_current = QLabel(format_quantity(current_qty))
        
        self.spin_new_qty = QSpinBox()
        self.spin_new_qty.setRange(0, 999999)
        self.spin_new_qty.setValue(current_qty)
        
        self.reason_combo = QComboBox()
        for r in self.reasons:
            self.reason_combo.addItem(r.get('Reason_Name'), r.get('Reason_ID'))
            
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Raison de la correction...")
        
        layout.addRow("Quantité Actuelle dans le Système:", self.lbl_current)
        layout.addRow("Quantité Physique (Nouvelle):", self.spin_new_qty)
        layout.addRow("Raison de la Correction:", self.reason_combo)
        layout.addRow("Notes:", self.notes)

    def get_data(self):
        current = quantity_to_int(self.lbl_current.text())
        new_val = self.spin_new_qty.value()
        diff = new_val - current
        
        return {
            "Batch_ID": self.batch.get('Batch_ID'),
            "Qty_Change": diff,
            "Reason_ID": self.reason_combo.currentData(),
            "Notes": self.notes.text()
        }

# ==============================================================================
# 5. Batch Details Dialog
# ==============================================================================
class BatchDetailsDialog(BaseDialog):
    """نافذة عرض تفاصيل المنتج والموقع (للقراءة فقط)"""
    def __init__(self, batch_data, parent=None):
        title = f"Détails du Lot : {batch_data.get('Lot_Number', '---')}"
        super().__init__(title, parent)
        self.batch = batch_data
        self.resize(750, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setSpacing(15)

        def add_row(layout, label_text, value_text, is_bold=False, color=None):
            lbl_key = QLabel(f"<b>{label_text} :</b>")
            lbl_val = QLabel(str(value_text))
            style = "font-size: 14px;"
            if is_bold: style += " font-weight: bold;"
            if color: style += f" color: {color};"
            lbl_val.setStyleSheet(style)
            lbl_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addRow(lbl_key, lbl_val)

        # 1. قسم المعلومات الأساسية
        grp_basic = QGroupBox("📦 Informations Produit")
        grp_basic.setStyleSheet("QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_basic = QFormLayout(grp_basic)
        
        add_row(layout_basic, "Produit", self.batch.get('Product_Name', '---'), True, "#2c3e50")
        add_row(layout_basic, "Marque", self.batch.get('Manuf_Name') or self.batch.get('Brand_Name', '---'))
        add_row(layout_basic, "Code-Barres", self.batch.get('Internal_Barcode') or self.batch.get('Barcode', '---'))
        main_layout.addWidget(grp_basic)

        # 2. قسم المخزون والموقع
        grp_stock = QGroupBox("📍 Stock & Emplacement")
        grp_stock.setStyleSheet("QGroupBox { font-weight: bold; color: #007572; border: 1px solid #007572; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_stock = QFormLayout(grp_stock)

        lbl_loc = QLabel(str(self.batch.get('Location_Name', 'Non défini')))
        lbl_loc.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9; background-color: #eaf2f8; padding: 5px; border-radius: 4px;")
        layout_stock.addRow(QLabel("<b>EMPLACEMENT :</b>"), lbl_loc)

        add_row(layout_stock, "Quantite Actuelle", format_quantity(self.batch.get('Quantity_Current', 0)), True, "#27ae60")
        add_row(layout_stock, "Quantite Initiale", format_quantity(self.batch.get('Quantity_Initial', 0)))
        add_row(layout_stock, "N° Lot", self.batch.get('Lot_Number', '---'), True)
        
        exp_date = str(self.batch.get('Expiry_Date', '---'))
        color_exp = None
        if self.batch.get('Expiry_Date'):
            try:
                ed = datetime.datetime.strptime(exp_date[:10], "%Y-%m-%d").date()
                today = datetime.date.today()
                if ed < today: color_exp = "#c0392b"
                elif (ed - today).days <= 30: color_exp = "#e67e22"
            except: pass
            
        add_row(layout_stock, "Date Expiration", exp_date, True, color_exp)
        add_row(layout_stock, "Date Entrée (Système)", str(self.batch.get('Created_At', '---'))[:16])
        main_layout.addWidget(grp_stock)

        # 3. قسم المعلومات المالية والمراجع
        grp_financial = QGroupBox("💰 Données Financières & Références")
        grp_financial.setStyleSheet("QGroupBox { font-weight: bold; color: #7f8c8d; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_fin = QFormLayout(grp_financial)
        
        price_u = float(self.batch.get('Unit_Price_Received', 0))
        qty_curr = quantity_to_int(self.batch.get('Quantity_Current', 0))
        tva_pct = float(self.batch.get('Tax_Rate_Percent', 0))
        
        tva_amount = price_u * (tva_pct / 100)
        total_val_ttc = (price_u + tva_amount) * qty_curr

        add_row(layout_fin, "Prix Unitaire (HT)", format_money(price_u, 'DA'))
        add_row(layout_fin, "TVA", f"{format_money(tva_amount, 'DA')} ({tva_pct}%)")
        add_row(layout_fin, "Valeur Totale (Stock Actuel)", f"{format_money(total_val_ttc, 'DA')} (TTC)", True, "#2c3e50")

        layout_fin.addRow(QLabel("----------"), QLabel(""))
        add_row(layout_fin, "Réf. Bon de Commande (PO)", self.batch.get('PO_ID', '---'))
        add_row(layout_fin, "Réf. Bon de Réception (BR)", self.batch.get('BR_ID', '---'))
        main_layout.addWidget(grp_financial)

        hbox = QHBoxLayout()
        hbox.addStretch()
        main_layout.addLayout(hbox)

# ==============================================================================
# 6. Inventory Dispatch Dialog (الحل النهائي لمشكلة المسح الضوئي)
# ==============================================================================
class InventoryDispatchDialog(BaseDialog):
    def __init__(self, products_in_stock, location_manager, parent=None):
        super().__init__("Distributeur de Stock (Scan Rapide Auto)", parent)
        self.products = products_in_stock  
        self.location_manager = location_manager
        self.dispatch_data = [] 
        
        # --- المؤقت السحري (The Fix) ---
        self.scan_timer = QTimer()
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.process_scan_buffer)

        self.resize(1200, 700)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self.form_widget)
        layout.setSpacing(15)

        # 1. منطقة المسح الضوئي
        search_frame = QFrame()
        search_frame.setStyleSheet("background: #ecf0f1; border-radius: 8px; padding: 10px;")
        search_layout = QHBoxLayout(search_frame)
        
        self.item_search = BarcodeLineEdit()
        self.item_search.setPlaceholderText("🔴 Scannez le code-barres ici (Entrée Auto)...")
        self.item_search.setMinimumHeight(60)
        self.item_search.setStyleSheet("""
            QLineEdit { 
                font-size: 22px; font-weight: bold; border: 2px solid #bdc3c7; 
                border-radius: 5px; padding-left: 10px; color: #2c3e50; background-color: white;
            }
            QLineEdit:focus { border: 2px solid #27ae60; background-color: #e8f8f5; }
        """)
        
        self.item_search.textChanged.connect(self.on_text_changed)
        
        btn_manual = QPushButton("🔎")
        btn_manual.setFixedWidth(50)
        btn_manual.setMinimumHeight(60)
        btn_manual.clicked.connect(self.process_scan_buffer)

        search_layout.addWidget(QLabel("<b>SCANNER :</b>"))
        search_layout.addWidget(self.item_search, 1)
        search_layout.addWidget(btn_manual)
        
        layout.addWidget(search_frame)

        # 2. الجدول
        self.stack_table = QTableWidget()
        cols = ["Produit", "Code-Barres", "Lot", "Emplacement", "Action", "Destination", "Qté", "Suppr."]
        self.stack_table.setColumnCount(len(cols))
        self.stack_table.setHorizontalHeaderLabels(cols)
        
        header = self.stack_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.stack_table.verticalHeader().setDefaultSectionSize(50)
        self.stack_table.setAlternatingRowColors(True)
        self.stack_table.setStyleSheet("QTableWidget::item { padding: 5px; font-size: 13px; }")
        
        layout.addWidget(self.stack_table)

        # 3. الأزرار السفلية
        btn_layout = QHBoxLayout()
        self.btn_process = QPushButton("🚀 Exécuter les opérations")
        self.btn_process.setMinimumHeight(55)
        self.btn_process.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; border-radius: 8px; }
            QPushButton:hover { background-color: #219150; }
        """)
        self.btn_process.clicked.connect(self.process_all)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_process)
        layout.addLayout(btn_layout)

        QTimer.singleShot(100, self.item_search.setFocus)

    def on_text_changed(self, text):
        if not text: return
        self.scan_timer.start(200)

    def process_scan_buffer(self):
        barcode = self.item_search.text().strip().lower()
        if not barcode: return

        found_batch = None
        
        for b in self.products:
            internal = str(b.get('Internal_Barcode', '')).strip().lower()
            manuf = str(b.get('Barcode', '')).strip().lower()
            lot = str(b.get('Lot_Number', '')).strip().lower()

            if barcode == internal or barcode == manuf:
                found_batch = b
                break
            
            if barcode == lot and found_batch is None:
                found_batch = b
        
        if found_batch:
            self.add_batch_to_table(found_batch)
            self.flash_feedback(True)
            self.item_search.clear()
        else:
            self.flash_feedback(False)
            self.item_search.selectAll()

        self.item_search.setFocus()

    def add_batch_to_table(self, batch):
        for r in range(self.stack_table.rowCount()):
            existing_meta = self.stack_table.item(r, 0).data(Qt.UserRole)
            if existing_meta['Batch_ID'] == batch['Batch_ID']:
                qty_widget = self.stack_table.cellWidget(r, 6)
                curr = qty_widget.value()
                if curr < qty_widget.maximum():
                    qty_widget.setValue(curr + 1)
                    self.stack_table.selectRow(r)
                return

        row = self.stack_table.rowCount()
        self.stack_table.insertRow(row)

        name_item = QTableWidgetItem(f"{batch['Product_Name']}")
        name_item.setData(Qt.UserRole, batch)
        self.stack_table.setItem(row, 0, name_item)
        
        bc_display = batch.get('Internal_Barcode') or batch.get('Barcode') or '---'
        self.stack_table.setItem(row, 1, QTableWidgetItem(str(bc_display)))
        self.stack_table.setItem(row, 2, QTableWidgetItem(str(batch['Lot_Number'])))
        self.stack_table.setItem(row, 3, QTableWidgetItem(batch.get('Location_Name', '---')))

        combo_action = QComboBox()
        combo_action.addItems(["Consommation", "Transfert"])
        self.stack_table.setCellWidget(row, 4, combo_action)

        loc_picker = LocationTreeComboBox(self.location_manager)
        loc_picker.setEnabled(False)
        loc_picker.setStyleSheet("border: none; background: transparent; color: transparent;")
        self.stack_table.setCellWidget(row, 5, loc_picker)

        def toggle_loc(idx):
            is_transfer = (idx == 1)
            loc_picker.setEnabled(is_transfer)
            loc_picker.setStyleSheet("" if is_transfer else "border: none; background: transparent; color: transparent;")
        
        combo_action.currentIndexChanged.connect(toggle_loc)

        spin_qty = NumericSpinBox()
        max_q = quantity_to_int(batch['Quantity_Current'])
        spin_qty.setRange(1, max_q)
        spin_qty.setValue(1)
        self.stack_table.setCellWidget(row, 6, spin_qty)

        btn_del = QPushButton("✖")
        btn_del.setStyleSheet("color: red; border: none; font-weight: bold; font-size: 16px; background: transparent;")
        btn_del.clicked.connect(lambda: self.stack_table.removeRow(self.stack_table.currentRow()))
        self.stack_table.setCellWidget(row, 7, btn_del)

        self.stack_table.scrollToBottom()
        self.stack_table.selectRow(row)

    def flash_feedback(self, success=True):
        color = "#d5f5e3" if success else "#fadbd8"
        orig = self.item_search.styleSheet()
        self.item_search.setStyleSheet(orig + f" background-color: {color};")
        QTimer.singleShot(300, lambda: self.item_search.setStyleSheet(orig))

    def process_all(self):
        if self.stack_table.rowCount() == 0:
            return

        self.dispatch_data = []
        errors = []

        for r in range(self.stack_table.rowCount()):
            meta = self.stack_table.item(r, 0).data(Qt.UserRole)
            action = self.stack_table.cellWidget(r, 4).currentText()
            qty = self.stack_table.cellWidget(r, 6).value()
            
            dest_id = None
            if action == "Transfert":
                dest_id = self.stack_table.cellWidget(r, 5).get_current_location_id()
                if not dest_id:
                    errors.append(f"{meta['Product_Name']}: Destination manquante")
                    continue
            
            self.dispatch_data.append({
                "Batch_ID": meta['Batch_ID'],
                "Action": "Consume" if action == "Consommation" else "Transfer",
                "Qty": qty,
                "Dest_ID": dest_id
            })

        if errors:
            QMessageBox.warning(self, "Erreur", "\n".join(errors))
            return

        self.accept()

# ==============================================================================
# 7. Unpack & Transfer Dialog (Déconditionnement & Transfert en Unité Détail)
# ==============================================================================
class UnpackTransferDialog(BaseDialog):
    """
    Dialogue de déconditionnement d'un lot en sous-unités de détail avec transfert vers un emplacement magasin/rayon.
    Exploite les unités et quantités pré-configurées dans les Données de Base (Produits) tout en laissant à l'utilisateur
    la liberté d'intervenir et de modifier manuellement le ratio de conversion ou les unités.
    """
    def __init__(self, batch_data, location_manager, product_manager=None, batch_manager=None, parent=None):
        prod_name = batch_data.get('Product_Name', 'Produit')
        super().__init__(f"Déconditionnement && Transfert - {prod_name}", parent)
        self.batch = batch_data
        self.location_manager = location_manager
        self.product_manager = product_manager
        self.batch_manager = batch_manager

        # Charger la hiérarchie des unités et facteurs depuis Données de Base
        self.prod_units = self._load_product_units()

        self.resize(680, 780)
        self.setMinimumWidth(640)
        self.init_ui()

    def _load_product_units(self):
        prod_id = self.batch.get('Product_ID')
        p = None
        if self.product_manager and prod_id:
            try:
                p = self.product_manager.get_product_by_id(prod_id)
            except Exception:
                pass

        if not p:
            p = self.batch

        ordering_unit = str(p.get('Ordering_Unit') or 'Carton').strip()
        stock_unit = str(p.get('Stock_Unit') or 'Boîte').strip()

        try:
            stock_qty_per_order = float(p.get('Stock_Qty_Per_Order_Unit') or 1.0)
            if stock_qty_per_order <= 0:
                stock_qty_per_order = 1.0
        except Exception:
            stock_qty_per_order = 1.0

        usage_unit = str(p.get('Usage_Unit') or 'Pièce').strip()
        if not usage_unit or usage_unit.lower() in ('none', 'null'):
            usage_unit = 'Pièce'

        try:
            usage_qty_per_stock = float(p.get('Usage_Qty_Per_Stock_Unit') or 1.0)
            if usage_qty_per_stock <= 0:
                usage_qty_per_stock = 1.0
        except Exception:
            usage_qty_per_stock = 1.0

        return {
            'Ordering_Unit': ordering_unit,
            'Stock_Unit': stock_unit,
            'Stock_Qty_Per_Order_Unit': stock_qty_per_order,
            'Usage_Unit': usage_unit,
            'Usage_Qty_Per_Stock_Unit': usage_qty_per_stock
        }

    def init_ui(self):
        # Appliquer un style ciblé garantissant une hauteur suffisante sans clipping ni double flèches
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                padding-bottom: 8px;
                padding-left: 10px;
                padding-right: 10px;
            }
            QLineEdit, QComboBox {
                min-height: 38px;
                max-height: 38px;
                font-size: 13px;
                padding: 4px 10px;
                border: 1px solid #ced4da;
                border-radius: 5px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1.5px solid #007572;
                background-color: #fcfefe;
            }
            QSpinBox, QDoubleSpinBox {
                min-height: 38px;
                max-height: 38px;
                font-size: 13px;
                padding: 4px 28px 4px 10px;
                border: 1px solid #ced4da;
                border-radius: 5px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #007572;
                background-color: #fcfefe;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 22px;
                height: 18px;
                border-left: 1px solid #ced4da;
                border-bottom: 1px solid #ced4da;
                background: #f8f9fa;
                border-top-right-radius: 5px;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
                background: #e2e6ea;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 22px;
                height: 18px;
                border-left: 1px solid #ced4da;
                background: #f8f9fa;
                border-bottom-right-radius: 5px;
            }
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background: #e2e6ea;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #495057;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #495057;
            }
        """)

        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 8, 12, 8)

        # 1. Carte d'information du lot source
        info_group = QGroupBox("📦 Informations du Lot Source (Parent)")
        info_group.setStyleSheet("QGroupBox { color: #2c3e50; border: 1px solid #bdc3c7; }")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(6)

        self.lbl_prod = QLabel(f"<b>{self.batch.get('Product_Name', '---')}</b>")
        self.lbl_lot = QLabel(f"{self.batch.get('Lot_Number', '---')} (Exp: {str(self.batch.get('Expiry_Date', '---'))[:10]})")
        self.lbl_curr_loc = QLabel(f"📍 {self.batch.get('Location_Name', 'Inconnu')}")

        self.current_source_unit = self.batch.get('Stock_Unit') or self.prod_units['Stock_Unit'] or 'Boîte'
        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        self.lbl_stock_avail = QLabel(f"<b style='color: #27ae60; font-size: 14px;'>{format_quantity(curr_stock)} {self.current_source_unit}</b>")

        info_layout.addRow("Produit :", self.lbl_prod)
        info_layout.addRow("N° de Lot :", self.lbl_lot)
        info_layout.addRow("Emplacement Actuel :", self.lbl_curr_loc)
        info_layout.addRow("Stock Disponible :", self.lbl_stock_avail)
        main_layout.addWidget(info_group)

        # 2. Référentiel Données de Base (Produits)
        master_group = QGroupBox("📋 Configuration Définie dans Produits (Données de Base)")
        master_group.setStyleSheet("QGroupBox { color: #2980b9; border: 1px solid #7fb3d5; background-color: #f4f9fd; }")
        master_layout = QVBoxLayout(master_group)
        master_layout.setSpacing(4)

        ou = self.prod_units['Ordering_Unit']
        su = self.prod_units['Stock_Unit']
        sq = self.prod_units['Stock_Qty_Per_Order_Unit']
        uu = self.prod_units['Usage_Unit']
        uq = self.prod_units['Usage_Qty_Per_Stock_Unit']

        lbl_hierarchy = QLabel(
            f"• <b>Unité Commande :</b> {ou}<br>"
            f"• <b>Unité Stockage :</b> {su} <i>(1 {ou} = {sq:g} {su})</i><br>"
            f"• <b>Unité Détail / Usage :</b> {uu} <i>(1 {su} = {uq:g} {uu})</i>"
        )
        lbl_hierarchy.setStyleSheet("font-size: 12px; color: #2471a3; line-height: 140%;")
        master_layout.addWidget(lbl_hierarchy)
        main_layout.addWidget(master_group)

        # 3. Paramètres de déconditionnement & Intervention Utilisateur
        decond_group = QGroupBox("⚙️ Ordre de Déconditionnement (Intervention && Conversion)")
        decond_group.setStyleSheet("QGroupBox { color: #007572; border: 1px solid #007572; }")
        decond_layout = QFormLayout(decond_group)
        decond_layout.setSpacing(8)

        # Sélecteur de modèle basé sur Master Data
        self.combo_preset = QComboBox()

        # Option 1: vers Usage_Unit
        self.combo_preset.addItem(
            f"🧪 Vers Unité Détail ({uu}) — Défini : 1 {su} = {uq:g} {uu}",
            {"target_unit": uu, "factor": uq, "source_unit": su}
        )

        # Option 2: vers Stock_Unit depuis Ordering_Unit (si distinct)
        if sq > 1 and su.lower() != ou.lower():
            self.combo_preset.addItem(
                f"📦 Vers Unité Stockage ({su}) — Défini : 1 {ou} = {sq:g} {su}",
                {"target_unit": su, "factor": sq, "source_unit": ou}
            )

        # Option 3: Commande directe vers Usage_Unit
        if sq > 1 and uq > 1:
            direct_ratio = sq * uq
            self.combo_preset.addItem(
                f"⚡ Direct Commande ➔ Détail ({uu}) — Défini : 1 {ou} = {direct_ratio:g} {uu}",
                {"target_unit": uu, "factor": direct_ratio, "source_unit": ou}
            )

        # Option 4: Personnalisé
        self.combo_preset.addItem("✏️ Saisie Personnalisée (Libre)", None)

        # Quantité à déconditionner (avec label dynamique pour l'unité source)
        self.lbl_qty_to_unpack = QLabel(f"Quantité à Sortir ({self.current_source_unit}) * :")
        self.lbl_qty_to_unpack.setStyleSheet("font-weight: 500; font-size: 13px; color: #2c3e50;")

        self.spin_qty = QSpinBox()
        max_q = max(1, curr_stock)
        self.spin_qty.setRange(1, max_q)
        self.spin_qty.setValue(1)
        self.spin_qty.setSuffix(f" {self.current_source_unit}")
        self.spin_qty.setStyleSheet("font-weight: bold;")
        self.spin_qty.valueChanged.connect(self._recalculate_preview)

        # Facteur de conversion (Modifiable par l'utilisateur)
        self.spin_factor = QDoubleSpinBox()
        self.spin_factor.setRange(0.01, 1000000.0)
        self.spin_factor.setDecimals(2)
        self.spin_factor.setValue(uq)
        self.spin_factor.setToolTip("Facteur pré-rempli depuis les données du produit, modifiable manuellement.")
        self.spin_factor.valueChanged.connect(self._recalculate_preview)

        # Nom de l'unité détail résultante (Modifiable par l'utilisateur)
        self.inp_target_unit = QLineEdit(uu)
        self.inp_target_unit.setPlaceholderText("Ex: Pièce, Flacon, Sachet, Test, Unité...")
        self.inp_target_unit.textChanged.connect(self._recalculate_preview)

        # Prix de vente unitaire HT (recalculé mais modifiable par l'utilisateur pour le magasin/vente)
        src_selling = float(self.batch.get('Selling_Price_HT', 0.0))
        init_selling_unit = src_selling / uq if uq > 0 else 0.0

        self.spin_selling_price = QDoubleSpinBox()
        self.spin_selling_price.setRange(0.0, 9999999.99)
        self.spin_selling_price.setDecimals(2)
        self.spin_selling_price.setSuffix(" DA HT")
        self.spin_selling_price.setValue(init_selling_unit)
        self.spin_selling_price.setToolTip("Prix de vente unitaire HT pour la vente au détail en magasin.")
        self.spin_selling_price.valueChanged.connect(self._recalculate_preview)

        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)

        decond_layout.addRow("Modèle Préconfiguré :", self.combo_preset)
        decond_layout.addRow(self.lbl_qty_to_unpack, self.spin_qty)
        decond_layout.addRow("Facteur de Conversion (Modifiable) * :", self.spin_factor)
        decond_layout.addRow("Nom Unité Détail (Modifiable) * :", self.inp_target_unit)
        decond_layout.addRow("Prix de Vente Unitaire Détail :", self.spin_selling_price)
        main_layout.addWidget(decond_group)

        # 4. Carte d'aperçu dynamique du résultat
        self.preview_card = QFrame()
        self.preview_card.setStyleSheet("background-color: #e8f8f5; border: 1px solid #a3e4d7; border-radius: 6px; padding: 10px;")
        prev_layout = QVBoxLayout(self.preview_card)
        prev_layout.setSpacing(4)

        self.lbl_result_qty = QLabel()
        self.lbl_result_qty.setStyleSheet("font-size: 13px; font-weight: bold; color: #117a65;")
        self.lbl_result_cost = QLabel()
        self.lbl_result_cost.setStyleSheet("font-size: 12px; color: #16a085;")
        self.lbl_result_remain = QLabel()
        self.lbl_result_remain.setStyleSheet("font-size: 12px; color: #7f8c8d;")

        prev_layout.addWidget(self.lbl_result_qty)
        prev_layout.addWidget(self.lbl_result_cost)
        prev_layout.addWidget(self.lbl_result_remain)
        main_layout.addWidget(self.preview_card)

        # 5. Destination & Options
        dest_group = QGroupBox("📍 Emplacement && Code-Barres")
        dest_group.setStyleSheet("QGroupBox { color: #2c3e50; border: 1px solid #bdc3c7; }")
        dest_layout = QFormLayout(dest_group)
        dest_layout.setSpacing(8)

        self.dest_combo = LocationTreeComboBox(self.location_manager)

        # Code-barres avec bouton Générer inline
        bc_container = QWidget()
        bc_layout = QHBoxLayout(bc_container)
        bc_layout.setContentsMargins(0, 0, 0, 0)
        bc_layout.setSpacing(6)

        self.inp_barcode = QLineEdit()
        self.inp_barcode.setPlaceholderText("Laisser vide pour auto-générer (EAN-13) ou saisir")
        self.inp_barcode.textChanged.connect(self._on_barcode_text_changed)

        self.btn_gen_barcode = QPushButton("⚡ Générer")
        self.btn_gen_barcode.setCursor(Qt.PointingHandCursor)
        self.btn_gen_barcode.setToolTip("Générer un code-barres EAN-13 interne garanti unique")
        self.btn_gen_barcode.setStyleSheet("""
            QPushButton {
                min-height: 38px;
                max-height: 38px;
                padding: 0 14px;
                background-color: #007572;
                color: #ffffff;
                font-weight: bold;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a57;
            }
        """)
        self.btn_gen_barcode.clicked.connect(self._on_generate_barcode)

        bc_layout.addWidget(self.inp_barcode, 1)
        bc_layout.addWidget(self.btn_gen_barcode)

        self.lbl_barcode_status = QLabel("ℹ️ Un code EAN-13 unique sera généré automatiquement si le champ reste vide.")
        self.lbl_barcode_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")

        # Options d'impression
        print_container = QWidget()
        print_layout = QHBoxLayout(print_container)
        print_layout.setContentsMargins(0, 0, 0, 0)
        print_layout.setSpacing(12)

        self.cb_print = QCheckBox("🖨️ Imprimer l'étiquette code-barres après le transfert")
        self.cb_print.setChecked(True)

        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 100)
        self.spin_copies.setValue(1)
        self.spin_copies.setSuffix(" copie(s)")
        self.spin_copies.setToolTip("Nombre d'exemplaires d'étiquettes à imprimer")
        self.spin_copies.setEnabled(self.cb_print.isChecked())
        self.cb_print.toggled.connect(self.spin_copies.setEnabled)

        print_layout.addWidget(self.cb_print)
        print_layout.addWidget(self.spin_copies)
        print_layout.addStretch()

        dest_layout.addRow("Emplacement Destination (Rayon / Magasin) * :", self.dest_combo)
        dest_layout.addRow("Code-Barres Spécifique :", bc_container)
        dest_layout.addRow("", self.lbl_barcode_status)
        dest_layout.addRow("Impression :", print_container)
        main_layout.addWidget(dest_group)

        self._recalculate_preview()

    def _on_generate_barcode(self):
        new_bc = None
        if self.batch_manager and hasattr(self.batch_manager, 'generate_unique_barcode'):
            try:
                new_bc = self.batch_manager.generate_unique_barcode()
            except Exception as e:
                logging.error(f"Error generating unique barcode: {e}")

        if not new_bc:
            # Algorithme local EAN-13 de secours
            import time
            base = "200" + str(int(time.time()))[-9:]
            odds = sum(int(base[i]) for i in range(0, 12, 2))
            evens = sum(int(base[i]) for i in range(1, 12, 2))
            check = (10 - ((odds + (evens * 3)) % 10)) % 10
            new_bc = base + str(check)

        self.inp_barcode.setText(new_bc)

    def _on_barcode_text_changed(self, text):
        clean_code = text.strip()
        if not clean_code:
            self.lbl_barcode_status.setText("ℹ️ Un code EAN-13 unique sera généré automatiquement si le champ reste vide.")
            self.lbl_barcode_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            return

        if self.batch_manager and hasattr(self.batch_manager, 'is_barcode_available'):
            try:
                is_avail, err = self.batch_manager.is_barcode_available(clean_code)
                if is_avail:
                    self.lbl_barcode_status.setText("✅ Code-barres valide et disponible.")
                    self.lbl_barcode_status.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
                else:
                    self.lbl_barcode_status.setText(f"❌ {err}")
                    self.lbl_barcode_status.setStyleSheet("color: #c0392b; font-size: 11px; font-weight: bold;")
            except Exception as e:
                self.lbl_barcode_status.setText(f"⚠️ Erreur de validation: {e}")
                self.lbl_barcode_status.setStyleSheet("color: #e67e22; font-size: 11px;")

    def _on_preset_changed(self, index):
        data = self.combo_preset.currentData()
        if data:
            target_unit = data.get('target_unit', 'Pièce')
            factor = float(data.get('factor', 1.0))
            source_unit = data.get('source_unit', self.current_source_unit)

            self.current_source_unit = source_unit
            self.lbl_qty_to_unpack.setText(f"Quantité à Sortir ({source_unit}) * :")
            self.inp_target_unit.setText(target_unit)
            self.spin_factor.setValue(factor)
            self.spin_qty.setSuffix(f" {source_unit}")

            # Recalculer le prix de vente unitaire conseillé
            src_selling = float(self.batch.get('Selling_Price_HT', 0.0))
            if src_selling > 0 and factor > 0:
                self.spin_selling_price.setValue(round(src_selling / factor, 2))

            self._recalculate_preview()

    def _recalculate_preview(self):
        qty_src = self.spin_qty.value()
        factor = self.spin_factor.value()
        unit_tgt = self.inp_target_unit.text().strip() or "Unité"
        src_unit = self.current_source_unit

        target_total_qty = int(qty_src * factor)

        unit_price_src = float(self.batch.get('Unit_Price_Received', 0.0))
        target_unit_cost = unit_price_src / factor if factor > 0 else 0.0

        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        remaining = max(0, curr_stock - qty_src)

        selling_u = self.spin_selling_price.value()

        self.lbl_result_qty.setText(f"🎯 <b>Nouveau Stock Détail :</b> {format_quantity(target_total_qty)} {unit_tgt} <i>(depuis {format_quantity(qty_src)} {src_unit})</i>")
        self.lbl_result_cost.setText(f"💰 <b>Coût Achat Unitaire :</b> {format_money(target_unit_cost, 'DA')} / {unit_tgt} &nbsp;|&nbsp; 🏷️ <b>Prix Vente HT :</b> {format_money(selling_u, 'DA')}")
        self.lbl_result_remain.setText(f"📦 <b>Stock Restant Lot Parent :</b> {format_quantity(remaining)} {src_unit}")

    def accept(self):
        # 1. Validation de la quantité
        qty_to_unpack = self.spin_qty.value()
        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        if qty_to_unpack <= 0:
            QMessageBox.warning(self, "Validation", "La quantité à déconditionner doit être supérieure à zéro.")
            return
        if qty_to_unpack > curr_stock:
            QMessageBox.warning(self, "Validation", f"Stock insuffisant : {curr_stock} {self.current_source_unit} disponible(s).")
            return

        # 2. Validation du facteur de conversion
        if self.spin_factor.value() <= 0:
            QMessageBox.warning(self, "Validation", "Le facteur de conversion doit être strictement supérieur à zéro.")
            return

        # 3. Validation de l'unité cible
        unit_tgt = self.inp_target_unit.text().strip()
        if not unit_tgt:
            QMessageBox.warning(self, "Validation", "Veuillez renseigner le nom de l'unité de détail.")
            self.inp_target_unit.setFocus()
            return

        # 4. Validation de la destination
        dest_id = self.dest_combo.get_current_location_id()
        if not dest_id:
            QMessageBox.warning(self, "Validation", "Veuillez sélectionner un emplacement de destination valide.")
            return

        # 5. Validation du code-barres spécifique
        custom_bc = self.inp_barcode.text().strip()
        if custom_bc and self.batch_manager and hasattr(self.batch_manager, 'is_barcode_available'):
            is_avail, err = self.batch_manager.is_barcode_available(custom_bc)
            if not is_avail:
                QMessageBox.warning(self, "Code-Barres Indisponible", f"Impossible d'utiliser ce code-barres :<br><br>{err}")
                self.inp_barcode.setFocus()
                return

        super().accept()

    def get_data(self):
        return {
            'qty_to_unpack': self.spin_qty.value(),
            'conversion_factor': float(self.spin_factor.value()),
            'source_unit': self.current_source_unit,
            'target_unit': self.inp_target_unit.text().strip() or "Unité",
            'selling_price_ht': self.spin_selling_price.value(),
            'dest_id': self.dest_combo.get_current_location_id(),
            'custom_barcode': self.inp_barcode.text().strip() or None,
            'print_label': self.cb_print.isChecked(),
            'print_copies': self.spin_copies.value()
        }
