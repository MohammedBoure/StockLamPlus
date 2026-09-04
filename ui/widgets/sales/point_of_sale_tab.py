# ui/widgets/sales/point_of_sale_tab.py

import logging
import uuid
from datetime import date
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QMessageBox, QDoubleSpinBox, QSpinBox, QDialog,
                               QDateEdit, QFrame, QCompleter, QAbstractItemView, QInputDialog,
                               QScrollArea, QGridLayout, QCheckBox, QSizePolicy)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel, QTimer, QSize, QPoint
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QColor
from branding import get_logo_path
from ui.icons import get_trash_icon
from .dialogs import ClientDialog, OpenSessionDialog, CloseSessionDialog, QuickCashPaymentDialog
from .touch_keypad import TouchKeypadDialog
from .pos_payment_dialog import PaymentDialog
from ui.formatting import format_money

def enable_auto_select_all(widget):
    """Garantit que 100% du texte du champ est sélectionné au clic (press & release) et au focus."""
    if not widget:
        return widget
    target = getattr(widget, 'lineEdit', lambda: None)() or widget

    orig_press = target.mousePressEvent
    orig_release = target.mouseReleaseEvent
    orig_focus = target.focusInEvent

    def on_press(e):
        orig_press(e)
        QTimer.singleShot(0, widget.selectAll if hasattr(widget, 'selectAll') else target.selectAll)

    def on_release(e):
        orig_release(e)
        QTimer.singleShot(0, widget.selectAll if hasattr(widget, 'selectAll') else target.selectAll)

    def on_focus(e):
        orig_focus(e)
        QTimer.singleShot(0, widget.selectAll if hasattr(widget, 'selectAll') else target.selectAll)

    target.mousePressEvent = on_press
    target.mouseReleaseEvent = on_release
    target.focusInEvent = on_focus
    return widget


class AutoSelectLineEdit(QLineEdit):
    """Champ de texte sélectionnant automatiquement tout son contenu au clic pour une saisie immédiate."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_auto_select_all(self)


class AutoSelectDoubleSpinBox(QDoubleSpinBox):
    """SpinBox numérique dont tout le texte est sélectionné dès la prise de focus ou le clic."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_auto_select_all(self)


class RemiseWidget(QWidget):
    valueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        self.value_spin = AutoSelectDoubleSpinBox()
        self.value_spin.setRange(0, 9999999)
        self.value_spin.setValue(0.0)
        self.value_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.value_spin.setDecimals(2)
        self.value_spin.setAlignment(Qt.AlignCenter)
        self.value_spin.setMinimumWidth(82)
        self.value_spin.setStyleSheet("border-radius: 0px; padding: 2px 4px;")
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["%", "DA"])
        self.type_combo.setMinimumWidth(58)
        self.type_combo.setStyleSheet("border-radius: 0px; padding: 2px 4px;")
        
        layout.addWidget(self.value_spin, 2)
        layout.addWidget(self.type_combo, 1)

        self.value_spin.valueChanged.connect(lambda v: self.valueChanged.emit())
        self.type_combo.currentIndexChanged.connect(lambda idx: self.valueChanged.emit())

    def get_value(self):
        return self.value_spin.value()

    def get_type(self):
        return self.type_combo.currentText()


class BarcodeLineEdit(AutoSelectLineEdit):
    """Line edit that accepts numeric input from common AZERTY scanner mappings
    and auto-selects all text on click for rapid overwrite."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        enable_auto_select_all(self)

    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1",
            Qt.Key_Eacute: "2",
            Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4",
            Qt.Key_ParenLeft: "5",
            Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7",
            Qt.Key_Underscore: "8",
            Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0",
        }
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
            return
        super().keyPressEvent(event)


class PointOfSaleTab(QWidget):
    """
    Point de Vente (POS) Tab for creating sales.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        self.cart_items = []  # List of dicts representing cart rows
        self.payment_lines = []
        self.loyalty_redeem_points = 0
        self.active_draft_id = None
        self.current_total_ttc = 0.0
        self.batches_cache = []
        self.active_pos_group = 1
        self.search_map = {}
        self.barcode_map = {}
        self.terminal_id = None
        self.terminal_label = "Caisse"
        self.cash_session_id = None
        self.cash_session_no = None
        self.scan_timer = QTimer(self)
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.process_instant_scan)
        
        self.init_ui()
        self.load_initial_data()
        self.refresh_cash_session_context()
        self._install_shortcuts()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # 1. Very Thin Full-Width Top Bar (outside of each container, no space wasted)
        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        # 2. Main Workspace (Horizontal Split: Cart area on left, Favorites panel on right)
        workspace = QHBoxLayout()
        workspace.setSpacing(8)
        workspace.setContentsMargins(0, 0, 0, 0)

        # --- Left Section: Cart Frame ---
        cart_frame = QFrame()
        cart_frame.setObjectName("CartFrame")
        cart_frame.setStyleSheet("""
            QFrame#CartFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
            }
        """)
        left_layout = QVBoxLayout(cart_frame)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(5)

        # Ligne Unique Compacte : Scanner Code-Barres/Recherche + Client + Nouveau Client + Date
        top_inputs_row = QHBoxLayout()
        top_inputs_row.setSpacing(6)
        top_inputs_row.setContentsMargins(0, 0, 0, 0)

        self.cb_product_search = BarcodeLineEdit()
        self.cb_product_search.setObjectName("ScanSearchInput")
        self.cb_product_search.setMinimumHeight(38)
        self.cb_product_search.setMaximumHeight(38)
        self.cb_product_search.setPlaceholderText("🔍 Scanner code-barres ou chercher un produit / référence...")
        self.cb_product_search.setStyleSheet("""
            QLineEdit#ScanSearchInput {
                background-color: #ffffff;
                border: 2px solid #007572;
                border-radius: 0px;
                padding: 0px 10px;
                font-size: 13px;
                font-weight: 500;
                color: #1e293b;
                min-height: 38px;
                max-height: 38px;
            }
            QLineEdit#ScanSearchInput:focus {
                border: 2px solid #005a57;
                background-color: #ffffff;
            }
        """)
        enable_auto_select_all(self.cb_product_search)

        self.product_completer = QCompleter(self)
        self.product_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_completer.setFilterMode(Qt.MatchContains)
        self.product_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.cb_product_search.setCompleter(self.product_completer)
        self.product_completer.activated.connect(self.on_product_selected)
        self.cb_product_search.returnPressed.connect(self.handle_search_return)
        self.cb_product_search.textChanged.connect(self.schedule_instant_scan)

        self.cb_client = QComboBox()
        self.cb_client.setPlaceholderText("👤 Client / Comptoir...")
        self.cb_client.setMinimumHeight(38)
        self.cb_client.setMaximumHeight(38)
        self.cb_client.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 0px 8px;
                font-size: 12px;
                color: #1e293b;
                min-height: 38px;
                max-height: 38px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #cbd5e1;
            }
        """)
        self.make_combo_searchable(self.cb_client)
        enable_auto_select_all(self.cb_client)

        self.btn_new_client = QPushButton("➕ Client")
        self.btn_new_client.setCursor(Qt.PointingHandCursor)
        self.btn_new_client.setToolTip("Créer rapidement un nouveau client")
        self.btn_new_client.setFixedWidth(78)
        self.btn_new_client.setMinimumHeight(38)
        self.btn_new_client.setMaximumHeight(38)
        self.btn_new_client.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #007572;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-weight: bold;
                font-size: 11px;
                padding: 0px 6px;
                min-height: 38px;
                max-height: 38px;
            }
            QPushButton:hover {
                background-color: #e6f4f1;
                border-color: #007572;
            }
        """)
        self.btn_new_client.clicked.connect(self.create_quick_client)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setFixedWidth(110)
        self.date_edit.setMinimumHeight(38)
        self.date_edit.setMaximumHeight(38)
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 0px 6px;
                font-size: 12px;
                color: #1e293b;
                min-height: 38px;
                max-height: 38px;
            }
        """)

        top_inputs_row.addWidget(self.cb_product_search, stretch=5)
        top_inputs_row.addWidget(self.cb_client, stretch=3)
        top_inputs_row.addWidget(self.btn_new_client)
        top_inputs_row.addWidget(self.date_edit)

        # Filtre d'emplacement (lieu de retrait)
        self.combo_location_filter = QComboBox()
        self.combo_location_filter.addItem("📍 Tous Lieux", None)
        self.combo_location_filter.setFixedWidth(135)
        self.combo_location_filter.setMinimumHeight(38)
        self.combo_location_filter.setMaximumHeight(38)
        self.combo_location_filter.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 0px 6px;
                font-size: 12px;
                color: #007572;
                font-weight: bold;
                min-height: 38px;
                max-height: 38px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #cbd5e1;
            }
        """)
        self.combo_location_filter.currentIndexChanged.connect(self.on_location_filter_changed)
        top_inputs_row.addWidget(self.combo_location_filter)

        left_layout.addLayout(top_inputs_row)

        # Line 3: Cart Table (Dynamic unlimited width/height, touch-friendly scrollbars, full text visible)
        self.cart_table = QTableWidget()
        self.cart_table.setObjectName("POSCartTable")
        # Colonnes ordonnées par priorité : Bouton Suppr en tête, Produits et Paramètres de vente d'abord, Stock/Lot/TVA en fin
        cols = ["", "Produit", "Qté vendue", "Prix HT", "Remise", "Total TTC", "Code-barres", "Emplacement (Lieu)", "Stock", "Lot", "TVA"]
        self.cart_table.setColumnCount(len(cols))
        self.cart_table.setHorizontalHeaderLabels(cols)

        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(0, 36)
        # Toutes les colonnes de données sont Interactives et s'étendent sans limite pour afficher l'intégralité des textes
        for i in range(1, len(cols)):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(65)
        self.cart_table.setColumnWidth(1, 230)
        self.cart_table.setColumnWidth(2, 90)
        self.cart_table.setColumnWidth(3, 135)
        self.cart_table.setColumnWidth(4, 145)
        self.cart_table.setColumnWidth(5, 110)
        self.cart_table.setColumnWidth(6, 160)
        self.cart_table.setColumnWidth(7, 165)
        self.cart_table.setColumnWidth(8, 75)
        self.cart_table.setColumnWidth(9, 110)
        self.cart_table.setColumnWidth(10, 85)

        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cart_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cart_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cart_table.cellDoubleClicked.connect(self.on_cart_cell_double_clicked)
        self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cart_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setShowGrid(False)
        self.cart_table.setWordWrap(False)
        self.cart_table.setFocusPolicy(Qt.NoFocus)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        self.cart_table.verticalHeader().setMinimumSectionSize(44)

        self.cart_table.setStyleSheet("""
            QTableWidget#POSCartTable {
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
                padding: 4px 6px;
                border-radius: 0px;
            }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 14px;
                margin: 0px;
                border: none;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 30px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: #007572;
            }
            QScrollBar:horizontal {
                background: #f1f5f9;
                height: 14px;
                margin: 0px;
                border: none;
                border-radius: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                min-width: 30px;
                border-radius: 0px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #007572;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
            }
        """)
        left_layout.addWidget(self.cart_table, stretch=1)

        # Line 4: Middle Action Bar at the bottom
        bottom_bar = self._build_bottom_bar()
        left_layout.addLayout(bottom_bar)

        workspace.addWidget(cart_frame, stretch=4)

        # --- Right Section: Favorites Panel (Empty space ready for fast access products) ---
        fav_panel = self._build_favorites_panel()
        workspace.addWidget(fav_panel, stretch=1)

        root_layout.addLayout(workspace)

    def _build_top_bar(self):
        """Barre supérieure réactive et fluide sans aucun chevauchement."""
        top_frame = QFrame()
        top_frame.setObjectName("POSTopBar")
        top_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_frame.setStyleSheet("""
            QFrame#POSTopBar {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 4px 8px;
            }
        """)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(6, 4, 6, 4)
        top_layout.setSpacing(8)

        # 1. Caisse & Session Badge Button
        self.btn_caisse_status = QPushButton("🔴 Caisse Fermée (Cliquer pour ouvrir)")
        self.btn_caisse_status.setCursor(Qt.PointingHandCursor)
        self.btn_caisse_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_caisse_status.setStyleSheet("""
            QPushButton {
                background: #fdf2f1;
                color: #c0392b;
                border: 1px solid #fecaca;
                border-radius: 0px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
                min-height: 30px;
            }
            QPushButton:hover {
                background: #fadbd8;
            }
        """)
        self.btn_caisse_status.clicked.connect(self.manage_cash_session)
        top_layout.addWidget(self.btn_caisse_status, 0)

        # Séparateur
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #cbd5e1;")
        top_layout.addWidget(sep1, 0)

        # 2. Informations Financières Secondaires
        self.lbl_total_ht = QLabel("Total HT : 0,00 DA")
        self.lbl_total_ht.setStyleSheet("font-size: 11px; color: #475569; font-weight: 600; padding: 2px;")
        top_layout.addWidget(self.lbl_total_ht, 0)

        self.lbl_total_remise = QLabel("Remise : 0,00 DA")
        self.lbl_total_remise.setStyleSheet("font-size: 11px; color: #d35400; font-weight: 600; padding: 2px;")
        top_layout.addWidget(self.lbl_total_remise, 0)

        self.lbl_total_tva = QLabel("TVA : 0,00 DA")
        self.lbl_total_tva.setStyleSheet("font-size: 11px; color: #475569; font-weight: 600; padding: 2px;")
        top_layout.addWidget(self.lbl_total_tva, 0)

        top_layout.addStretch(1)

        # 2b. Bouton Actualiser
        self.btn_refresh = QPushButton("🔄 Actualiser")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Actualiser les données de caisse, produits, stock et favoris (F5)")
        self.btn_refresh.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #007572;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #e6f4f1;
                border-color: #007572;
            }
        """)
        self.btn_refresh.clicked.connect(self.load_initial_data)
        top_layout.addWidget(self.btn_refresh, 0)

        # 3. Prix Final Net à Payer
        self.frame_net_total = QFrame()
        self.frame_net_total.setObjectName("NetTotalFrame")
        self.frame_net_total.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.frame_net_total.setStyleSheet("""
            QFrame#NetTotalFrame {
                background-color: #007572;
                border: 1px solid #005a57;
                border-radius: 0px;
                padding: 4px 12px;
                min-height: 34px;
            }
        """)
        frame_layout = QHBoxLayout(self.frame_net_total)
        frame_layout.setContentsMargins(4, 0, 4, 0)
        frame_layout.setSpacing(0)

        self.lbl_total_ttc = QLabel("NET À PAYER : 0,00 DA")
        self.lbl_total_ttc.setAlignment(Qt.AlignCenter)
        self.lbl_total_ttc.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff; padding: 0px; margin: 0px;")
        frame_layout.addWidget(self.lbl_total_ttc)

        top_layout.addWidget(self.frame_net_total, 0)

        return top_frame

    def _update_total_display(self, total):
        """Modifie la taille du texte dynamiquement selon la longueur du montant pour éviter tout chevauchement."""
        self.current_total_ttc = float(total or 0.0)
        val_str = f"{format_money(self.current_total_ttc)} DA"
        txt = f"NET À PAYER : {val_str}"
        length = len(val_str)
        if length <= 12:
            font_size = 17
        elif length <= 16:
            font_size = 15
        elif length <= 20:
            font_size = 13
        else:
            font_size = 12
        self.lbl_total_ttc.setText(txt)
        self.lbl_total_ttc.setStyleSheet(f"font-size: {font_size}px; font-weight: 800; color: #ffffff;")

    def _build_favorites_panel(self):
        """Panneau droit contenant les boutons de numéros pour les listes de produits favoris."""
        fav_frame = QFrame()
        fav_frame.setObjectName("FavoritesFrame")
        fav_frame.setFixedWidth(280)
        fav_frame.setStyleSheet("""
            QFrame#FavoritesFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
            }
        """)
        fav_layout = QVBoxLayout(fav_frame)
        fav_layout.setContentsMargins(4, 4, 4, 4)
        fav_layout.setSpacing(4)

        # Zone de numéros simples (1, 2, 3...) organisés en lignes/barres : dès qu'une ligne est pleine (8 boutons), une nouvelle ligne/barre commence
        self.fav_num_scroll = QScrollArea()
        self.fav_num_scroll.setWidgetResizable(True)
        self.fav_num_scroll.setFixedHeight(34)
        self.fav_num_scroll.setFrameShape(QFrame.NoFrame)
        self.fav_num_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.fav_num_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.fav_num_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 6px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 0px;
            }
        """)

        self.fav_tabs_container = QWidget()
        self.fav_tabs_container.setStyleSheet("background: transparent;")
        from PySide6.QtWidgets import QGridLayout
        self.fav_tabs_layout = QGridLayout(self.fav_tabs_container)
        self.fav_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.fav_tabs_layout.setSpacing(2)
        self.fav_tabs_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.fav_num_scroll.setWidget(self.fav_tabs_container)
        fav_layout.addWidget(self.fav_num_scroll)

        self.scroll_fav = QScrollArea()
        self.scroll_fav.setWidgetResizable(True)
        self.scroll_fav.setFrameShape(QFrame.NoFrame)
        self.scroll_fav.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 8px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 0px;
            }
        """)

        self.fav_container = QWidget()
        self.fav_container.setStyleSheet("background: transparent;")
        self.fav_grid = QVBoxLayout(self.fav_container)
        self.fav_grid.setContentsMargins(0, 0, 0, 0)
        self.fav_grid.setSpacing(3)

        self.scroll_fav.setWidget(self.fav_container)
        fav_layout.addWidget(self.scroll_fav)

        return fav_frame

    def set_active_fav_group(self, group_num):
        """Change la liste active et actualise immédiatement l'affichage."""
        self.active_pos_group = group_num
        self.refresh_favorites_display()

    def refresh_favorites_display(self):
        """Actualise les boutons de numéros simples et les produits de la liste sélectionnée."""
        # 1. Détecter tous les numéros existants dans les lots en stock
        existing_numbers = set()
        for batch in self.batches_cache:
            grp = batch.get('POS_Priority_Group')
            if grp is not None:
                try:
                    grp_int = int(grp)
                    if grp_int > 0:
                        existing_numbers.add(grp_int)
                except (ValueError, TypeError):
                    pass

        try:
            if hasattr(self.data_manager, 'products') and hasattr(self.data_manager.products, 'get_assigned_pos_priority_groups'):
                existing_numbers.update(self.data_manager.products.get_assigned_pos_priority_groups())
        except Exception:
            pass

        numbers_list = sorted(list(existing_numbers))
        if not numbers_list:
            numbers_list = [1, 2]

        if not hasattr(self, 'active_pos_group') or self.active_pos_group not in numbers_list:
            self.active_pos_group = numbers_list[0]

        # 2. Rafraîchir les boutons de numéros simples organisés en lignes/barres (8 par ligne)
        while self.fav_tabs_layout.count():
            item = self.fav_tabs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        BUTTONS_PER_ROW = 8
        for idx, num in enumerate(numbers_list):
            r = idx // BUTTONS_PER_ROW
            c = idx % BUTTONS_PER_ROW

            btn_num = QPushButton(str(num))
            btn_num.setFocusPolicy(Qt.NoFocus)
            btn_num.setCursor(Qt.PointingHandCursor)
            btn_num.setFixedSize(30, 26)
            is_active = (self.active_pos_group == num)
            if is_active:
                btn_num.setStyleSheet("""
                    QPushButton {
                        background-color: #007572;
                        color: #ffffff;
                        border: 1px solid #005a57;
                        border-radius: 0px;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 0px;
                    }
                """)
            else:
                btn_num.setStyleSheet("""
                    QPushButton {
                        background-color: #f8fafc;
                        color: #1e293b;
                        border: 1px solid #cbd5e1;
                        border-radius: 0px;
                        font-weight: 600;
                        font-size: 12px;
                        padding: 0px;
                    }
                    QPushButton:hover {
                        background-color: #e2e8f0;
                        color: #007572;
                        border-color: #007572;
                    }
                """)
            btn_num.clicked.connect(lambda _chk=False, n_val=num: self.set_active_fav_group(n_val))
            self.fav_tabs_layout.addWidget(btn_num, r, c)

        # Dès qu'une ligne est pleine (8 boutons), une nouvelle ligne/barre est créée et la hauteur s'adapte
        num_rows = ((len(numbers_list) - 1) // BUTTONS_PER_ROW) + 1 if numbers_list else 1
        calculated_h = min(96, num_rows * 28 + (num_rows - 1) * 2 + 4)
        self.fav_num_scroll.setFixedHeight(calculated_h)

        # 3. Rafraîchir les produits de la liste active
        while self.fav_grid.count():
            item = self.fav_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        matching_batches = []
        seen_products = set()
        for batch in self.batches_cache:
            p_id = batch.get('Product_ID')
            if p_id in seen_products:
                continue

            grp = batch.get('POS_Priority_Group')
            try:
                grp_val = int(grp) if grp is not None else None
            except (ValueError, TypeError):
                grp_val = None

            if grp_val == self.active_pos_group:
                seen_products.add(p_id)
                matching_batches.append(batch)

        if not matching_batches:
            lbl_empty = QLabel(
                f"<b>Liste {self.active_pos_group} vide</b><br><br>"
                "Pour affecter un produit :<br>"
                "Inventaire > Clic-droit sur le lot > "
                f"<i>⭐ Assigner au Groupe (N° {self.active_pos_group})</i>"
            )
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setWordWrap(True)
            lbl_empty.setStyleSheet("color: #64748b; font-size: 11px; padding: 20px 8px; background: #f8fafc; border: 1px dashed #cbd5e1; line-height: 140%;")
            self.fav_grid.addWidget(lbl_empty)
            self.fav_grid.addStretch()
            return

        count = 0
        for batch in matching_batches:
            p_name = batch.get('Product_Name', 'Produit')
            p_price = float(batch.get('Selling_Price_HT') or 0.0)
            tva = float(batch.get('Selling_TVA_Percent') or batch.get('Tax_Rate_Percent') or 0.0)
            p_ttc = p_price * (1 + tva / 100.0)
            stock_q = batch.get('Quantity_Current', 0)

            btn = QPushButton()
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"{p_name}\nPrix TTC : {format_money(p_ttc)} DA | Stock : {stock_q}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 0px;
                    text-align: left;
                    padding: 2px 6px;
                    min-height: 26px;
                    max-height: 28px;
                }
                QPushButton:hover {
                    background-color: #e6f4f1;
                    border-color: #007572;
                }
            """)
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.setSpacing(4)

            lbl_n = QLabel(p_name)
            lbl_n.setStyleSheet("font-weight: 600; font-size: 11px; color: #1e293b; background: transparent;")

            lbl_p = QLabel(f"{format_money(p_ttc)} DA")
            lbl_p.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl_p.setStyleSheet("font-size: 10px; color: #007572; font-weight: bold; background: transparent;")

            btn_layout.addWidget(lbl_n, stretch=1)
            btn_layout.addWidget(lbl_p)

            btn.clicked.connect(lambda _chk=False, b=batch: self.handle_favorite_product_clicked(b))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=batch: self.show_favorite_product_context_menu(b, pos))
            self.fav_grid.addWidget(btn)

            count += 1
            if count >= 40:
                break

        self.fav_grid.addStretch()

    def _build_bottom_bar(self):
        """Barre centrale inférieure contenant les boutons interactifs essentiels à bords vifs."""
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(6)

        # 1. Bouton Valider (Renommé simplement 'Valider')
        self.btn_validate = QPushButton("✔️ Valider (F10)")
        self.btn_validate.setCursor(Qt.PointingHandCursor)
        self.btn_validate.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border-radius: 0px;
                padding: 6px 16px;
                min-height: 36px;
                border: none;
            }
            QPushButton:hover { background-color: #005a57; }
            QPushButton:pressed { background-color: #004543; }
        """)
        self.btn_validate.clicked.connect(self.validate_sale)
        bottom_layout.addWidget(self.btn_validate)

        # 2. Pavé Tactile / Clavier Virtuel Animé et Déplaçable
        self.btn_keypad = QPushButton("🔢 Pavé Tactile")
        self.btn_keypad.setCursor(Qt.PointingHandCursor)
        self.btn_keypad.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #007572;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #007572;
                border-radius: 0px;
                padding: 6px 12px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #e6f4f1; }
        """)
        self.btn_keypad.clicked.connect(self.toggle_touch_keypad)
        bottom_layout.addWidget(self.btn_keypad)

        # 2b. Saisie / Association de Code-Barres
        self.btn_enter_barcode = QPushButton("🏷️ Saisie Code-Barres")
        self.btn_enter_barcode.setCursor(Qt.PointingHandCursor)
        self.btn_enter_barcode.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #0f5f8f;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #93c5fd;
                border-radius: 0px;
                padding: 6px 12px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #eff6ff; }
        """)
        self.btn_enter_barcode.clicked.connect(self.on_btn_enter_barcode_clicked)
        bottom_layout.addWidget(self.btn_enter_barcode)

        # 3. Suspendre
        self.btn_hold_sale = QPushButton("⏸️ Suspendre (F8)")
        self.btn_hold_sale.setCursor(Qt.PointingHandCursor)
        self.btn_hold_sale.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 6px 10px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_hold_sale.clicked.connect(lambda: self.save_current_draft("Held"))
        bottom_layout.addWidget(self.btn_hold_sale)

        # 4. Reprendre
        self.btn_resume_sale = QPushButton("▶️ Reprendre (F9)")
        self.btn_resume_sale.setCursor(Qt.PointingHandCursor)
        self.btn_resume_sale.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 6px 10px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_resume_sale.clicked.connect(self.resume_draft)
        bottom_layout.addWidget(self.btn_resume_sale)

        # 5. Vider Panier
        self.btn_clear = QPushButton("🗑️ Vider Panier")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #e74c3c;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                padding: 6px 10px;
                min-height: 36px;
            }
            QPushButton:hover { background-color: #fee2e2; }
        """)
        self.btn_clear.clicked.connect(self.clear_cart)
        bottom_layout.addWidget(self.btn_clear)

        bottom_layout.addStretch(1)

        # 6. Impression Automatique Ticket
        self.chk_print_receipt = QCheckBox("🖨️ Ticket Auto")
        self.chk_print_receipt.setChecked(True)
        self.chk_print_receipt.setStyleSheet("font-size: 12px; color: #2c3e50; font-weight: 600;")
        bottom_layout.addWidget(self.chk_print_receipt)

        return bottom_layout

    def toggle_touch_keypad(self):
        """Affiche ou masque le dialogue animé et déplaçable du pavé tactile."""
        if not hasattr(self, 'touch_keypad') or self.touch_keypad is None:
            self.touch_keypad = TouchKeypadDialog(parent=self)
        if self.touch_keypad.isVisible():
            self.touch_keypad.hide()
        else:
            btn_pos = self.btn_keypad.mapToGlobal(QPoint(0, 0))
            x = max(20, btn_pos.x() - 50)
            y = max(20, btn_pos.y() - 370)
            self.touch_keypad.show_animated(QPoint(x, y))

    def _has_permission(self, permission):
        try:
            checker = getattr(self.window(), "has_permission", None)
            return bool(checker(permission)) if checker else True
        except Exception:
            return True

    def _install_shortcuts(self):
        self._shortcut_validate = QShortcut(QKeySequence("F10"), self)
        self._shortcut_validate.activated.connect(self.validate_sale)
        self._shortcut_hold = QShortcut(QKeySequence("F8"), self)
        self._shortcut_hold.activated.connect(lambda: self.save_current_draft("Held"))
        self._shortcut_resume = QShortcut(QKeySequence("F9"), self)
        self._shortcut_resume.activated.connect(self.resume_draft)
        self._shortcut_session = QShortcut(QKeySequence("F6"), self)
        self._shortcut_session.activated.connect(self.manage_cash_session)
        self._shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self._shortcut_refresh.activated.connect(self.load_initial_data)

    def apply_promotion_code(self):
        if not self._has_permission("act_pos_discount"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour appliquer une promotion.")
            return
        code, ok = QInputDialog.getText(self, "Promotion", "Code coupon:")
        if not ok or not code.strip():
            return
        items = self._collect_cart_items()
        success, result = self.data_manager.pos_features.evaluate_promotion(code.strip(), items)
        if not success:
            QMessageBox.warning(self, "Promotion", result.get("message", "Promotion invalide."))
            return
        discount_percent = float(result.get("discount_percent") or 0)
        allowed_products = set(result.get("promotion", {}).get("Product_IDs") or [])
        for row in range(self.cart_table.rowCount()):
            batch = self.cart_table.item(row, 1).data(Qt.UserRole) or {}
            if allowed_products and batch.get("Product_ID") not in allowed_products:
                continue
            remise = self.cart_table.cellWidget(row, 4)
            remise.type_combo.setCurrentText("%")
            remise.value_spin.setValue(min(100.0, discount_percent))
        self.calculate_totals()
        self.btn_promotion.setText(f"Promotion: {code.strip()}")
        QMessageBox.information(
            self, "Promotion", f"Remise appliquée: {float(result.get('discount_amount') or 0):.2f} DA"
        )
    def apply_loyalty_points(self):
        if self.cart_table.rowCount() == 0:
            QMessageBox.warning(self, "Fidélité", "Le panier est vide.")
            return
        client = self.cb_client.currentData()
        client_id = client.get("Client_ID") if isinstance(client, dict) else client
        if not client_id:
            QMessageBox.warning(self, "Fidélité", "Sélectionnez un client pour utiliser ses points.")
            return
        account = self.data_manager.pos_features.get_loyalty_account(client_id) or {}
        balance = float(account.get("Points_Balance") or 0)
        if balance <= 0:
            QMessageBox.information(self, "Fidélité", "Ce client n'a pas de points disponibles.")
            return
        available_points = max(0, int(balance) - self.loyalty_redeem_points)
        if available_points <= 0:
            QMessageBox.information(self, "Fidélité", "Tous les points disponibles sont déjà appliqués.")
            return
        points, ok = QInputDialog.getInt(
            self, "Fidélité", f"Points disponibles: {available_points} (1 point = 1 DA HT)", 1, 1, available_points, 1
        )
        if not ok:
            return
        remaining = float(points)
        for row in range(self.cart_table.rowCount()):
            if remaining <= 0:
                break
            qty_widget = self.cart_table.cellWidget(row, 2)
            price_widget = self.cart_table.cellWidget(row, 3)
            remise = self.cart_table.cellWidget(row, 4)
            line_ht = float(qty_widget.value() * (price_widget.currentData() or 0))
            current_discount = (
                line_ht * remise.get_value() / 100.0
                if remise.get_type() == "%"
                else remise.get_value()
            )
            available = max(0.0, line_ht - current_discount)
            applied = min(float(int(remaining)), available)
            if applied < 1.0:
                continue
            remise.type_combo.setCurrentText("DA")
            remise.value_spin.setValue(min(line_ht, current_discount + applied))
            remaining -= applied
        applied_points = points - int(round(remaining))
        self.loyalty_redeem_points = max(0, self.loyalty_redeem_points + applied_points)
        self.calculate_totals()
        self.btn_loyalty.setText(f"Points utilisés: {self.loyalty_redeem_points}")
        if applied_points <= 0:
            QMessageBox.warning(self, "Fidélité", "Aucun point n'a pu être appliqué.")
        else:
            QMessageBox.information(self, "Fidélité", f"{applied_points} point(s) appliqué(s).")
    def open_payment_dialog(self):
        if self.cart_table.rowCount() == 0:
            QMessageBox.warning(self, "Paiement", "Le panier est vide.")
            return False
        credit_summary = {}
        client_id = self.cb_client.currentData()
        if client_id and hasattr(self.data_manager, "pos_features"):
            credit_summary = self.data_manager.pos_features.get_client_credit_summary(client_id)
        dialog = PaymentDialog(
            self.current_total_ttc,
            self,
            default_method=self.cb_payment_method.currentData() or "Cash",
            credit_summary=credit_summary,
        )
        if dialog.exec() != QDialog.Accepted:
            return False
        self.payment_lines = dialog.get_payment_lines()
        if self.payment_lines:
            self.cb_payment_method.setCurrentIndex(
                max(0, self.cb_payment_method.findData(self.payment_lines[0]["method"]))
            )
            self.btn_payment_details.setText(
                f"Paiement enregistré ({len(self.payment_lines)} ligne(s))"
            )
        return True

    def create_quick_client(self):
        dialog = ClientDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data:
            return
        client_id = self.data_manager.clients.add_client(**data)
        if not client_id:
            QMessageBox.warning(self, "Client", "Impossible de créer le client.")
            return
        self.load_initial_data()
        for index in range(self.cb_client.count()):
            client = self.cb_client.itemData(index)
            if isinstance(client, dict) and client.get("Client_ID") == client_id:
                self.cb_client.setCurrentIndex(index)
                break

    def _collect_cart_items(self):
        items = []
        for row in range(self.cart_table.rowCount()):
            batch_item = self.cart_table.item(row, 1)
            if not batch_item:
                continue
            batch = batch_item.data(Qt.UserRole) or {}
            qty = self.cart_table.cellWidget(row, 2).value()
            price_ht = self.cart_table.cellWidget(row, 3).currentData() or 0.0
            remise = self.cart_table.cellWidget(row, 4)
            line_ht = qty * price_ht
            if remise.get_type() == "%":
                discount_percent = max(0.0, min(100.0, remise.get_value()))
            else:
                discount_amount = max(0.0, min(remise.get_value(), line_ht))
                discount_percent = (discount_amount / line_ht * 100.0) if line_ht else 0.0
            items.append({
                "product_id": batch.get("Product_ID"),
                "batch_id": batch.get("Batch_ID"),
                "qty_sold": qty,
                "unit_price_ht": price_ht,
                "discount_percent": discount_percent,
                "tva_percent": self.cart_table.cellWidget(row, 10).value(),
            })
        return items

    def save_current_draft(self, draft_type="Held"):
        if not self._has_permission("act_pos_hold_sale" if draft_type == "Held" else "act_pos_quote"):
            QMessageBox.warning(self, "Autorisation", "Vous n'avez pas l'autorisation pour cette action.")
            return
        items = self._collect_cart_items()
        if not items:
            QMessageBox.warning(self, "Vente", "Le panier est vide.")
            return
        client = self.cb_client.currentData()
        draft_id = self.data_manager.pos_features.save_draft(
            client.get("Client_ID") if client else None,
            self.date_edit.date().toString("yyyy-MM-dd"),
            items,
            self.current_total_ttc,
            draft_type=draft_type,
            user_id=self.get_current_user_id(),
        )
        if draft_id:
            self.active_draft_id = None
            self.clear_cart()
            QMessageBox.information(self, "Vente", "La vente a été enregistrée et peut être reprise.")
        else:
            QMessageBox.warning(self, "Vente", "Impossible d'enregistrer la vente suspendue.")

    def resume_draft(self):
        drafts = self.data_manager.pos_features.list_drafts()
        if not drafts:
            QMessageBox.information(self, "Vente", "Aucune vente suspendue.")
            return
        labels = [
            f"{row.get('Draft_Ref')} | {row.get('Draft_Type')} | {row.get('Client_Name') or 'Comptoir'} | {row.get('Total_Amount_TTC') or 0} DA"
            for row in drafts
        ]
        label, ok = QInputDialog.getItem(self, "Reprendre une vente", "Vente:", labels, 0, False)
        if not ok:
            return
        selected = drafts[labels.index(label)]
        draft = self.data_manager.pos_features.get_draft(selected.get("Draft_ID"))
        if not draft:
            QMessageBox.warning(self, "Vente", "La vente suspendue est introuvable.")
            return
        self.clear_cart()
        for item in draft.get("cart_items", []):
            batch = next((b for b in self.batches_cache if b.get("Batch_ID") == item.get("batch_id")), None)
            if not batch:
                continue
            self.add_product_to_cart(batch)
            row = self.cart_table.rowCount() - 1
            self.cart_table.cellWidget(row, 2).setValue(float(item.get("qty_sold") or 1))
            price = self.cart_table.cellWidget(row, 3)
            price_index = price.findData(float(item.get("unit_price_ht") or 0))
            if price_index >= 0:
                price.setCurrentIndex(price_index)
            remise = self.cart_table.cellWidget(row, 4)
            remise.type_combo.setCurrentText("%")
            remise.value_spin.setValue(float(item.get("discount_percent") or 0))
            self.cart_table.cellWidget(row, 10).setValue(float(item.get("tva_percent") or 0))
        self.active_draft_id = draft.get("Draft_ID")
        if draft.get("Client_ID"):
            for index in range(self.cb_client.count()):
                client = self.cb_client.itemData(index)
                if isinstance(client, dict) and client.get("Client_ID") == draft.get("Client_ID"):
                    self.cb_client.setCurrentIndex(index)
                    break
        self.calculate_totals()
    def make_combo_searchable(self, combo):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        if combo.completer():
            combo.completer().setFilterMode(Qt.MatchContains)
            combo.completer().setCaseSensitivity(Qt.CaseInsensitive)
        enable_auto_select_all(combo)

    def get_current_user_id(self):
        try:
            main_window = self.window()
            current_user = getattr(main_window, 'current_user', None)
            if isinstance(current_user, dict):
                return current_user.get('User_ID') or current_user.get('id')
        except Exception:
            pass
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def refresh_cash_session_context(self):
        """Actualise le badge et les informations de la session de caisse active."""
        user_id = self.get_current_user_id()
        session = self.data_manager.cash_sessions.get_any_open_session(user_id)
        if session:
            self.cash_session_id = session.get('Cash_Session_ID')
            self.terminal_id = session.get('Terminal_ID')
            self.terminal_label = session.get('Terminal_Name') or session.get('Terminal_Code') or "Caisse"
            self.cash_session_no = session.get('Session_No')
            if hasattr(self, 'btn_caisse_status'):
                self.btn_caisse_status.setText(f"🟢 {self.terminal_label} ({self.cash_session_no})")
                self.btn_caisse_status.setStyleSheet("""
                    QPushButton {
                        background: #e8f8f5;
                        color: #007572;
                        border: 1px solid #a3e4d7;
                        border-radius: 0px;
                        padding: 4px 10px;
                        font-weight: bold;
                        font-size: 12px;
                        min-height: 28px;
                    }
                    QPushButton:hover { background: #d1f2eb; }
                """)
        else:
            self.cash_session_id = None
            self.cash_session_no = None
            if hasattr(self, 'btn_caisse_status'):
                self.btn_caisse_status.setText("🔴 Caisse Fermée (Cliquer pour ouvrir)")
                self.btn_caisse_status.setStyleSheet("""
                    QPushButton {
                        background: #fdf2f1;
                        color: #c0392b;
                        border: 1px solid #fecaca;
                        border-radius: 0px;
                        padding: 4px 10px;
                        font-weight: bold;
                        font-size: 12px;
                        min-height: 28px;
                    }
                    QPushButton:hover { background: #fadbd8; }
                """)

    def manage_cash_session(self):
        """Ouvre le dialogue de gestion de session de caisse (ouverture / clôture)."""
        if not self.cash_session_id:
            self.open_cash_session()
        else:
            summary = self.data_manager.cash_sessions.get_session_summary(self.cash_session_id)
            open_sess = self.data_manager.cash_sessions.get_open_session(self.terminal_id) or {}
            open_amt = float(open_sess.get('Opening_Amount') or 0.0)
            exp_cash = float(summary.get('Expected_Cash') or 0.0)
            theo_total = open_amt + exp_cash
            invoices = summary.get('Invoice_Count') or 0

            box = QMessageBox(self)
            box.setWindowTitle("Gestion de Caisse")
            box.setText(f"<b>Caisse Active : {self.terminal_label}</b><br>"
                        f"<b>Session N° : {self.cash_session_no}</b><br><br>"
                        f"• Fond initial d'ouverture : <b>{format_money(open_amt)} DA</b><br>"
                        f"• Ventes espèces de la session : <b>{format_money(exp_cash)} DA</b><br>"
                        f"• Total espèces théorique en caisse : <b>{format_money(theo_total)} DA</b><br>"
                        f"• Nombre de tickets émis : <b>{invoices}</b><br><br>"
                        f"Que souhaitez-vous faire ?")
            btn_details = box.addButton("📋 Voir Détails Session", QMessageBox.ActionRole)
            btn_close = box.addButton("🔒 Clôturer la Session", QMessageBox.ActionRole)
            btn_continue = box.addButton("Poursuivre les ventes", QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_details:
                from ui.widgets.sales.dialogs import CashSessionDetailsDialog
                dlg = CashSessionDetailsDialog(self.data_manager, self.cash_session_id, parent=self)
                dlg.exec()
            elif clicked == btn_close:
                self.close_cash_session()

    def open_cash_session(self):
        """Ouvre une nouvelle session de caisse en choisissant la caisse et le fond initial."""
        if not self._has_permission("act_pos_open_session"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour ouvrir la caisse.")
            return

        terminals = self.data_manager.cash_sessions.get_terminals()
        if not terminals:
            QMessageBox.warning(self, "Caisse", "Aucune caisse disponible dans le système.")
            return

        dlg = OpenSessionDialog(terminals, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        terminal_id = data['terminal_id']
        opening_amount = data['opening_amount']
        notes = data['notes']

        success, session = self.data_manager.cash_sessions.open_session(
            terminal_id=terminal_id,
            user_id=self.get_current_user_id(),
            opening_amount=opening_amount,
            notes=notes
        )

        if success:
            self.terminal_id = terminal_id
            self.terminal_label = data['terminal_name']
            self.cash_session_id = session.get('Cash_Session_ID')
            self.cash_session_no = session.get('Session_No')
            self.refresh_cash_session_context()
            QMessageBox.information(
                self, "Caisse Ouverte",
                f"Session de caisse démarrée avec succès !\n\nSession : {self.cash_session_no}\nFond initial : {format_money(opening_amount)} DA"
            )
        else:
            QMessageBox.critical(self, "Erreur", session.get('message', "Impossible d'ouvrir la caisse."))

    def close_cash_session(self):
        """Clôture la session de caisse en cours avec comptage réel et enregistrement d'écart."""
        if not self._has_permission("act_pos_close_session"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour clôturer la caisse.")
            return

        if not self.cash_session_id:
            QMessageBox.warning(self, "Caisse", "Aucune session ouverte à clôturer.")
            return

        if self.cart_table.rowCount() > 0:
            QMessageBox.warning(self, "Caisse", "Veuillez vider ou valider le panier en cours avant de clôturer la caisse.")
            return

        summary = self.data_manager.cash_sessions.get_session_summary(self.cash_session_id)
        open_session = self.data_manager.cash_sessions.get_open_session(self.terminal_id) or {
            'Terminal_Name': self.terminal_label,
            'Session_No': self.cash_session_no,
            'Opening_Amount': 0.0
        }

        dlg = CloseSessionDialog(open_session, summary, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        success, result = self.data_manager.cash_sessions.close_session(
            cash_session_id=self.cash_session_id,
            user_id=self.get_current_user_id(),
            counted_cash=data['counted_cash'],
            notes=data['notes']
        )

        if success:
            diff = float(result.get('Cash_Difference') or 0.0)
            diff_str = f"+{format_money(diff)}" if diff > 0 else format_money(diff)
            msg = (f"Session de caisse clôturée avec succès !\n\n"
                   f"• Total théorique attendu : {format_money(result.get('Expected_Cash') or 0)} DA\n"
                   f"• Montant réel compté : {format_money(data['counted_cash'])} DA\n"
                   f"• Écart de caisse : {diff_str} DA")
            QMessageBox.information(self, "Caisse Clôturée", msg)
            self.cash_session_id = None
            self.cash_session_no = None
            self.refresh_cash_session_context()
        else:
            QMessageBox.critical(self, "Erreur", result.get('message', "Impossible de clôturer la caisse."))

    def record_cash_movement(self, movement_type):
        if not self._has_permission("act_pos_cash_movement"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour modifier la caisse.")
            return
        if not self.cash_session_id:
            QMessageBox.warning(self, "Caisse", "Aucune session ouverte.")
            return
        amount, ok = QInputDialog.getDouble(self, "Mouvement caisse", "Montant:", 0.0, 0.01, 999999999.0, 2)
        if not ok:
            return
        reason, ok = QInputDialog.getText(self, "Mouvement caisse", "Motif:")
        if not ok or not reason.strip():
            return
        movement_id = self.data_manager.pos_features.add_cash_movement(
            self.cash_session_id, movement_type, amount, reason.strip(), self.get_current_user_id()
        )
        if movement_id:
            QMessageBox.information(self, "Caisse", "Mouvement enregistré.")
        else:
            QMessageBox.warning(self, "Caisse", "Impossible d'enregistrer le mouvement.")
    def load_initial_data(self):
        # Load clients
        self.cb_client.clear()
        self.cb_client.addItem("Vente comptoir / sans client", None)
        try:
            clients = self.data_manager.clients.get_all_clients()
            for c in clients:
                self.cb_client.addItem(f"{c['Client_Name']} - {c.get('City', '')}", c)
            self.cb_client.setCurrentIndex(0)
        except Exception as e:
            logging.error(f"Error loading clients for POS: {e}")

        # Load products (Batches with stock > 0)
        self.cb_product_search.blockSignals(True)
        self.cb_product_search.clear()
        self.cb_product_search.blockSignals(False)
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        try:
            self.batches_cache = self.data_manager.batches.get_all_batches_with_details()
            suggestions = []
            for batch in self.batches_cache:
                suggestion = self.format_product_suggestion(batch)
                suggestions.append(suggestion)
                self.search_map[suggestion] = batch
                self.register_barcodes(batch)
            self.product_completer.setModel(QStringListModel(suggestions))
            if hasattr(self, 'fav_grid'):
                self.refresh_favorites_display()
            self.populate_pos_locations()
        except Exception as e:
            logging.error(f"Error loading batches for POS: {e}")

    def normalize_code(self, value):
        return str(value or "").strip().lower().replace(" ", "").replace("-", "")

    def is_real_code(self, value):
        code = str(value or "").strip()
        return bool(code) and code.lower() not in {"none", "null", "---"}

    def parse_all_barcodes(self, batch_or_text):
        """Extrait et nettoie tous les codes-barres distincts (supporte codes multiples séparés par virgule, slash, etc.)."""
        if isinstance(batch_or_text, dict):
            raw_codes = [
                batch_or_text.get("Internal_Barcode"),
                batch_or_text.get("External_Barcode"),
                batch_or_text.get("Barcode")
            ]
        else:
            raw_codes = [batch_or_text]

        results = []
        for raw in raw_codes:
            if not self.is_real_code(raw):
                continue
            import re
            parts = re.split(r'[,;/|\r\n]+', str(raw))
            for p in parts:
                p_clean = p.strip()
                if self.is_real_code(p_clean) and p_clean not in results:
                    results.append(p_clean)
        return results

    def register_barcodes(self, batch):
        codes = self.parse_all_barcodes(batch)
        for code in codes:
            normalized = self.normalize_code(code)
            if normalized:
                self.barcode_map[normalized] = batch

    def format_product_suggestion(self, batch):
        codes = self.parse_all_barcodes(batch)
        code_str = " / ".join(codes) if codes else "-"
        lot = batch.get("Lot_Number") or "---"
        qty = batch.get("Quantity_Current") or 0
        return f"[{code_str}] {batch.get('Product_Name', '')} | Lot: {lot} | Stock: {qty}"

    def on_product_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            self.add_product_to_cart(batch)

    def schedule_instant_scan(self, text):
        if not text.strip():
            self.scan_timer.stop()
            return
        self.scan_timer.start(120)

    def _parse_scan_input(self, text):
        raw = str(text or "").strip()
        if "*" not in raw:
            return 1.0, raw
        prefix, code = raw.split("*", 1)
        try:
            quantity = float(prefix.strip())
        except (TypeError, ValueError):
            return 1.0, raw
        return (quantity if quantity > 0 else 1.0), code.strip()
    def process_instant_scan(self):
        quantity, code = self._parse_scan_input(self.cb_product_search.text())
        if not code:
            return
        batch = self.barcode_map.get(self.normalize_code(code))
        if batch:
            self.add_product_to_cart(batch, quantity=quantity)
    def handle_search_return(self):
        quantity, _ = self._parse_scan_input(self.cb_product_search.text())
        self.add_product_to_cart(self.find_batch_from_search_text(), show_not_found=True, quantity=quantity)
    def find_batch_from_search_text(self):
        _quantity, text = self._parse_scan_input(self.cb_product_search.text())
        if not text:
            return None

        if text in self.search_map:
            return self.search_map[text]

        exact_code = self.barcode_map.get(self.normalize_code(text))
        if exact_code:
            return exact_code

        lowered = text.lower()
        matches = [
            batch for batch in self.batches_cache
            if lowered in str(batch.get("Product_Name", "")).lower()
            or lowered in str(batch.get("Lot_Number", "")).lower()
        ]
        return matches[0] if len(matches) == 1 else None

    def clear_search_input(self):
        self.cb_product_search.blockSignals(True)
        self.cb_product_search.clear()
        self.cb_product_search.blockSignals(False)
        self.cb_product_search.setFocus()

    def flash_scan_feedback(self, success=True):
        color = "#dff7e8" if success else "#fdecea"
        border = "#27ae60" if success else "#e74c3c"
        self.cb_product_search.setStyleSheet(
            f"border: 2px solid {border}; background-color: {color};"
        )
        QTimer.singleShot(350, lambda: self.cb_product_search.setStyleSheet(""))

    def add_product_to_cart(self, batch=None, show_not_found=False, quantity=1.0):
        if batch is None:
            batch = self.find_batch_from_search_text()

        if not batch:
            if show_not_found and self.cb_product_search.text().strip() != "":
                self.flash_scan_feedback(False)
                QMessageBox.warning(self, "Attention", "Produit non trouvé.")
                self.clear_search_input()
            return
            
        # If the same lot is scanned again, increase the quantity smoothly.
        for row in range(self.cart_table.rowCount()):
            existing_item = self.cart_table.item(row, 1)
            existing_batch = existing_item.data(Qt.UserRole) if existing_item else None
            if existing_batch and existing_batch.get('Batch_ID') == batch.get('Batch_ID'):
                qty_widget = self.cart_table.cellWidget(row, 2)
                if qty_widget and qty_widget.value() < qty_widget.maximum():
                    qty_widget.setValue(min(qty_widget.maximum(), qty_widget.value() + max(0.01, float(quantity or 1))))
                    self.cart_table.scrollToItem(existing_item)
                    self.flash_scan_feedback(True)
                    self.clear_search_input()
                    return
                QMessageBox.information(self, "Info", "Stock maximum déjà atteint pour ce lot.")
                self.clear_search_input()
                return

        row_idx = self.cart_table.rowCount()
        self.cart_table.insertRow(row_idx)
        self.cart_table.setRowHeight(row_idx, 46)
        
        # Col 0: Action Delete (Icône professionnelle vectorielle et bords vifs)
        btn_del = QPushButton()
        btn_del.setIcon(get_trash_icon(18))
        btn_del.setIconSize(QSize(18, 18))
        btn_del.setFixedSize(28, 28)
        btn_del.setToolTip("Supprimer cette ligne du panier")
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border: 1px solid #dc2626;
            }
            QPushButton:pressed {
                background-color: #fca5a5;
            }
        """)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(lambda _checked=False, button=btn_del: self.remove_cart_row(button))
        action_cell = QWidget()
        action_layout = QHBoxLayout(action_cell)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setAlignment(Qt.AlignCenter)
        action_layout.addWidget(btn_del)
        self.cart_table.setCellWidget(row_idx, 0, action_cell)

        # Col 1: Product Name
        name_item = QTableWidgetItem(batch.get('Product_Name', 'Produit'))
        name_item.setData(Qt.UserRole, batch)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setToolTip(batch.get('Product_Name', 'Produit'))
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.cart_table.setItem(row_idx, 1, name_item)
        
        # Col 2: Qty Sold Input (Auto-sélection intégrale garantie au clic)
        qty_spin = AutoSelectDoubleSpinBox()
        enable_auto_select_all(qty_spin)
        qty_spin.setRange(0.01, float(batch.get('Quantity_Current') or 999999))
        qty_spin.setDecimals(2)
        qty_spin.setValue(min(qty_spin.maximum(), max(0.01, float(quantity or 1))))
        qty_spin.setAlignment(Qt.AlignCenter)
        qty_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        qty_spin.setStyleSheet("border-radius: 0px; padding: 2px 4px; min-height: 30px;")
        qty_spin.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 2, qty_spin)
        
        # Col 3: Price Selection Combo (Support 4 prices, bords vifs)
        price_combo = QComboBox()
        price_combo.setMinimumWidth(130)
        price_combo.setStyleSheet("border-radius: 0px; padding: 2px 4px;")
        p1 = float(batch.get('Selling_Price_HT') or 0)
        p2 = float(batch.get('Selling_Price_HT_2') or 0)
        p3 = float(batch.get('Selling_Price_HT_3') or 0)
        p4 = float(batch.get('Selling_Price_HT_4') or 0)
        
        if p1 > 0: price_combo.addItem(f"Prix 1 - {format_money(p1)} DA", p1)
        if p2 > 0: price_combo.addItem(f"Prix 2 - {format_money(p2)} DA", p2)
        if p3 > 0: price_combo.addItem(f"Prix 3 - {format_money(p3)} DA", p3)
        if p4 > 0: price_combo.addItem(f"Prix 4 - {format_money(p4)} DA", p4)
        
        if price_combo.count() == 0:
            price_combo.addItem("0,00 DA", 0.0)
            
        price_combo.currentIndexChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 3, price_combo)
        
        # Col 4: Remise (Widget % ou DA, sélection intégrale au clic)
        remise_widget = RemiseWidget()
        enable_auto_select_all(remise_widget.value_spin)
        remise_widget.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 4, remise_widget)
        
        # Col 5: Line Total TTC
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cart_table.setItem(row_idx, 5, total_item)

        # Col 6: Code-barres (Affichage intégral sans coupure et support double-clic pour saisie/association)
        codes = self.parse_all_barcodes(batch)
        barcode_text = " / ".join(codes) if codes else "---"

        barcode_item = QTableWidgetItem(barcode_text)
        barcode_item.setFlags(barcode_item.flags() & ~Qt.ItemIsEditable)
        barcode_item.setTextAlignment(Qt.AlignCenter)
        barcode_item.setBackground(QColor("#edf7ff"))
        barcode_item.setForeground(QColor("#0f5f8f"))
        f_bc = barcode_item.font()
        f_bc.setBold(True)
        barcode_item.setFont(f_bc)
        barcode_item.setToolTip(f"{barcode_text}\n(Double-clic pour saisir/associer un code-barres)")
        self.cart_table.setItem(row_idx, 6, barcode_item)
        
        # Col 7: Emplacement (Lieu de retrait interactif si plusieurs lieux disponibles)
        p_id = batch.get('Product_ID')
        available_batches = [
            b for b in self.batches_cache
            if b.get('Product_ID') == p_id and float(b.get('Quantity_Current') or 0) > 0
        ]
        if len(available_batches) <= 1:
            loc_name = batch.get('Location_Name') or "Par défaut"
            loc_item = QTableWidgetItem(f"📍 {loc_name}")
            loc_item.setFlags(loc_item.flags() & ~Qt.ItemIsEditable)
            loc_item.setTextAlignment(Qt.AlignCenter)
            loc_item.setFont(QFont("", -1, QFont.Bold))
            loc_item.setForeground(QColor("#007572"))
            loc_item.setToolTip(f"Emplacement de retrait : {loc_name}")
            self.cart_table.setItem(row_idx, 7, loc_item)
        else:
            loc_combo = QComboBox()
            loc_combo.setStyleSheet("""
                QComboBox {
                    background-color: #f0fdf4;
                    border: 1px solid #86efac;
                    border-radius: 0px;
                    padding: 2px 4px;
                    color: #166534;
                    font-weight: bold;
                    font-size: 11px;
                    min-height: 28px;
                }
                QComboBox::drop-down { border-left: 1px solid #86efac; }
            """)
            for b_opt in available_batches:
                l_name = b_opt.get('Location_Name') or "Lieu inconnu"
                s_qty = b_opt.get('Quantity_Current') or 0
                l_num = b_opt.get('Lot_Number') or ""
                label = f"📍 {l_name} ({s_qty})"
                if l_num and l_num != "---":
                    label += f" | {l_num}"
                loc_combo.addItem(label, b_opt)

            for i in range(loc_combo.count()):
                if loc_combo.itemData(i).get('Batch_ID') == batch.get('Batch_ID'):
                    loc_combo.setCurrentIndex(i)
                    break

            loc_combo.currentIndexChanged.connect(
                lambda _idx, cb=loc_combo: self.on_cart_location_changed(cb)
            )
            self.cart_table.setCellWidget(row_idx, 7, loc_combo)

        # Col 8: Qty Stock
        stock_item = QTableWidgetItem(str(batch.get('Quantity_Current', 0)))
        stock_item.setFlags(stock_item.flags() & ~Qt.ItemIsEditable)
        stock_item.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row_idx, 8, stock_item)

        # Col 9: N° Lot
        lot_item = QTableWidgetItem(batch.get('Lot_Number', '---'))
        lot_item.setFlags(lot_item.flags() & ~Qt.ItemIsEditable)
        lot_item.setToolTip(str(batch.get('Lot_Number', '---')))
        lot_item.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row_idx, 9, lot_item)
        
        # Col 10: TVA
        tva_spin = AutoSelectDoubleSpinBox()
        enable_auto_select_all(tva_spin)
        tva_spin.setRange(0, 100)
        tva_spin.setSuffix(" %")
        tva_spin.setAlignment(Qt.AlignCenter)
        tva_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        tva_spin.setStyleSheet("border-radius: 0px; padding: 2px 4px; min-height: 30px;")
        tva_spin.setValue(float(batch.get('Selling_TVA_Percent') or batch.get('Tax_Rate_Percent') or 0))
        tva_spin.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 10, tva_spin)
        
        self.calculate_totals()
        # Ajustement dynamique sans limite pour garantir l'affichage complet de tous les textes
        self.cart_table.resizeColumnsToContents()
        self.cart_table.setColumnWidth(0, 36)
        if self.cart_table.columnWidth(1) < 220:
            self.cart_table.setColumnWidth(1, 220)
        # S'assurer que la colonne code-barres dispose d'assez d'espace pour afficher tout le texte
        fm = self.cart_table.fontMetrics()
        req_bc_w = fm.horizontalAdvance(barcode_text) + 36
        if self.cart_table.columnWidth(6) < req_bc_w:
            self.cart_table.setColumnWidth(6, req_bc_w)

        self.cart_table.scrollToBottom()
        self.flash_scan_feedback(True)
        
        # Clear search input for the next scan
        self.clear_search_input()

    def remove_cart_row(self, button):
        # Must find the real row dynamically because indexes shift
        for r in range(self.cart_table.rowCount()):
            widget = self.cart_table.cellWidget(r, 0)
            if widget == button or (widget and widget.findChild(QPushButton) == button):
                self.cart_table.removeRow(r)
                break
        self.calculate_totals()

    def calculate_totals(self):
        total_ht = 0.0
        total_tva = 0.0
        total_remise = 0.0
        
        for row in range(self.cart_table.rowCount()):
            qty_widget = self.cart_table.cellWidget(row, 2)
            price_widget = self.cart_table.cellWidget(row, 3)
            remise_widget = self.cart_table.cellWidget(row, 4)
            total_item = self.cart_table.item(row, 5)
            tva_widget = self.cart_table.cellWidget(row, 10)
            
            if not all([qty_widget, price_widget, remise_widget, tva_widget, total_item]):
                continue
                
            qty = qty_widget.value()
            price_ht = price_widget.currentData() or 0.0
            tva_pct = tva_widget.value()
            
            line_ht = qty * price_ht
            
            remise_val = remise_widget.get_value()
            remise_type = remise_widget.get_type()
            
            if remise_type == "%":
                remise_amount = line_ht * (remise_val / 100.0)
            else:
                remise_amount = remise_val

            remise_amount = max(0.0, min(remise_amount, line_ht))
                
            net_ht = max(0.0, line_ht - remise_amount)
            tva_val = net_ht * (tva_pct / 100.0)
            line_ttc = net_ht + tva_val
            
            total_ht += net_ht
            total_remise += remise_amount
            total_tva += tva_val
            
            total_item.setText(format_money(line_ttc))
            
        total_ttc = total_ht + total_tva
        self.current_total_ttc = total_ttc
        
        self.lbl_total_ht.setText(f"Total HT : {format_money(total_ht)} DA")
        self.lbl_total_tva.setText(f"TVA : {format_money(total_tva)} DA")
        self.lbl_total_remise.setText(f"Remise : {format_money(total_remise)} DA")
        if hasattr(self, '_update_total_display'):
            self._update_total_display(total_ttc)
        else:
            self.lbl_total_ttc.setText(f"NET À PAYER : {format_money(total_ttc)} DA")

    def clear_cart(self):
        self.loyalty_redeem_points = 0
        self.cart_table.setRowCount(0)
        self.calculate_totals()

    def _validate_sale_legacy(self):
        if self.cart_table.rowCount() == 0:
            QMessageBox.warning(self, "Erreur", "Le panier est vide.")
            return
            
        client = self.cb_client.currentData()
        client_id = client['Client_ID'] if client else None
        client_name = client['Client_Name'] if client else "Vente comptoir"
            
        invoice_date = self.date_edit.date().toString("yyyy-MM-dd")
        
        # 1. Create Invoice Header
        from database.system_logger import active_user_id
        u_id = active_user_id.get()
        
        invoice_id = self.data_manager.sales.create_invoice(
            client_id=client_id,
            invoice_date=invoice_date,
            status='Validated',
            notes=None if client else "Vente sans client",
            user_id=u_id
        )
        
        if not invoice_id:
            QMessageBox.critical(self, "Erreur", "Impossible de créer la facture.")
            return
            
        # 2. Add Details
        success = True
        for row in range(self.cart_table.rowCount()):
            batch = self.cart_table.item(row, 1).data(Qt.UserRole)
            qty = self.cart_table.cellWidget(row, 2).value()
            price_ht = self.cart_table.cellWidget(row, 3).currentData() or 0.0
            
            remise_val = self.cart_table.cellWidget(row, 4).get_value()
            remise_type = self.cart_table.cellWidget(row, 4).get_type()
            
            line_ht = qty * price_ht
            if remise_type == "%":
                remise_pct = max(0.0, min(remise_val, 100.0))
            else:
                remise_amount = max(0.0, min(remise_val, line_ht))
                remise_pct = (remise_amount / line_ht * 100.0) if line_ht > 0 else 0.0
                
            tva_pct = self.cart_table.cellWidget(row, 10).value()
            
            detail_id = self.data_manager.sales.add_invoice_detail(
                invoice_id=invoice_id,
                product_id=batch['Product_ID'],
                batch_id=batch['Batch_ID'],
                qty_sold=qty,
                unit_price_ht=price_ht,
                discount_percent=remise_pct,
                tva_percent=tva_pct
            )
            
            if not detail_id:
                success = False
                break
                
            # Deduct stock
            # In a real system, you'd use a dedicated function in inventory_batch_manager
            # For now, we rely on the manager if available, or do a direct adjustment
            self.data_manager.batches.stock_movement_log.create_movement_log(
                product_id=batch['Product_ID'],
                movement_type='Sale',
                qty_change=-float(qty),
                unit_used='Unit',
                batch_id=batch['Batch_ID'],
                user_id=u_id,
                notes=f"Vente Facture #{invoice_id} - Client: {client_name}"
            )
            
            # Update Current_Quantity in DB
            with self.data_manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s",
                    (qty, batch['Batch_ID'])
                )
                conn.commit()

        if success:
            QMessageBox.information(self, "Succès", f"Vente enregistrée avec succès ! Facture #{invoice_id}")
            self.clear_cart()
            # Reload inventory data so stock quantities are fresh
            self.load_initial_data()
        else:
            QMessageBox.critical(self, "Erreur", "Une erreur est survenue lors de l'enregistrement des détails.")

    def _build_receipt_data(self, invoice_label, invoice_date, client, cart_items):
        """Build a complete receipt payload from the same values used for the sale."""
        receipt_items = []
        subtotal_ht = 0.0
        remise_total = 0.0
        net_ht_total = 0.0
        tva_total = 0.0
        total_ttc = 0.0

        for row, item in enumerate(cart_items):
            batch = self.cart_table.item(row, 0).data(Qt.UserRole) or {}
            qty = float(item.get("qty_sold") or 0)
            unit_price_ht = float(item.get("unit_price_ht") or 0)
            discount_percent = max(0.0, min(100.0, float(item.get("discount_percent") or 0)))
            tva_percent = max(0.0, min(100.0, float(item.get("tva_percent") or 0)))

            price_before = qty * unit_price_ht
            discount_amount = min(price_before, price_before * discount_percent / 100.0)
            net_ht = max(0.0, price_before - discount_amount)
            tva_amount = net_ht * tva_percent / 100.0
            line_total_ttc = net_ht + tva_amount

            subtotal_ht += price_before
            remise_total += discount_amount
            net_ht_total += net_ht
            tva_total += tva_amount
            total_ttc += line_total_ttc

            receipt_items.append({
                "name": batch.get("Product_Name") or "Produit",
                "qty": qty,
                "unit_price_ht": round(unit_price_ht, 2),
                "price": round(unit_price_ht, 2),
                "price_before": round(price_before, 2),
                "discount_percent": round(discount_percent, 2),
                "discount_amount": round(discount_amount, 2),
                "net_ht": round(net_ht, 2),
                "tva_percent": round(tva_percent, 2),
                "tva_amount": round(tva_amount, 2),
                "total": round(line_total_ttc, 2),
            })

        printer_config = getattr(getattr(self.data_manager, "printer", None), "config", {}) or {}
        company = {
            "name": printer_config.get("lab_name", ""),
            "address": printer_config.get("lab_address", ""),
            "nif": printer_config.get("lab_nif", ""),
            "rc": printer_config.get("lab_rc", ""),
        }
        return {
            "id": str(invoice_label),
            "date": invoice_date,
            "client": client["Client_Name"] if client else "Passager",
            "cashier": self.terminal_label,
            "currency": "DA",
            "company": company,
            "logo_path": printer_config.get("receipt_logo_path") or get_logo_path(),
            "items": receipt_items,
            "subtotal_ht": round(subtotal_ht, 2),
            "remise_total": round(remise_total, 2),
            "net_ht": round(net_ht_total, 2),
            "tva_total": round(tva_total, 2),
            "total": round(total_ttc, 2),
            "show_discount": remise_total > 0,
            "show_tva": tva_total > 0,
            "payments": list(self.payment_lines),
        }

    def validate_sale(self):
        """Processus d'encaissement normal direct en Dinars uniquement (Espèces)."""
        if not self._has_permission("act_validate_sale"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour la validation des ventes.")
            return

        if self.cart_table.rowCount() == 0:
            QMessageBox.warning(self, "Panier", "Le panier est vide. Veuillez ajouter des produits.")
            return

        self.refresh_cash_session_context()
        if not self.cash_session_id:
            res = QMessageBox.question(
                self, "Session Caisse Requise",
                "Aucune session de caisse n'est actuellement ouverte.\nVoulez-vous ouvrir une session maintenant pour enregistrer cette vente ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if res == QMessageBox.Yes:
                self.open_cash_session()
            if not self.cash_session_id:
                return

        client = self.cb_client.currentData()
        client_id = client['Client_ID'] if client else None
        invoice_date = self.date_edit.date().toString("yyyy-MM-dd")

        # Dialogue rapide d'encaissement normal en Dinars (Espèces)
        dlg = QuickCashPaymentDialog(self.current_total_ttc, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        pay_data = dlg.get_data()
        received = pay_data['received']
        change = pay_data['change']
        should_print = pay_data['print_receipt']

        cart_items = []
        for row in range(self.cart_table.rowCount()):
            batch_item = self.cart_table.item(row, 1)
            batch = batch_item.data(Qt.UserRole) if batch_item else {}
            qty = self.cart_table.cellWidget(row, 2).value()
            price_ht = self.cart_table.cellWidget(row, 3).currentData() or 0.0
            remise_val = self.cart_table.cellWidget(row, 4).get_value()
            remise_type = self.cart_table.cellWidget(row, 4).get_type()

            line_ht = qty * price_ht
            if remise_type == "%":
                remise_pct = max(0.0, min(remise_val, 100.0))
            else:
                remise_amount = max(0.0, min(remise_val, line_ht))
                remise_pct = (remise_amount / line_ht * 100.0) if line_ht > 0 else 0.0

            cart_items.append({
                "product_id": batch.get('Product_ID'),
                "batch_id": batch.get('Batch_ID'),
                "qty_sold": qty,
                "unit_price_ht": price_ht,
                "discount_percent": remise_pct,
                "tva_percent": self.cart_table.cellWidget(row, 10).value(),
            })

        self.btn_validate.setEnabled(False)
        request_id = str(uuid.uuid4())
        try:
            success, result = self.data_manager.sales.create_validated_sale(
                client_id=client_id,
                invoice_date=invoice_date,
                cart_items=cart_items,
                terminal_id=self.terminal_id,
                cash_session_id=self.cash_session_id,
                payment_method="Cash",
                user_id=self.get_current_user_id(),
                request_id=request_id,
                notes=None if client else "Vente sans client",
                payment_lines=[{"method": "Cash", "amount": self.current_total_ttc}],
                draft_id=self.active_draft_id,
            )
        except Exception as exc:
            logging.exception("Unexpected error while validating POS sale")
            success = False
            result = {"message": str(exc) or "Une erreur inattendue est survenue."}
        finally:
            self.btn_validate.setEnabled(True)

        if success:
            invoice_label = result.get('invoice_no') or f"#{result.get('invoice_id')}"
            
            # Impression ticket si demandée
            if should_print:
                try:
                    invoice_data = self._build_receipt_data(
                        invoice_label, invoice_date, client, cart_items
                    )
                    self.data_manager.printer.print_receipt(invoice_data)
                except Exception as e:
                    logging.error(f"Erreur impression recu: {e}", exc_info=True)

            msg = f"Vente enregistrée avec succès !\n\nFacture : {invoice_label}\nMontant Payé : {format_money(self.current_total_ttc)} DA"
            if change > 0:
                msg += f"\nMonnaie Rendue : {format_money(change)} DA"
            QMessageBox.information(self, "Vente Validée", msg)

            self.active_draft_id = None
            self.clear_cart()
            self.load_initial_data()
        else:
            QMessageBox.critical(
                self, "Erreur",
                result.get('message', "Une erreur est survenue lors de l'enregistrement de la vente.")
            )
            self.load_initial_data()
        self.refresh_cash_session_context()

    def handle_favorite_product_clicked(self, batch):
        """Gère la sélection d'un produit favori : permet de choisir l'emplacement (lieu) si présent dans plusieurs endroits."""
        p_id = batch.get('Product_ID')
        loc_filter = self.combo_location_filter.currentData() if hasattr(self, 'combo_location_filter') else None

        matching_batches = [
            b for b in self.batches_cache
            if b.get('Product_ID') == p_id and float(b.get('Quantity_Current') or 0) > 0
        ]

        if loc_filter is not None:
            filtered_by_loc = [b for b in matching_batches if b.get('Location_ID') == loc_filter]
            if filtered_by_loc:
                matching_batches = filtered_by_loc

        if len(matching_batches) <= 1:
            target = matching_batches[0] if matching_batches else batch
            self.add_product_to_cart(target, quantity=1.0)
            return

        # Présent dans plusieurs emplacements ou lots : dialogue tactile de choix du lieu de retrait
        from ui.widgets.sales.dialogs import SelectBatchBarcodeDialog
        dlg = SelectBatchBarcodeDialog(matching_batches, parent=self)
        if dlg.exec():
            selected = dlg.get_selected_batch()
            if selected:
                self.add_product_to_cart(selected, quantity=1.0)

    def show_favorite_product_context_menu(self, batch, pos):
        """Menu contextuel pour gérer les codes-barres d'un produit depuis la liste des favoris."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor
        menu = QMenu(self)
        action_barcode = menu.addAction("🏷️ Saisir / Associer un Code-Barres...")
        action = menu.exec(QCursor.pos())
        if action == action_barcode:
            self.open_enter_barcode_dialog(batch)

    def on_cart_cell_double_clicked(self, row, col):
        """Ouvre le dialogue de saisie de code-barres lors du double-clic sur la colonne Code-barres."""
        if col == 6:  # Colonne Code-barres
            item = self.cart_table.item(row, 1)
            if item:
                batch = item.data(Qt.UserRole)
                if batch:
                    self.open_enter_barcode_dialog(batch, row_idx=row)

    def on_btn_enter_barcode_clicked(self):
        """Action du bouton Saisie Code-Barres dans la barre inférieure."""
        row = self.cart_table.currentRow()
        if row >= 0:
            item = self.cart_table.item(row, 1)
            if item:
                batch = item.data(Qt.UserRole)
                if batch:
                    self.open_enter_barcode_dialog(batch, row_idx=row)
                    return

        # Si aucune ligne n'est sélectionnée, demander à scanner ou sélectionner
        from PySide6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(
            self, "Saisie Code-Barres",
            "Scannez ou saisissez le code-barres à associer :"
        )
        if ok and code.strip():
            self.open_associate_unknown_barcode_dialog(code.strip())

    def open_enter_barcode_dialog(self, batch, row_idx=None):
        """Ouvre le dialogue de saisie de code-barres pour un produit/lot."""
        from ui.widgets.sales.dialogs import EnterProductBarcodeDialog
        dlg = EnterProductBarcodeDialog(self.data_manager, batch, parent=self)
        if dlg.exec():
            # Ré-enregistrer les codes-barres dans la table
            self.register_barcodes(batch)
            if row_idx is not None and row_idx < self.cart_table.rowCount():
                codes = self.parse_all_barcodes(batch)
                b_text = " / ".join(codes) if codes else "---"
                item = self.cart_table.item(row_idx, 6)
                if item:
                    item.setText(b_text)
                    item.setToolTip(f"{b_text}\n(Double-clic pour saisir/associer un code-barres)")
            self.load_active_batches()

    def open_associate_unknown_barcode_dialog(self, barcode):
        """Permet d'associer un code-barres scanné inconnu à un produit du catalogue."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QHBoxLayout, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("🏷️ Associer Code-Barres Inconnu")
        dlg.setMinimumSize(450, 200)
        l = QVBoxLayout(dlg)
        l.addWidget(QLabel(f"Code-barres scanné : <b>{barcode}</b>"))
        l.addWidget(QLabel("Sélectionnez le produit auquel associer ce code-barres :"))
        combo = QComboBox()
        combo.setEditable(True)
        products = self.data_manager.products.get_all_products()
        for p in products:
            combo.addItem(p.get('Product_Name', 'Produit'), p.get('Product_ID'))
        l.addWidget(combo)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_ok = QPushButton("Associer")
        btn_ok.setStyleSheet("background-color: #007572; color: white;")
        def _do_assoc():
            p_id = combo.currentData()
            if p_id:
                success, msg = self.data_manager.products.add_product_barcode(p_id, barcode)
                if success:
                    QMessageBox.information(dlg, "Succès", f"Code-barres '{barcode}' associé avec succès !")
                    dlg.accept()
                    self.load_active_batches()
                else:
                    QMessageBox.critical(dlg, "Erreur", f"Échec : {msg}")
        btn_ok.clicked.connect(_do_assoc)
        btn_box.addWidget(btn_ok)
        l.addLayout(btn_box)
        dlg.exec()

    def populate_pos_locations(self):
        """Charge la liste des emplacements disponibles dans le filtre de caisse."""
        if not hasattr(self, 'combo_location_filter'):
            return
        curr = self.combo_location_filter.currentData()
        self.combo_location_filter.blockSignals(True)
        self.combo_location_filter.clear()
        self.combo_location_filter.addItem("📍 Tous Lieux", None)
        try:
            if hasattr(self.data_manager, 'locations'):
                locs = self.data_manager.locations.get_all_locations()
                for loc in locs:
                    self.combo_location_filter.addItem(f"📍 {loc.get('Location_Name')}", loc.get('Location_ID'))
        except Exception as e:
            logging.error(f"Erreur populate_pos_locations: {e}")
        idx = self.combo_location_filter.findData(curr)
        if idx >= 0:
            self.combo_location_filter.setCurrentIndex(idx)
        else:
            self.combo_location_filter.setCurrentIndex(0)
        self.combo_location_filter.blockSignals(False)

    def on_location_filter_changed(self):
        """Actualise les produits favoris et la recherche lorsque l'emplacement sélectionné change."""
        self.refresh_favorites_display()

    def on_cart_location_changed(self, combo):
        """Change le lot/emplacement de retrait pour la ligne du panier correspondante."""
        for r in range(self.cart_table.rowCount()):
            if self.cart_table.cellWidget(r, 7) == combo:
                new_batch = combo.currentData()
                if not new_batch:
                    return
                # Mettre à jour l'objet batch dans la cellule produit
                name_item = self.cart_table.item(r, 1)
                if name_item:
                    name_item.setData(Qt.UserRole, new_batch)
                # Mettre à jour la cellule de stock (Col 8)
                stock_item = self.cart_table.item(r, 8)
                if stock_item:
                    stock_item.setText(str(new_batch.get('Quantity_Current', 0)))
                # Mettre à jour le N° Lot (Col 9)
                lot_item = self.cart_table.item(r, 9)
                if lot_item:
                    lot_num = new_batch.get('Lot_Number', '---')
                    lot_item.setText(lot_num)
                    lot_item.setToolTip(str(lot_num))
                # Mettre à jour le code-barres (Col 6)
                codes = self.parse_all_barcodes(new_batch)
                bc_text = " / ".join(codes) if codes else "---"
                bc_item = self.cart_table.item(r, 6)
                if bc_item:
                    bc_item.setText(bc_text)
                    bc_item.setToolTip(f"{bc_text}\n(Double-clic pour saisir/associer un code-barres)")
                # Mettre à jour le maximum autorisé pour la quantité
                qty_spin = self.cart_table.cellWidget(r, 2)
                if qty_spin:
                    qty_spin.setRange(0.01, float(new_batch.get('Quantity_Current') or 999999))
                self.calculate_totals()
                break
