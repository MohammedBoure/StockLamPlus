# ui/widgets/wholesale_sales/supervisor_override_dialog.py

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.formatting import format_money


class SupervisorOverrideDialog(QDialog):
    """
    Dialogue modal de dérogation de crédit avec authentification par identifiants / PIN superviseur.
    Empêche la validation des ventes à crédit dépassant le plafond sans accord managérial explicite.
    """

    def __init__(
        self,
        parent,
        data_manager,
        client_name: str,
        credit_limit: float,
        current_balance: float,
        document_amount: float,
        projected_balance: float,
        excess_amount: float
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_name = client_name
        self.credit_limit = credit_limit
        self.current_balance = current_balance
        self.document_amount = document_amount
        self.projected_balance = projected_balance
        self.excess_amount = excess_amount

        self.approved = False
        self.supervisor_user = None
        self.override_reason = ""

        self.setWindowTitle("🔒 Autorisation Superviseur - Dépassement Plafond de Crédit")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.resize(560, 460)
        self.setMinimumSize(500, 400)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Alert Header Card
        alert_frame = QFrame()
        alert_frame.setStyleSheet("""
            QFrame {
                background-color: #fef2f2;
                border: 1.5px solid #f87171;
                border-radius: 0px;
                padding: 10px 14px;
            }
        """)
        v_alert = QVBoxLayout(alert_frame)
        v_alert.setContentsMargins(6, 4, 6, 4)
        v_alert.setSpacing(4)

        lbl_alert_title = QLabel("⚠️ BLOCAGE DE CRÉDIT : Plafond Autorisé Dépassé")
        lbl_alert_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;")
        v_alert.addWidget(lbl_alert_title)

        lbl_alert_sub = QLabel(
            f"Le client '{self.client_name}' dépasse son plafond de crédit autorisé. "
            "Une validation de direction / superviseur est obligatoire pour poursuivre cette vente."
        )
        lbl_alert_sub.setWordWrap(True)
        lbl_alert_sub.setStyleSheet("font-size: 12px; color: #7f1d1d;")
        v_alert.addWidget(lbl_alert_sub)
        layout.addWidget(alert_frame)

        # 2. Financial Metrics Details Table/Card
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 8px 12px;
            }
        """)
        m_layout = QVBoxLayout(metrics_frame)
        m_layout.setContentsMargins(8, 6, 8, 6)
        m_layout.setSpacing(6)

        def make_metric_row(label_text, value_text, is_bold=False, color="#1e293b"):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: 12px; color: #475569; {'font-weight: bold;' if is_bold else ''}")
            val = QLabel(value_text)
            val.setStyleSheet(f"font-size: 13px; color: {color}; font-weight: bold;")
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(val)
            return row

        m_layout.addLayout(make_metric_row("Plafond de Crédit Autorisé :", f"{format_money(self.credit_limit)} DA"))
        m_layout.addLayout(make_metric_row("Solde Actuel Dû :", f"{format_money(self.current_balance)} DA"))
        m_layout.addLayout(make_metric_row("Montant Net du Document :", f"{format_money(self.document_amount)} DA"))
        m_layout.addLayout(make_metric_row("Encours Total Projeté :", f"{format_money(self.projected_balance)} DA", is_bold=True, color="#0284c7"))
        m_layout.addLayout(make_metric_row("DÉPASSEMENT / EXCÉDENT :", f"+{format_money(self.excess_amount)} DA", is_bold=True, color="#dc2626"))

        layout.addWidget(metrics_frame)

        # 3. Reason Input
        lbl_reason = QLabel("Motif de la dérogation / Notes * :")
        lbl_reason.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e293b;")
        layout.addWidget(lbl_reason)

        self.txt_reason = QLineEdit()
        self.txt_reason.setPlaceholderText("Ex: Accord verbal gérance, chèque de caution remis, engagement écrit...")
        self.txt_reason.setMinimumHeight(34)
        self.txt_reason.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 8px; font-size: 12px;")
        layout.addWidget(self.txt_reason)

        # 4. Supervisor Credentials Inputs
        cred_frame = QFrame()
        cred_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                padding: 10px;
            }
        """)
        c_layout = QVBoxLayout(cred_frame)
        c_layout.setContentsMargins(6, 4, 6, 4)
        c_layout.setSpacing(6)

        lbl_cred_hdr = QLabel("Authentification du Responsable / Superviseur :")
        lbl_cred_hdr.setStyleSheet("font-size: 12px; font-weight: bold; color: #007572;")
        c_layout.addWidget(lbl_cred_hdr)

        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(8)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Nom d'utilisateur")
        self.input_username.setMinimumHeight(34)
        self.input_username.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 8px; font-size: 12px;")

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Mot de passe / Code PIN")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setMinimumHeight(34)
        self.input_password.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 0px; padding: 4px 8px; font-size: 12px;")
        self.input_password.returnPressed.connect(self._on_authorize_clicked)

        inputs_layout.addWidget(self.input_username, 1)
        inputs_layout.addWidget(self.input_password, 1)
        c_layout.addLayout(inputs_layout)

        layout.addWidget(cred_frame)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancel = QPushButton("❌ Refuser & Annuler")
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

        self.btn_authorize = QPushButton("🔓 Valider l'Autorisation Exceptionnelle")
        self.btn_authorize.setCursor(Qt.PointingHandCursor)
        self.btn_authorize.setMinimumHeight(38)
        self.btn_authorize.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btn_authorize.clicked.connect(self._on_authorize_clicked)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_authorize)

        layout.addLayout(btn_layout)

    def _on_authorize_clicked(self):
        reason = self.txt_reason.text().strip()
        if not reason:
            QMessageBox.warning(self, "Motif Requis", "Veuillez saisir un motif justifiant cette dérogation de crédit.")
            self.txt_reason.setFocus()
            return

        username = self.input_username.text().strip()
        password = self.input_password.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Identifiants Requis", "Veuillez saisir le nom d'utilisateur et le mot de passe / PIN.")
            self.input_username.setFocus()
            return

        try:
            auth_user = self.data_manager.users.authenticate(username, password)
            if not auth_user:
                QMessageBox.critical(self, "Échec d'Authentification", "Nom d'utilisateur ou mot de passe incorrect.")
                self.input_password.clear()
                self.input_password.setFocus()
                return

            # Check supervisor/admin privileges
            role = auth_user.get('Role') or ''
            perms = auth_user.get('Permissions') or {}
            is_supervisor = (
                role in ('Admin', 'Manager')
                or perms.get('override_credit_limit') is True
                or perms.get('admin') is True
                or perms.get('manage_users') is True
            )

            if not is_supervisor:
                QMessageBox.critical(
                    self,
                    "Permissions Insuffisantes",
                    f"L'utilisateur '{username}' n'a pas les droits de superviseur ou d'administrateur nécessaires "
                    "pour approuver un dépassement de crédit."
                )
                return

            self.approved = True
            self.supervisor_user = auth_user
            self.override_reason = reason
            logging.info(
                f"[CREDIT OVERRIDE] Approved by supervisor '{username}' (User ID: {auth_user.get('User_ID')}) "
                f"for client '{self.client_name}'. Reason: {reason}. Excess: {self.excess_amount} DA."
            )
            self.accept()

        except Exception as e:
            logging.error(f"Error validating supervisor override: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la vérification des identifiants :\n{str(e)}")

    def get_override_info(self):
        return {
            'approved': self.approved,
            'supervisor_user': self.supervisor_user,
            'reason': self.override_reason
        }
