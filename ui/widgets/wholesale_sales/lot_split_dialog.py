# ui/widgets/wholesale_sales/lot_split_dialog.py

from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QFrame, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut
from ui.formatting import format_money


class MultiLotSelectionDialog(QDialog):
    """
    Dialogue modal de répartition et sélection multi-lots (Multi-Lot / Multi-Location Split Selector).
    Permet à l'opérateur de vente en gros d'allouer rapidement les quantités requises
    sur plusieurs lots / dates de péremption / emplacements en une seule opération ergonomique.
    """

    def __init__(
        self,
        parent,
        product_name: str,
        batches: list,
        requested_qty: float = 1.0,
        price_tier: str = 'Prix_1',
        resolve_price_fn=None
    ):
        super().__init__(parent)
        self.product_name = product_name
        self.batches = list(batches or [])
        self.requested_qty = max(0.01, float(requested_qty))
        self.price_tier = price_tier
        self.resolve_price_fn = resolve_price_fn
        self.spinboxes = []
        self.allocations = []

        self.setWindowTitle("📦 Répartition Multi-Lots & Emplacements - Vente Gros")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.resize(880, 520)
        self.setMinimumSize(780, 420)

        self.init_ui()
        self._auto_allocate_fifo()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # 1. Product Header Card
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 8px 12px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(6, 4, 6, 4)

        v_prod = QVBoxLayout()
        v_prod.setSpacing(2)
        lbl_pname = QLabel(f"Produit : {self.product_name}")
        lbl_pname.setStyleSheet("font-size: 15px; font-weight: bold; color: #007572;")
        total_avail = sum(float(b.get('Quantity_Current') or 0.0) for b in self.batches)
        lbl_sub = QLabel(f"Total disponible en stock (tous lots confondus) : {total_avail:g} unités | {len(self.batches)} lot(s) disponible(s)")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748b;")
        v_prod.addWidget(lbl_pname)
        v_prod.addWidget(lbl_sub)
        h_layout.addLayout(v_prod, 1)

        # Target requested quantity box
        lbl_req = QLabel("Quantité demandée :")
        lbl_req.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e293b;")
        h_layout.addWidget(lbl_req)

        self.spin_target_qty = QDoubleSpinBox()
        self.spin_target_qty.setRange(0.01, 999999.0)
        self.spin_target_qty.setValue(self.requested_qty)
        self.spin_target_qty.setDecimals(2)
        self.spin_target_qty.setMinimumHeight(34)
        self.spin_target_qty.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #ffffff;
                border: 1.5px solid #007572;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                color: #004d40;
                padding: 2px 6px;
            }
        """)
        self.spin_target_qty.valueChanged.connect(self._on_target_qty_changed)
        h_layout.addWidget(self.spin_target_qty)

        btn_fifo = QPushButton("⚡ Répartir (FIFO)")
        btn_fifo.setCursor(Qt.PointingHandCursor)
        btn_fifo.setMinimumHeight(34)
        btn_fifo.setToolTip("Alloue automatiquement la quantité demandée en priorité aux lots les plus anciens (FIFO / Péremption)")
        btn_fifo.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        btn_fifo.clicked.connect(self._auto_allocate_fifo)
        h_layout.addWidget(btn_fifo)

        btn_reset = QPushButton("🔄 Réinitialiser")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setMinimumHeight(34)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_reset.clicked.connect(self._reset_allocations)
        h_layout.addWidget(btn_reset)

        root_layout.addWidget(header_frame)

        # 2. Table of Batches
        self.table = QTableWidget()
        cols = [
            "N° Lot", "Date Péremption", "Emplacement",
            "Stock Disponible", "Prix Unit. HT", "Quantité Allouée"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
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
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self._populate_table()
        root_layout.addWidget(self.table, 1)

        # 3. Real-time Summary Card
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 8px 12px;
            }
        """)
        s_layout = QHBoxLayout(self.summary_frame)
        s_layout.setContentsMargins(6, 4, 6, 4)

        self.lbl_demand = QLabel(f"Demandé : {self.requested_qty:g}")
        self.lbl_demand.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e293b;")

        self.lbl_allocated = QLabel("Alloué : 0.00")
        self.lbl_allocated.setStyleSheet("font-weight: bold; font-size: 13px; color: #0284c7;")

        self.lbl_remaining = QLabel(f"Reste : {self.requested_qty:g}")
        self.lbl_remaining.setStyleSheet("font-weight: bold; font-size: 13px; color: #d97706;")

        s_layout.addWidget(self.lbl_demand)
        s_layout.addWidget(QLabel(" | "))
        s_layout.addWidget(self.lbl_allocated)
        s_layout.addWidget(QLabel(" | "))
        s_layout.addWidget(self.lbl_remaining)
        s_layout.addStretch(1)

        # 4. Action Buttons
        self.btn_cancel = QPushButton("Annuler (Echap)")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("✅ Valider la Répartition (F10 / Enter)")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setMinimumHeight(38)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_confirm.clicked.connect(self._validate_and_accept)

        s_layout.addWidget(self.btn_cancel)
        s_layout.addWidget(self.btn_confirm)

        root_layout.addWidget(self.summary_frame)

        # Shortcuts
        self.shortcut_enter = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.shortcut_enter.activated.connect(self._validate_and_accept)
        self.shortcut_f10 = QShortcut(QKeySequence("F10"), self)
        self.shortcut_f10.activated.connect(self._validate_and_accept)

    def _populate_table(self):
        self.table.setRowCount(0)
        self.spinboxes = []

        for row, batch in enumerate(self.batches):
            self.table.insertRow(row)

            # 0. Lot Number
            item_lot = QTableWidgetItem(str(batch.get('Lot_Number') or '---'))
            item_lot.setTextAlignment(Qt.AlignCenter)
            item_lot.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            self.table.setItem(row, 0, item_lot)

            # 1. Expiry Date
            exp_date = str(batch.get('Expiry_Date') or '---')
            item_exp = QTableWidgetItem(exp_date)
            item_exp.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_exp)

            # 2. Location
            loc_name = str(batch.get('Location_Name') or 'Entrepôt Principal')
            item_loc = QTableWidgetItem(loc_name)
            item_loc.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 2, item_loc)

            # 3. Available stock
            max_stock = float(batch.get('Quantity_Current') or 0.0)
            item_stock = QTableWidgetItem(f"{max_stock:g}")
            item_stock.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_stock.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 3, item_stock)

            # 4. Unit price HT
            if callable(self.resolve_price_fn):
                price = self.resolve_price_fn(batch, self.price_tier)
            else:
                price = float(batch.get('Selling_Price_HT') or 0.0)
            item_price = QTableWidgetItem(f"{format_money(price)} DA")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 4, item_price)

            # 5. Allocated Qty SpinBox
            spin = QDoubleSpinBox()
            spin.setRange(0.0, max_stock)
            spin.setValue(0.0)
            spin.setDecimals(2)
            spin.setAlignment(Qt.AlignCenter)
            spin.setMinimumHeight(32)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: #ffffff;
                    border: 1.5px solid #007572;
                    border-radius: 0px;
                    font-weight: bold;
                    font-size: 13px;
                    color: #004d40;
                    padding: 2px 4px;
                }
                QDoubleSpinBox:focus {
                    background-color: #e6f4f1;
                }
            """)
            spin.valueChanged.connect(self._recalculate_summary)
            self.table.setCellWidget(row, 5, spin)
            self.spinboxes.append((batch, spin))

    def _auto_allocate_fifo(self):
        """Alloue automatiquement la quantité demandée selon le FIFO (péremption la plus proche d'abord)."""
        target = self.spin_target_qty.value()
        remaining = target

        # Sort batches by expiry date (None/empty dates put last)
        sorted_indices = sorted(
            range(len(self.batches)),
            key=lambda idx: str(self.batches[idx].get('Expiry_Date') or '9999-12-31')
        )

        for idx in sorted_indices:
            batch, spin = self.spinboxes[idx]
            max_stock = float(batch.get('Quantity_Current') or 0.0)
            take = min(remaining, max_stock)
            spin.blockSignals(True)
            spin.setValue(take)
            spin.blockSignals(False)
            remaining -= take
            if remaining <= 0:
                remaining = 0

        self._recalculate_summary()

    def _reset_allocations(self):
        for _, spin in self.spinboxes:
            spin.blockSignals(True)
            spin.setValue(0.0)
            spin.blockSignals(False)
        self._recalculate_summary()

    def _on_target_qty_changed(self):
        self.requested_qty = self.spin_target_qty.value()
        self.lbl_demand.setText(f"Demandé : {self.requested_qty:g}")
        self._recalculate_summary()

    def _recalculate_summary(self):
        total_allocated = sum(spin.value() for _, spin in self.spinboxes)
        target = self.spin_target_qty.value()
        remaining = max(0.0, target - total_allocated)

        self.lbl_allocated.setText(f"Alloué : {total_allocated:g}")
        self.lbl_remaining.setText(f"Reste : {remaining:g}")

        if abs(total_allocated - target) < 0.001:
            self.lbl_allocated.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a34a;")
            self.lbl_remaining.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a34a;")
        elif total_allocated < target:
            self.lbl_allocated.setStyleSheet("font-weight: bold; font-size: 13px; color: #d97706;")
            self.lbl_remaining.setStyleSheet("font-weight: bold; font-size: 13px; color: #d97706;")
        else:
            self.lbl_allocated.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")
            self.lbl_remaining.setStyleSheet("font-weight: bold; font-size: 13px; color: #dc2626;")

    def _validate_and_accept(self):
        allocs = []
        for batch, spin in self.spinboxes:
            qty = spin.value()
            if qty > 0:
                allocs.append((batch, qty))

        if not allocs:
            QMessageBox.warning(self, "Quantité Nulle", "Veuillez allouer au moins une quantité sur l'un des lots.")
            return

        total_alloc = sum(qty for _, qty in allocs)
        target = self.spin_target_qty.value()
        if total_alloc < target:
            reply = QMessageBox.question(
                self,
                "Allocation Partielle",
                f"La quantité totale allouée ({total_alloc:g}) est inférieure à la quantité demandée ({target:g}).\n"
                f"Souhaitez-vous quand même valider cette allocation partielle ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.allocations = allocs
        self.accept()

    def get_allocations(self):
        """Retourne la liste des tuples (batch_dict, allocated_qty) confirmés."""
        return self.allocations
