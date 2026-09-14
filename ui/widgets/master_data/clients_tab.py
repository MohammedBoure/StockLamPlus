# ui/widgets/master_data/clients_tab.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QPushButton, QHBoxLayout, QMessageBox, QLineEdit,
                               QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QBrush
from .dialogs import ClientDialog
from .client_statement_dialog import ClientStatementDialog
from ui.formatting import format_money

class ClientsTab(QWidget):
    """
    Tab for managing clients with balance & credit limits tracking and account statements.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.client_manager = data_manager.clients
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Toolbar ---
        control_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un client (Nom, Email, Ville, Catégorie)...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_clients_data)

        self.add_button = QPushButton("➕ Ajouter Client")
        self.add_button.setMinimumHeight(35)
        self.add_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.add_button.clicked.connect(self.open_add_dialog)

        self.btn_statement_top = QPushButton("📄 Relevé de Compte")
        self.btn_statement_top.setMinimumHeight(35)
        self.btn_statement_top.setStyleSheet("background-color: #007572; color: white; font-weight: bold;")
        self.btn_statement_top.clicked.connect(self.open_statement_dialog)
        
        self.refresh_button = QPushButton("🔄 Actualiser")
        self.refresh_button.setMinimumHeight(35)
        self.refresh_button.clicked.connect(self.load_clients_data)
        
        control_layout.addWidget(self.search_input, 1)
        control_layout.addWidget(self.add_button)
        control_layout.addWidget(self.btn_statement_top)
        control_layout.addWidget(self.refresh_button)
        main_layout.addLayout(control_layout)

        # --- Table ---
        self.clients_table = QTableWidget()
        columns = ["ID", "Nom du Client", "Contact", "Téléphone", "Email", "Ville", "Catégorie", "Plafond Crédit", "Solde Actuel", "NIF", "RC"]
        self.clients_table.setColumnCount(len(columns))
        self.clients_table.setHorizontalHeaderLabels(columns)

        self.clients_table.setSortingEnabled(True)
        self.clients_table.horizontalHeader().setSectionsClickable(True)
        self.clients_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.clients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.clients_table.setAlternatingRowColors(True)
        self.clients_table.verticalHeader().setDefaultSectionSize(40)
        self.clients_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.clients_table.setColumnHidden(0, True) # Hide ID
        
        self.clients_table.doubleClicked.connect(self.open_edit_dialog)
        self.clients_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clients_table.customContextMenuRequested.connect(self.open_context_menu)
        
        main_layout.addWidget(self.clients_table)

        # --- Bottom Actions ---
        actions_layout = QHBoxLayout()
        self.statement_button = QPushButton("📄 Relevé de Compte")
        self.statement_button.setStyleSheet("background-color: #007572; color: white; font-weight: bold;")
        self.statement_button.clicked.connect(self.open_statement_dialog)

        self.edit_button = QPushButton("✏️ Modifier le Client")
        self.edit_button.clicked.connect(self.open_edit_dialog)
        
        self.delete_button = QPushButton("🗑️ Supprimer")
        self.delete_button.setStyleSheet("color: #c0392b;")
        self.delete_button.clicked.connect(self.delete_client)
        
        actions_layout.addWidget(self.statement_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.delete_button)
        main_layout.addLayout(actions_layout)

        self.load_clients_data()

    def _create_centered_item(self, text, is_numeric=False):
        item = QTableWidgetItem()
        if is_numeric:
            try:
                val = float(str(text))
                item.setData(Qt.EditRole, val)
            except:
                item.setText(str(text))
        else:
            item.setText(str(text) if text is not None else "")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def load_clients_data(self):
        try:
            if hasattr(self.client_manager, 'get_all_clients_with_balances'):
                clients = self.client_manager.get_all_clients_with_balances()
            else:
                clients = self.client_manager.get_all_clients()

            search_text = self.search_input.text().lower()

            filtered_clients = []
            for c in clients:
                if search_text in str(c.get('Client_Name', '')).lower() or \
                   (c.get('Email') and search_text in str(c.get('Email', '')).lower()) or \
                   (c.get('City') and search_text in str(c.get('City', '')).lower()) or \
                   (c.get('Phone') and search_text in str(c.get('Phone', '')).lower()) or \
                   (c.get('Price_Tier') and search_text in str(c.get('Price_Tier', '')).lower()):
                    filtered_clients.append(c)

            self.clients_table.setSortingEnabled(False)
            self.clients_table.setRowCount(0)
            
            for row_idx, c in enumerate(filtered_clients):
                self.clients_table.insertRow(row_idx)
                
                # ["ID", "Nom du Client", "Contact", "Téléphone", "Email", "Ville", "Catégorie", "Plafond Crédit", "Solde Actuel", "NIF", "RC"]
                self.clients_table.setItem(row_idx, 0, self._create_centered_item(c['Client_ID'], is_numeric=True))
                self.clients_table.setItem(row_idx, 1, self._create_centered_item(c.get('Client_Name', '')))
                self.clients_table.setItem(row_idx, 2, self._create_centered_item(c.get('Contact_Person', '')))
                self.clients_table.setItem(row_idx, 3, self._create_centered_item(c.get('Phone', '')))
                self.clients_table.setItem(row_idx, 4, self._create_centered_item(c.get('Email', '')))
                self.clients_table.setItem(row_idx, 5, self._create_centered_item(c.get('City', '')))

                # 6. Catégorie (Price_Tier)
                tier_raw = str(c.get('Price_Tier') or 'Prix_1')
                tier_map = {
                    'Prix_1': 'Prix 1 (Détail)',
                    'Prix_2': 'Prix 2 (Demi-Gros)',
                    'Prix_3': 'Prix 3 (Gros)',
                    'Prix_4': 'Prix 4 (Super-Gros)'
                }
                tier_str = tier_map.get(tier_raw, tier_raw)
                item_tier = self._create_centered_item(tier_str)
                self.clients_table.setItem(row_idx, 6, item_tier)

                # 7. Plafond Crédit
                limit_val = float(c.get('Credit_Limit') or 0.0)
                item_limit = QTableWidgetItem(f"{format_money(limit_val)} DA")
                item_limit.setData(Qt.EditRole, limit_val)
                item_limit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.clients_table.setItem(row_idx, 7, item_limit)

                # 8. Solde Actuel avec Badge Styling / QBrush Coloring
                bal_val = float(c.get('Current_Balance') or 0.0)
                item_bal = QTableWidgetItem(f"{format_money(bal_val)} DA")
                item_bal.setData(Qt.EditRole, bal_val)
                item_bal.setTextAlignment(Qt.AlignCenter)
                item_bal.setFont(QFont("Segoe UI", 9, QFont.Bold))

                # Badge styling / QBrush coloring: Green when Solde <= Credit_Limit, and Red when Solde > Credit_Limit
                if bal_val <= limit_val:
                    item_bal.setBackground(QBrush(QColor("#dcfce7")))  # Soft pastel green
                    item_bal.setForeground(QBrush(QColor("#15803d")))  # Dark green text
                else:
                    item_bal.setBackground(QBrush(QColor("#fee2e2")))  # Soft pastel red
                    item_bal.setForeground(QBrush(QColor("#b91c1c")))  # Dark red text

                self.clients_table.setItem(row_idx, 8, item_bal)

                # 9. NIF & 10. RC
                self.clients_table.setItem(row_idx, 9, self._create_centered_item(c.get('Tax_ID_Number', '')))
                self.clients_table.setItem(row_idx, 10, self._create_centered_item(c.get('Commercial_Reg_No', '')))

            self.clients_table.setSortingEnabled(True)

        except Exception as e:
            logging.error(f"Error loading clients: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des clients:\n{str(e)}")

    def open_add_dialog(self):
        dialog = ClientDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                res = self.client_manager.add_client(**data)
                if res:
                    self.load_clients_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Ce nom de client existe déjà ou une erreur est survenue.")

    def open_edit_dialog(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client à modifier.")
            return

        client_id_item = self.clients_table.item(row, 0)
        if not client_id_item:
            return
        client_id = int(client_id_item.text())

        client_data = self.client_manager.get_client_by_id(client_id)
        if not client_data:
            QMessageBox.warning(self, "Erreur", "Données introuvables.")
            return

        dialog = ClientDialog(self, client_data)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                if self.client_manager.update_client(client_id, **new_data):
                    self.load_clients_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de mettre à jour le client.")

    def delete_client(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client à supprimer.")
            return

        client_id = int(self.clients_table.item(row, 0).text())
        client_name = self.clients_table.item(row, 1).text()

        confirm = QMessageBox.question(
            self,
            "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer le client '{client_name}' ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if self.client_manager.soft_delete_client(client_id):
                self.load_clients_data()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de supprimer le client. Il est peut-être lié à des factures.")

    def open_statement_dialog(self):
        row = self.clients_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client pour afficher son relevé de compte.")
            return

        client_id_item = self.clients_table.item(row, 0)
        if not client_id_item:
            return
        client_id = int(client_id_item.text())

        dialog = ClientStatementDialog(self.data_manager, client_id, self)
        dialog.exec()

    def open_context_menu(self, pos):
        item = self.clients_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        self.clients_table.selectRow(row)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #007572;
                color: white;
            }
        """)

        act_statement = QAction("📄 Générer Relevé de Compte", self)
        act_edit = QAction("✏️ Modifier le Client", self)
        act_delete = QAction("🗑️ Supprimer le Client", self)

        act_statement.triggered.connect(self.open_statement_dialog)
        act_edit.triggered.connect(self.open_edit_dialog)
        act_delete.triggered.connect(self.delete_client)

        menu.addAction(act_statement)
        menu.addSeparator()
        menu.addAction(act_edit)
        menu.addAction(act_delete)

        menu.exec(self.clients_table.viewport().mapToGlobal(pos))
