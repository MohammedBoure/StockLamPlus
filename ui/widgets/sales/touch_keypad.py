from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QFrame, QWidget,
                               QApplication, QDoubleSpinBox, QStackedWidget,
                               QTextEdit, QAbstractSpinBox, QComboBox)
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QEvent, QTimer
from PySide6.QtGui import QKeyEvent, QCursor


def is_widget_valid(w):
    """Vérifie si un objet Qt existe encore en mémoire C++ et n'a pas été détruit."""
    if w is None:
        return False
    try:
        import shiboken6
        if not shiboken6.isValid(w):
            return False
    except Exception:
        pass
    try:
        w.objectName()
        return True
    except RuntimeError:
        return False


def is_input_widget(w):
    """Vérifie si le widget est un vrai champ de saisie de texte ou de nombre (exclut les boutons)."""
    if not is_widget_valid(w):
        return False
    if isinstance(w, (QLineEdit, QTextEdit, QAbstractSpinBox)):
        return True
    if isinstance(w, QComboBox) and w.isEditable():
        return True
    return False


class TouchKeypadDialog(QDialog):
    """
    Clavier tactile virtuel bi-mode (Numérique 🔢 et Alphabétique 🔤).
    - Agit exactement comme un clavier physique : ne vole jamais le focus (NoFocus).
    - Transmet directement les frappes de lettres et de chiffres à l'élément actif.
    - Poignée de déplacement ultra-claire et bords 100% vifs (sharp edges).
    - Basculement instantané entre clavier Chiffres et clavier Lettres (AZERTY/QWERTY).
    - Adapté aux petits et grands écrans tactiles.
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
        self.caps_lock = True
        self.keyboard_layout_mode = "AZERTY"  # "AZERTY" ou "QWERTY"
        self.letter_buttons = []

        # Suivre les changements de focus dans l'application pour savoir où envoyer les frappes
        QApplication.instance().focusChanged.connect(self._on_app_focus_changed)

        self.init_ui()

    def _on_app_focus_changed(self, old_widget, new_widget):
        try:
            # Ne capturer que les vrais champs de texte/nombres (ignorer QPushButton)
            if is_input_widget(new_widget) and not self.isAncestorOf(new_widget) and new_widget != self:
                self.last_target_widget = new_widget
                self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None

    def _get_target_widget(self):
        target = QApplication.focusWidget()
        if not is_input_widget(target) or self.isAncestorOf(target) or target == self:
            target = self.last_target_widget

        if not is_widget_valid(target):
            self.last_target_widget = None
            target = None

        if not target and self.pos_tab and hasattr(self.pos_tab, 'cb_product_search'):
            if is_widget_valid(self.pos_tab.cb_product_search):
                target = self.pos_tab.cb_product_search

        return target if is_widget_valid(target) else None

    def _update_target_indicator(self):
        try:
            target = self._get_target_widget()
            if not is_widget_valid(target):
                self.lbl_target.setText("Cible : 🔍 <b>Recherche / Code-barres</b>")
                return

            if self.pos_tab:
                if target == self.pos_tab.cb_product_search:
                    self.lbl_target.setText("Cible : 🔍 <b>Recherche / Code-barres</b>")
                    return
                elif hasattr(self.pos_tab, 'cb_client') and (
                    target == self.pos_tab.cb_client or target == self.pos_tab.cb_client.lineEdit()
                ):
                    self.lbl_target.setText("Cible : 👤 <b>Recherche Client</b>")
                    return

            parent = target.parent() if hasattr(target, 'parent') else None
            if (parent and isinstance(parent, QDoubleSpinBox)) or isinstance(target, QDoubleSpinBox):
                self.lbl_target.setText("Cible : 🔢 <b>Nombre / Quantité / Prix</b>")
                return

            name = target.objectName() or target.__class__.__name__
            self.lbl_target.setText(f"Cible : <b>{name}</b>")
        except (RuntimeError, AttributeError):
            self.last_target_widget = None
            self.lbl_target.setText("Cible : 🔍 <b>Recherche / Code-barres</b>")

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(5)

        # 1. Poignée de déplacement très claire et visible (Large Drag Handle Header)
        self.header_drag = QFrame()
        self.header_drag.setCursor(Qt.SizeAllCursor)
        self.header_drag.setStyleSheet("""
            QFrame {
                background-color: #004d40;
                border: 1px solid #002d26;
                border-radius: 0px;
                padding: 3px;
            }
        """)
        h_layout = QHBoxLayout(self.header_drag)
        h_layout.setContentsMargins(6, 3, 6, 3)
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
        btn_close.setToolTip("Fermer le clavier")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                font-weight: 900;
                font-size: 14px;
                font-family: Arial, sans-serif;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        btn_close.clicked.connect(self.hide)
        h_layout.addWidget(btn_close)
        self.main_layout.addWidget(self.header_drag)

        # 2. Indicateur de cible active + Boutons de focus rapide
        self.lbl_target = QLabel("Cible : 🔍 Recherche Produit / Code-Barres")
        self.lbl_target.setStyleSheet("font-size: 11px; color: #007572; background: #e6f4f1; border: 1px solid #b2dfdb; border-radius: 0px; padding: 3px 6px;")
        self.main_layout.addWidget(self.lbl_target)

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
        self.main_layout.addLayout(quick_targets)

        # 3. Stacked Widget (Page 0 = Pavé Chiffres, Page 1 = Clavier Lettres)
        self.stacked_pages = QStackedWidget()
        self.page_numpad = self._build_numpad_page()
        self.page_letters = self._build_letters_page()

        self.stacked_pages.addWidget(self.page_numpad)
        self.stacked_pages.addWidget(self.page_letters)
        self.main_layout.addWidget(self.stacked_pages)

    # --------------------------------------------------------------------------
    # PAGE 1 : PAVÉ NUMÉRIQUE (NUMPAD)
    # --------------------------------------------------------------------------
    def _build_numpad_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(4)

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

        # Colonne droite du pavé
        btn_back = self._make_action_button("⌫", "#fee2e2", "#991b1b", "#fca5a5")
        btn_back.setToolTip("Effacer (Backspace)")
        btn_back.clicked.connect(lambda: self.send_key(Qt.Key_Backspace, ""))
        grid.addWidget(btn_back, 0, 3)

        btn_clear = self._make_action_button("C", "#fee2e2", "#991b1b", "#fca5a5")
        btn_clear.setToolTip("Vider le champ")
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

        vbox.addLayout(grid)

        # Ligne inférieure Numpad : Bascule Lettres + Suppr + Entrée
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        btn_to_letters = QPushButton("🔤 ABC")
        btn_to_letters.setFocusPolicy(Qt.NoFocus)
        btn_to_letters.setCursor(Qt.PointingHandCursor)
        btn_to_letters.setMinimumHeight(40)
        btn_to_letters.setToolTip("Passer au clavier de lettres alphabétique")
        btn_to_letters.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1.5px solid #93c5fd;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #dbeafe; }
        """)
        btn_to_letters.clicked.connect(self.switch_to_letters)
        bottom_row.addWidget(btn_to_letters, stretch=1)

        btn_del_line = QPushButton("🗑️ Suppr")
        btn_del_line.setFocusPolicy(Qt.NoFocus)
        btn_del_line.setCursor(Qt.PointingHandCursor)
        btn_del_line.setMinimumHeight(40)
        btn_del_line.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #dc2626;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        btn_del_line.clicked.connect(self.delete_active_cart_row)
        bottom_row.addWidget(btn_del_line, stretch=1)

        btn_enter = QPushButton("Entrée ⏎")
        btn_enter.setFocusPolicy(Qt.NoFocus)
        btn_enter.setCursor(Qt.PointingHandCursor)
        btn_enter.setMinimumHeight(40)
        btn_enter.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                padding: 2px;
            }
            QPushButton:hover { background-color: #005a57; }
        """)
        btn_enter.clicked.connect(lambda: self.send_key(Qt.Key_Return, "\r"))
        bottom_row.addWidget(btn_enter, stretch=2)

        vbox.addLayout(bottom_row)
        return page

    # --------------------------------------------------------------------------
    # PAGE 2 : CLAVIER DE LETTRES (ALPHABÉTIQUE VIRTUAL KEYBOARD)
    # --------------------------------------------------------------------------
    def _build_letters_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Ligne de contrôle : Mode Clavier (AZERTY/QWERTY) + Retour Chiffres
        top_ctrl = QHBoxLayout()
        top_ctrl.setSpacing(4)

        self.btn_layout_toggle = QPushButton("AZERTY")
        self.btn_layout_toggle.setFocusPolicy(Qt.NoFocus)
        self.btn_layout_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_layout_toggle.setFixedSize(70, 26)
        self.btn_layout_toggle.setToolTip("Basculer entre disposition AZERTY et QWERTY")
        self.btn_layout_toggle.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #007572; }
        """)
        self.btn_layout_toggle.clicked.connect(self.toggle_azerty_qwerty)
        top_ctrl.addWidget(self.btn_layout_toggle)

        lbl_info = QLabel("Clavier Tactile Alphabétique")
        lbl_info.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        top_ctrl.addWidget(lbl_info, stretch=1)

        btn_to_numpad_top = QPushButton("🔢 Chiffres")
        btn_to_numpad_top.setFocusPolicy(Qt.NoFocus)
        btn_to_numpad_top.setCursor(Qt.PointingHandCursor)
        btn_to_numpad_top.setFixedHeight(26)
        btn_to_numpad_top.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
                padding: 0px 8px;
            }
            QPushButton:hover { background-color: #dbeafe; }
        """)
        btn_to_numpad_top.clicked.connect(self.switch_to_numpad)
        top_ctrl.addWidget(btn_to_numpad_top)

        vbox.addLayout(top_ctrl)

        # Grille des touches alphabétiques
        self.letters_layout = QVBoxLayout()
        self.letters_layout.setSpacing(3)
        vbox.addLayout(self.letters_layout)
        self._render_letter_rows()

        # Rangée inférieure du clavier alphabétique (Espace, Ponctuation, Entrée)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        btn_to_numpad_bottom = QPushButton("🔢 123")
        btn_to_numpad_bottom.setFocusPolicy(Qt.NoFocus)
        btn_to_numpad_bottom.setCursor(Qt.PointingHandCursor)
        btn_to_numpad_bottom.setMinimumHeight(40)
        btn_to_numpad_bottom.setMinimumWidth(65)
        btn_to_numpad_bottom.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1.5px solid #93c5fd;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #dbeafe; }
        """)
        btn_to_numpad_bottom.clicked.connect(self.switch_to_numpad)
        bottom_row.addWidget(btn_to_numpad_bottom)

        for sym in [".", "-", "_", "/"]:
            btn_sym = self._make_letter_button(sym, width=32)
            btn_sym.clicked.connect(lambda _chk=False, s=sym: self.send_key(0, s))
            bottom_row.addWidget(btn_sym)

        btn_space = QPushButton("ESPACE ␣")
        btn_space.setFocusPolicy(Qt.NoFocus)
        btn_space.setCursor(Qt.PointingHandCursor)
        btn_space.setMinimumHeight(40)
        btn_space.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #007572;
            }
        """)
        btn_space.clicked.connect(lambda: self.send_key(Qt.Key_Space, " "))
        bottom_row.addWidget(btn_space, stretch=3)

        btn_enter_letters = QPushButton("Entrée ⏎")
        btn_enter_letters.setFocusPolicy(Qt.NoFocus)
        btn_enter_letters.setCursor(Qt.PointingHandCursor)
        btn_enter_letters.setMinimumHeight(40)
        btn_enter_letters.setMinimumWidth(80)
        btn_enter_letters.setStyleSheet("""
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
        btn_enter_letters.clicked.connect(lambda: self.send_key(Qt.Key_Return, "\r"))
        bottom_row.addWidget(btn_enter_letters)

        vbox.addLayout(bottom_row)
        return page

    def _render_letter_rows(self):
        # Vider les anciennes rangées
        while self.letters_layout.count():
            item = self.letters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Vider sous-layout
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()

        self.letter_buttons.clear()

        if self.keyboard_layout_mode == "AZERTY":
            row1 = ["A", "Z", "E", "R", "T", "Y", "U", "I", "O", "P"]
            row2 = ["Q", "S", "D", "F", "G", "H", "J", "K", "L", "M"]
            row3 = ["W", "X", "C", "V", "B", "N", "'", "@"]
        else:
            row1 = ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"]
            row2 = ["A", "S", "D", "F", "G", "H", "J", "K", "L", ";"]
            row3 = ["Z", "X", "C", "V", "B", "N", "M", "'"]

        # Rangée 1
        h1 = QHBoxLayout()
        h1.setSpacing(3)
        for char in row1:
            btn = self._make_letter_button(char if self.caps_lock else char.lower())
            btn.clicked.connect(lambda _chk=False, b=btn: self._on_letter_clicked(b))
            self.letter_buttons.append((btn, char))
            h1.addWidget(btn)
        self.letters_layout.addLayout(h1)

        # Rangée 2
        h2 = QHBoxLayout()
        h2.setSpacing(3)
        for char in row2:
            btn = self._make_letter_button(char if self.caps_lock else char.lower())
            btn.clicked.connect(lambda _chk=False, b=btn: self._on_letter_clicked(b))
            self.letter_buttons.append((btn, char))
            h2.addWidget(btn)
        self.letters_layout.addLayout(h2)

        # Rangée 3 : [ ⇧ Maj ] + Lettres + [ ⌫ ]
        h3 = QHBoxLayout()
        h3.setSpacing(3)

        btn_shift = QPushButton("⇧ Maj")
        btn_shift.setFocusPolicy(Qt.NoFocus)
        btn_shift.setCursor(Qt.PointingHandCursor)
        btn_shift.setMinimumHeight(40)
        btn_shift.setMinimumWidth(56)
        shift_bg = "#007572" if self.caps_lock else "#f1f5f9"
        shift_fg = "#ffffff" if self.caps_lock else "#334155"
        btn_shift.setStyleSheet(f"""
            QPushButton {{
                background-color: {shift_bg};
                color: {shift_fg};
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        btn_shift.clicked.connect(self.toggle_caps_lock)
        h3.addWidget(btn_shift)

        for char in row3:
            btn = self._make_letter_button(char if self.caps_lock else char.lower())
            btn.clicked.connect(lambda _chk=False, b=btn: self._on_letter_clicked(b))
            self.letter_buttons.append((btn, char))
            h3.addWidget(btn)

        btn_back = QPushButton("⌫")
        btn_back.setFocusPolicy(Qt.NoFocus)
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setMinimumHeight(40)
        btn_back.setMinimumWidth(56)
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #991b1b;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        btn_back.clicked.connect(lambda: self.send_key(Qt.Key_Backspace, ""))
        h3.addWidget(btn_back)

        self.letters_layout.addLayout(h3)

    def _on_letter_clicked(self, btn):
        text = btn.text()
        self.send_key(0, text)

    def toggle_caps_lock(self):
        self.caps_lock = not self.caps_lock
        self._render_letter_rows()

    def toggle_azerty_qwerty(self):
        if self.keyboard_layout_mode == "AZERTY":
            self.keyboard_layout_mode = "QWERTY"
        else:
            self.keyboard_layout_mode = "AZERTY"
        self.btn_layout_toggle.setText(self.keyboard_layout_mode)
        self._render_letter_rows()

    def switch_to_letters(self):
        self.stacked_pages.setCurrentIndex(1)
        self.setFixedWidth(520)
        self._update_target_indicator()

    def switch_to_numpad(self):
        self.stacked_pages.setCurrentIndex(0)
        self.setFixedWidth(330)
        self._update_target_indicator()

    def _make_letter_button(self, char, width=None):
        btn = QPushButton(char)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(40)
        if width:
            btn.setFixedWidth(width)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-size: 15px;
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
        try:
            target = self._get_target_widget()
            if not is_widget_valid(target):
                return

            if isinstance(target, QDoubleSpinBox):
                target = target.lineEdit() or target

            if not is_widget_valid(target):
                return

            press_ev = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text)
            release_ev = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, text)
            QApplication.sendEvent(target, press_ev)
            QApplication.sendEvent(target, release_ev)
            self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None
            self._update_target_indicator()

    def send_double_zero(self):
        self.send_key(Qt.Key_0, "0")
        self.send_key(Qt.Key_0, "0")

    def clear_target(self):
        try:
            target = self._get_target_widget()
            if not is_widget_valid(target):
                return
            if hasattr(target, 'clear'):
                target.clear()
            elif hasattr(target, 'setValue'):
                target.setValue(0.0)
            elif isinstance(target, QDoubleSpinBox):
                target.setValue(0.0)
        except RuntimeError:
            self.last_target_widget = None
            self._update_target_indicator()

    # Raccourcis de ciblage rapide avec sélection intégrale
    def focus_search(self):
        try:
            if self.pos_tab and hasattr(self.pos_tab, 'cb_product_search'):
                w = self.pos_tab.cb_product_search
                if is_widget_valid(w):
                    w.setFocus()
                    QTimer.singleShot(0, w.selectAll)
                    self.last_target_widget = w
                    self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None

    def focus_client(self):
        try:
            if self.pos_tab and hasattr(self.pos_tab, 'cb_client'):
                w = self.pos_tab.cb_client.lineEdit() or self.pos_tab.cb_client
                if is_widget_valid(w):
                    w.setFocus()
                    QTimer.singleShot(0, w.selectAll)
                    self.last_target_widget = w
                    self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None

    def _get_active_row(self):
        try:
            if not self.pos_tab or not hasattr(self.pos_tab, 'cart_table'):
                return -1
            table = self.pos_tab.cart_table
            if not is_widget_valid(table) or table.rowCount() == 0:
                return -1
            row = table.currentRow()
            if row < 0:
                row = table.rowCount() - 1
                table.setCurrentCell(row, 1)
            return row
        except RuntimeError:
            return -1

    def focus_qty(self):
        try:
            row = self._get_active_row()
            if row >= 0:
                qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
                if is_widget_valid(qty_spin):
                    target = qty_spin.lineEdit() or qty_spin
                    if is_widget_valid(target):
                        target.setFocus()
                        QTimer.singleShot(0, target.selectAll)
                        self.last_target_widget = target
                        self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None

    def focus_remise(self):
        try:
            row = self._get_active_row()
            if row >= 0:
                remise_w = self.pos_tab.cart_table.cellWidget(row, 4)
                if is_widget_valid(remise_w) and hasattr(remise_w, 'value_spin'):
                    target = remise_w.value_spin.lineEdit() or remise_w.value_spin
                    if is_widget_valid(target):
                        target.setFocus()
                        QTimer.singleShot(0, target.selectAll)
                        self.last_target_widget = target
                        self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None

    def adjust_active_qty(self, delta):
        try:
            row = self._get_active_row()
            if row >= 0:
                qty_spin = self.pos_tab.cart_table.cellWidget(row, 2)
                if is_widget_valid(qty_spin):
                    new_val = max(0.01, min(qty_spin.maximum(), qty_spin.value() + delta))
                    qty_spin.setValue(new_val)
                    target = qty_spin.lineEdit() or qty_spin
                    if is_widget_valid(target):
                        target.setFocus()
                        QTimer.singleShot(0, target.selectAll)
                        self.last_target_widget = target
                    self._update_target_indicator()
        except RuntimeError:
            self.last_target_widget = None
            self._update_target_indicator()

    def delete_active_cart_row(self):
        self.last_target_widget = None
        row = self._get_active_row()
        if row >= 0:
            self.pos_tab.cart_table.removeRow(row)
            self.pos_tab.calculate_totals()
        if self.pos_tab and hasattr(self.pos_tab, 'cb_product_search') and is_widget_valid(self.pos_tab.cb_product_search):
            self.last_target_widget = self.pos_tab.cb_product_search
            self.pos_tab.cb_product_search.setFocus()
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
