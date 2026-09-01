from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QFrame, QWidget,
                               QApplication, QDoubleSpinBox)
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QEvent, QTimer
from PySide6.QtGui import QKeyEvent, QCursor


class TouchKeypadDialog(QDialog):
    """
    Clavier tactile virtuel flottant agissant exactement comme un clavier physique.
    Ne vole pas le focus (NoFocus) et transmet directement les frappes à l'élément actif.
    Dispose d'une poignée de déplacement ultra-claire et de bords 100% vifs (sharp edges).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pos_tab = parent
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedWidth(330)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 2px solid #007572;
                border-radius: 0px;
            }
        """)

        self._drag_pos = QPoint()
        self.last_target_widget = None

        # Suivre les changements de focus dans l'application pour savoir où envoyer les frappes
        QApplication.instance().focusChanged.connect(self._on_app_focus_changed)

        self.init_ui()

    def _on_app_focus_changed(self, old_widget, new_widget):
        if new_widget and not self.isAncestorOf(new_widget) and new_widget != self:
            self.last_target_widget = new_widget
            self._update_target_indicator()

    def _get_target_widget(self):
        target = QApplication.focusWidget()
        if not target or self.isAncestorOf(target) or target == self:
            target = self.last_target_widget
        if not target and self.pos_tab and hasattr(self.pos_tab, 'cb_product_search'):
            target = self.pos_tab.cb_product_search
        return target

    def _update_target_indicator(self):
        target = self._get_target_widget()
        if not target:
            self.lbl_target.setText("Cible : Aucune (Sélectionnez un champ)")
            return
        
        name = target.objectName() or target.__class__.__name__
        if self.pos_tab:
            if target == self.pos_tab.cb_product_search:
                self.lbl_target.setText("Cible : 🔍 <b>Recherche / Code-barres</b>")
                return
            elif hasattr(self.pos_tab, 'cb_client') and (target == self.pos_tab.cb_client or target == self.pos_tab.cb_client.lineEdit()):
                self.lbl_target.setText("Cible : 👤 <b>Recherche Client</b>")
                return
        
        if isinstance(target.parent(), QDoubleSpinBox) or isinstance(target, QDoubleSpinBox):
            self.lbl_target.setText("Cible : 🔢 <b>Nombre / Quantité / Prix</b>")
            return

        self.lbl_target.setText(f"Cible : <b>{name}</b>")

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # 1. Poignée de déplacement très claire et visible (Large Drag Handle Header)
        self.header_drag = QFrame()
        self.header_drag.setCursor(Qt.SizeAllCursor)
        self.header_drag.setStyleSheet("""
            QFrame {
                background-color: #004d40;
                border: 1px solid #002d26;
                border-radius: 0px;
                padding: 4px;
            }
        """)
        h_layout = QHBoxLayout(self.header_drag)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(6)

        lbl_drag_icon = QLabel("✥ ⣿")
        lbl_drag_icon.setStyleSheet("color: #a7f3d0; font-size: 14px; font-weight: bold;")
        h_layout.addWidget(lbl_drag_icon)

        lbl_drag_title = QLabel("GLISSER POUR DÉPLACER")
        lbl_drag_title.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        h_layout.addWidget(lbl_drag_title, stretch=1)

        btn_close = QPushButton("✕")
        btn_close.setFocusPolicy(Qt.NoFocus)
        btn_close.setFixedSize(26, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Fermer le clavier tactile")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        btn_close.clicked.connect(self.hide)
        h_layout.addWidget(btn_close)
        layout.addWidget(self.header_drag)

        # 2. Indicateur de cible active + Boutons de focus rapide
        self.lbl_target = QLabel("Cible : 🔍 Recherche Produit / Code-Barres")
        self.lbl_target.setStyleSheet("font-size: 11px; color: #007572; background: #e6f4f1; border: 1px solid #b2dfdb; border-radius: 0px; padding: 4px 6px;")
        layout.addWidget(self.lbl_target)

        quick_targets = QHBoxLayout()
        quick_targets.setSpacing(3)
        btn_focus_search = self._make_quick_focus_button("🔍 Code", self.focus_search)
        btn_focus_client = self._make_quick_focus_button("👤 Client", self.focus_client)
        btn_focus_qty = self._make_quick_focus_button("🔢 Qté", self.focus_qty)
        btn_focus_rem = self._make_quick_focus_button("🏷️ Remise", self.focus_remise)

        quick_targets.addWidget(btn_focus_search)
        quick_targets.addWidget(btn_focus_client)
        quick_targets.addWidget(btn_focus_qty)
        quick_targets.addWidget(btn_focus_rem)
        layout.addLayout(quick_targets)

        # 3. Grille des chiffres et touches clavier
        grid = QGridLayout()
        grid.setSpacing(4)

        # Chiffres
        num_keys = [
            ('7', Qt.Key_7, 0, 0), ('8', Qt.Key_8, 0, 1), ('9', Qt.Key_9, 0, 2),
            ('4', Qt.Key_4, 1, 0), ('5', Qt.Key_5, 1, 1), ('6', Qt.Key_6, 1, 2),
            ('1', Qt.Key_1, 2, 0), ('2', Qt.Key_2, 2, 1), ('3', Qt.Key_3, 2, 2),
            ('0', Qt.Key_0, 3, 0), ('00', None, 3, 1),    ('.', Qt.Key_Period, 3, 2),
        ]

        for label, key_code, r, c in num_keys:
            btn = self._make_numpad_button(label)
            if label == '00':
                btn.clicked.connect(self.send_double_zero)
            else:
                btn.clicked.connect(lambda _chk=False, k=key_code, t=label: self.send_key(k, t))
            grid.addWidget(btn, r, c)

        # Colonne de droite : Corrections & Incréments
        btn_back = self._make_action_button("⌫", "#fee2e2", "#991b1b", "#fca5a5")
        btn_back.setToolTip("Effacer le dernier caractère (Backspace)")
        btn_back.clicked.connect(lambda: self.send_key(Qt.Key_Backspace, ""))
        grid.addWidget(btn_back, 0, 3)

        btn_clear = self._make_action_button("C", "#fee2e2", "#991b1b", "#fca5a5")
        btn_clear.setToolTip("Vider le champ sélectionné")
        btn_clear.clicked.connect(self.clear_target)
        grid.addWidget(btn_clear, 1, 3)

        btn_plus1 = self._make_action_button("+1", "#e0f2fe", "#0369a1", "#bae6fd")
        btn_plus1.setToolTip("Ajouter +1 à la quantité")
        btn_plus1.clicked.connect(lambda: self.adjust_active_qty(1.0))
        grid.addWidget(btn_plus1, 2, 3)

        btn_minus1 = self._make_action_button("-1", "#e0f2fe", "#0369a1", "#bae6fd")
        btn_minus1.setToolTip("Retrancher -1 à la quantité")
        btn_minus1.clicked.connect(lambda: self.adjust_active_qty(-1.0))
        grid.addWidget(btn_minus1, 3, 3)

        layout.addLayout(grid)

        # 4. Ligne d'actions inférieures : Suppression de ligne & Entrée
        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(4)

        btn_del_line = QPushButton("🗑️ Suppr. Ligne")
        btn_del_line.setFocusPolicy(Qt.NoFocus)
        btn_del_line.setCursor(Qt.PointingHandCursor)
        btn_del_line.setMinimumHeight(38)
        btn_del_line.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #dc2626;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        btn_del_line.clicked.connect(self.delete_active_cart_row)
        bottom_actions.addWidget(btn_del_line, stretch=1)

        btn_enter = QPushButton("Entrée ⏎")
        btn_enter.setFocusPolicy(Qt.NoFocus)
        btn_enter.setCursor(Qt.PointingHandCursor)
        btn_enter.setMinimumHeight(38)
        btn_enter.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        btn_enter.clicked.connect(lambda: self.send_key(Qt.Key_Return, "\r"))
        bottom_actions.addWidget(btn_enter, stretch=2)

        layout.addLayout(bottom_actions)

    def _make_numpad_button(self, text):
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-size: 17px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border: 1.5px solid #007572;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
        """)
        return btn

    def _make_action_button(self, text, bg, fg, border):
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(44)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
                border: 1.5px solid {fg};
            }}
        """)
        return btn

    def _make_quick_focus_button(self, text, handler):
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(26)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #007572;
                border-color: #007572;
            }
        """)
        btn.clicked.connect(handler)
        return btn

    # Envoi direct d'événements clavier (Exactement comme un clavier physique)
    def send_key(self, key, text=""):
        target = self._get_target_widget()
        if not target:
            return

        # Si la cible est un QDoubleSpinBox, cibler son lineEdit interne
        if isinstance(target, QDoubleSpinBox):
            target = target.lineEdit() or target

        press_ev = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text)
        release_ev = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, text)
        QApplication.sendEvent(target, press_ev)
        QApplication.sendEvent(target, release_ev)
        self._update_target_indicator()

    def send_double_zero(self):
        self.send_key(Qt.Key_0, "0")
        self.send_key(Qt.Key_0, "0")

    def clear_target(self):
        target = self._get_target_widget()
        if not target:
            return
        if hasattr(target, 'clear'):
            target.clear()
        elif hasattr(target, 'setValue'):
            target.setValue(0.0)
        elif isinstance(target, QDoubleSpinBox):
            target.setValue(0.0)

    # Raccourcis de ciblage rapide avec sélection intégrale
    def focus_search(self):
        if self.pos_tab and hasattr(self.pos_tab, 'cb_product_search'):
            w = self.pos_tab.cb_product_search
            w.setFocus()
            QTimer.singleShot(0, w.selectAll)
            self.last_target_widget = w
            self._update_target_indicator()

    def focus_client(self):
        if self.pos_tab and hasattr(self.pos_tab, 'cb_client'):
            w = self.pos_tab.cb_client.lineEdit() or self.pos_tab.cb_client
            w.setFocus()
            QTimer.singleShot(0, w.selectAll)
            self.last_target_widget = w
            self._update_target_indicator()

    def _get_active_row(self):
        if not self.pos_tab or not hasattr(self.pos_tab, 'cart_table'):
            return -1
        table = self.pos_tab.cart_table
        if table.rowCount() == 0:
            return -1
        row = table.currentRow()
        if row < 0:
            row = table.rowCount() - 1
            table.setCurrentCell(row, 1)
        return row

    def focus_qty(self):
        row = self._get_active_row()
        if row >= 0:
            qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
            if qty_spin:
                target = qty_spin.lineEdit() or qty_spin
                target.setFocus()
                QTimer.singleShot(0, target.selectAll)
                self.last_target_widget = target
                self._update_target_indicator()

    def focus_remise(self):
        row = self._get_active_row()
        if row >= 0:
            remise_w = self.pos_tab.cart_table.cellWidget(row, 4)
            if remise_w and hasattr(remise_w, 'value_spin'):
                target = remise_w.value_spin.lineEdit() or remise_w.value_spin
                target.setFocus()
                QTimer.singleShot(0, target.selectAll)
                self.last_target_widget = target
                self._update_target_indicator()

    def adjust_active_qty(self, delta):
        row = self._get_active_row()
        if row >= 0:
            qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
            if qty_spin:
                new_val = max(0.01, min(qty_spin.maximum(), qty_spin.value() + delta))
                qty_spin.setValue(new_val)
                target = qty_spin.lineEdit() or qty_spin
                target.setFocus()
                QTimer.singleShot(0, target.selectAll)
                self.last_target_widget = target
                self._update_target_indicator()

    def delete_active_cart_row(self):
        row = self._get_active_row()
        if row >= 0:
            self.pos_tab.cart_table.removeRow(row)
            self.pos_tab.calculate_totals()
            self._update_target_indicator()

    # Déplacement fluide par glissement
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
        self._update_target_indicator()
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(180)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()
