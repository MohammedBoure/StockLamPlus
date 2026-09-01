from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QFrame, QWidget,
                               QApplication, QMessageBox)
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QKeyEvent
from ui.formatting import format_money


class TouchKeypadDialog(QDialog):
    """
    Dialogue animé de pavé tactile numérique et fonctions POS,
    entièrement déplaçable (touch/mouse draggable) et superposé à l'interface.
    Coins 100% vifs (sharp edges, sans arrondis).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pos_tab = parent
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFixedWidth(340)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 2px solid #007572;
                border-radius: 0px;
            }
        """)

        self.current_value = ""
        self._drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Header déplaçable avec titre et bouton fermer
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #007572;
                border-radius: 0px;
                padding: 4px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(6, 2, 6, 2)
        h_layout.setSpacing(6)

        lbl_drag = QLabel("✥ <b>PAVÉ TACTILE</b> (Glisser pour déplacer)")
        lbl_drag.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        h_layout.addWidget(lbl_drag, stretch=1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_close.clicked.connect(self.hide)
        h_layout.addWidget(btn_close)
        layout.addWidget(header)

        # 2. Écran d'affichage du montant / chiffre saisi
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight)
        self.display.setPlaceholderText("0")
        self.display.setStyleSheet("""
            QLineEdit {
                background-color: #f8fafc;
                color: #007572;
                border: 1.5px solid #cbd5e1;
                border-radius: 0px;
                font-size: 22px;
                font-weight: 800;
                padding: 6px 10px;
                min-height: 40px;
            }
        """)
        layout.addWidget(self.display)

        # 3. Grille des chiffres et opérations rapides
        grid = QGridLayout()
        grid.setSpacing(5)

        # Boutons numériques
        num_keys = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 0), ('00', 3, 1), ('.', 3, 2),
        ]

        for text, r, c in num_keys:
            btn = self._make_key_button(text, "#ffffff", "#2c3e50", "#e2e8f0")
            btn.clicked.connect(lambda _chk=False, ch=text: self.append_char(ch))
            grid.addWidget(btn, r, c)

        # Colonne Opérations & Corrections (Colonne 3)
        btn_back = self._make_key_button("⌫", "#fee2e2", "#c0392b", "#fca5a5")
        btn_back.clicked.connect(self.backspace)
        grid.addWidget(btn_back, 0, 3)

        btn_clear = self._make_key_button("C", "#fee2e2", "#c0392b", "#fca5a5")
        btn_clear.clicked.connect(self.clear_input)
        grid.addWidget(btn_clear, 1, 3)

        btn_plus1 = self._make_key_button("+1", "#e0f2fe", "#0369a1", "#bae6fd")
        btn_plus1.setToolTip("Incrémenter la quantité de la ligne active (+1)")
        btn_plus1.clicked.connect(lambda: self.adjust_active_qty(1.0))
        grid.addWidget(btn_plus1, 2, 3)

        btn_minus1 = self._make_key_button("-1", "#e0f2fe", "#0369a1", "#bae6fd")
        btn_minus1.setToolTip("Décrémenter la quantité de la ligne active (-1)")
        btn_minus1.clicked.connect(lambda: self.adjust_active_qty(-1.0))
        grid.addWidget(btn_minus1, 3, 3)

        layout.addLayout(grid)

        # 4. Ligne d'affectation aux champs du panier
        action_layout = QHBoxLayout()
        action_layout.setSpacing(4)

        self.btn_apply_qty = self._make_action_button("Qté", "#007572", "#ffffff")
        self.btn_apply_qty.setToolTip("Affecter le chiffre à la Quantité de la ligne sélectionnée")
        self.btn_apply_qty.clicked.connect(self.apply_to_quantity)
        action_layout.addWidget(self.btn_apply_qty)

        self.btn_apply_remise = self._make_action_button("Remise", "#d97706", "#ffffff")
        self.btn_apply_remise.setToolTip("Affecter le chiffre à la Remise de la ligne sélectionnée")
        self.btn_apply_remise.clicked.connect(self.apply_to_discount)
        action_layout.addWidget(self.btn_apply_remise)

        self.btn_del_line = self._make_action_button("🗑️ Suppr", "#dc2626", "#ffffff")
        self.btn_del_line.setToolTip("Supprimer la ligne active du panier")
        self.btn_del_line.clicked.connect(self.delete_active_row)
        action_layout.addWidget(self.btn_del_line)

        self.btn_enter = self._make_action_button("Entrée ⏎", "#16a34a", "#ffffff")
        self.btn_enter.setToolTip("Valider la saisie ou envoyer Entrée au champ de recherche")
        self.btn_enter.clicked.connect(self.press_enter)
        action_layout.addWidget(self.btn_enter)

        layout.addLayout(action_layout)

    def _make_key_button(self, text, bg, fg, border):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(44)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 0px;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: #007572;
            }}
            QPushButton:pressed {{
                background-color: #cbd5e1;
            }}
        """)
        return btn

    def _make_action_button(self, text, bg, fg):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(38)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 6px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
                border: 1px solid #ffffff;
            }}
        """)
        return btn

    # Saisie tactile
    def append_char(self, ch):
        if ch == "." and "." in self.current_value:
            return
        if len(self.current_value) >= 12:
            return
        self.current_value += ch
        self.display.setText(self.current_value)

    def backspace(self):
        self.current_value = self.current_value[:-1]
        self.display.setText(self.current_value)

    def clear_input(self):
        self.current_value = ""
        self.display.setText("")

    def get_parsed_value(self):
        try:
            return float(self.current_value or 0.0)
        except ValueError:
            return 0.0

    def _get_active_row(self):
        if not self.pos_tab or not hasattr(self.pos_tab, 'cart_table'):
            return -1
        table = self.pos_tab.cart_table
        if table.rowCount() == 0:
            return -1
        row = table.currentRow()
        if row < 0 or row >= table.rowCount():
            row = table.rowCount() - 1
            table.setCurrentCell(row, 1)
        return row

    def apply_to_quantity(self):
        row = self._get_active_row()
        if row < 0:
            return
        val = self.get_parsed_value()
        if val <= 0:
            return
        qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
        if qty_spin:
            qty_spin.setValue(min(qty_spin.maximum(), val))
        self.clear_input()

    def apply_to_discount(self):
        row = self._get_active_row()
        if row < 0:
            return
        val = self.get_parsed_value()
        remise_widget = self.pos_tab.cart_table.cellWidget(row, 4)
        if remise_widget and hasattr(remise_widget, 'value_spin'):
            remise_widget.value_spin.setValue(val)
        self.clear_input()

    def adjust_active_qty(self, delta):
        row = self._get_active_row()
        if row < 0:
            return
        qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
        if qty_spin:
            new_val = max(0.01, min(qty_spin.maximum(), qty_spin.value() + delta))
            qty_spin.setValue(new_val)

    def delete_active_row(self):
        row = self._get_active_row()
        if row < 0:
            return
        self.pos_tab.cart_table.removeRow(row)
        self.pos_tab.calculate_totals()

    def press_enter(self):
        if self.current_value and self.pos_tab and hasattr(self.pos_tab, 'cb_product_search'):
            # Si une saisie de code-barre est présente, l'injecter dans la recherche
            self.pos_tab.cb_product_search.setText(self.current_value)
            self.pos_tab.handle_search_return()
            self.clear_input()
        elif self.pos_tab:
            # Sinon appliquer à la quantité par défaut
            self.apply_to_quantity()

    # Déplacement fluide tactile / souris
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    # Animation d'apparition
    def show_animated(self, target_pos=None):
        if target_pos:
            self.move(target_pos)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()
