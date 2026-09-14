# ui/widgets/sales/invoice_payment_dialog.py

import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDateEdit, QDoubleSpinBox, QLineEdit, QPushButton,
    QFrame, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from ui.formatting import format_money


class InvoicePaymentDialog(QDialog):
    """
    Dialogue d'encaissement et de règlement pour une facture de vente (POS ou Vente en Gros).
    Enregistre le règlement dans Client_Payments et met à jour le statut de la facture.
    """

    def __init__(self, data_manager, invoice_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.invoice_data = invoice_data
        
        self.invoice_id = invoice_data.get('Invoice_ID')
        self.client_id = invoice_data.get('Client_ID')
        self.total_ttc = float(invoice_data.get('Total_Amount_TTC') or 0.0)
        self.paid_amount = float(invoice_data.get('Paid_Amount') or 0.0)
        self.remaining_balance = max(0.0, self.total_ttc - self.paid_amount)
        
        doc_ref = invoice_data.get('Invoice_No') or f"#{self.invoice_id}"
        self.setWindowTitle(f"Encaisser Paiement - Facture {doc_ref}")
        self.resize(500, 460)
        self._init_ui()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header Title
        lbl_title = QLabel("💳 Enregistrement d'un Règlement Client")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f766e;")
        layout.addWidget(lbl_title)

        # Summary Group
        summary_group = QGroupBox("Détails de la Facture")
        summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #f8fafc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
        """)
        summary_layout = QFormLayout(summary_group)
        summary_layout.setSpacing(6)
        summary_layout.setContentsMargins(12, 12, 12, 12)

        client_name = self.invoice_data.get('Client_Name') or "Client Comptoir"
        doc_ref = self.invoice_data.get('Invoice_No') or f"#{self.invoice_id}"
        inv_date = str(self.invoice_data.get('Invoice_Date') or self.invoice_data.get('Event_Date') or "-")
        due_date = str(self.invoice_data.get('Due_Date') or "-")

        summary_layout.addRow("<b>Client :</b>", QLabel(client_name))
        summary_layout.addRow("<b>Facture N° :</b>", QLabel(doc_ref))
        summary_layout.addRow("<b>Date Facture :</b>", QLabel(inv_date))
        summary_layout.addRow("<b>Date d'Échéance :</b>", QLabel(due_date))
        summary_layout.addRow("<b>Montant Total TTC :</b>", QLabel(f"{format_money(self.total_ttc)} DA"))
        summary_layout.addRow("<b>Déjà Réglé :</b>", QLabel(f"{format_money(self.paid_amount)} DA"))

        lbl_balance = QLabel(f"{format_money(self.remaining_balance)} DA")
        lbl_balance.setStyleSheet("font-size: 14px; font-weight: bold; color: #dc2626;")
        summary_layout.addRow("<b>Reste à Payer :</b>", lbl_balance)

        layout.addWidget(summary_group)

        # Form Group
        form_group = QGroupBox("Paramètres du Paiement")
        form_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
        """)
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(12, 12, 12, 12)

        # Date de paiement
        self.edit_date = QDateEdit(QDate.currentDate())
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("Date de règlement :", self.edit_date)

        # Montant
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999999.0)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSingleStep(100.0)
        self.spin_amount.setSuffix(" DA")
        self.spin_amount.setValue(self.remaining_balance if self.remaining_balance > 0 else self.total_ttc)
        self.spin_amount.setStyleSheet("font-size: 13px; font-weight: bold; color: #047857; min-height: 28px;")
        form_layout.addRow("Montant versé :", self.spin_amount)

        # Mode de paiement
        self.cb_method = QComboBox()
        methods = [
            ("Espèces", "Espèce"),
            ("Chèque", "Chèque"),
            ("Virement bancaire", "Virement"),
            ("Versement bancaire", "Versement"),
            ("Carte bancaire", "Carte")
        ]
        for label, val in methods:
            self.cb_method.addItem(label, val)
        form_layout.addRow("Mode de paiement :", self.cb_method)

        # Reference
        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Ex: N° Chèque, Référence virement...")
        form_layout.addRow("Référence / N° Pièce :", self.edit_ref)

        # Notes
        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Remarques ou observations...")
        form_layout.addRow("Observations :", self.edit_notes)

        layout.addWidget(form_group)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("💾 Valider le Règlement")
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #115e59;
            }
        """)
        self.btn_submit.clicked.connect(self._validate_and_submit)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_submit)

        layout.addLayout(btn_layout)

    def _validate_and_submit(self):
        amount = self.spin_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Veuillez saisir un montant supérieur à zéro.")
            return

        if not self.client_id:
            QMessageBox.warning(
                self, "Client non défini",
                "Cette facture n'est pas rattachée à un compte client spécifique.\n"
                "Le règlement direct est réservé aux clients enregistrés."
            )
            return

        pay_date = self.edit_date.date().toString("yyyy-MM-dd")
        method = self.cb_method.currentData()
        ref = self.edit_ref.text().strip() or None
        notes = self.edit_notes.text().strip() or None
        user_id = self._current_user_id()

        try:
            payment_id = self.data_manager.client_payments.add_payment(
                client_id=self.client_id,
                payment_date=pay_date,
                amount=amount,
                payment_method=method,
                reference=ref,
                notes=notes,
                invoice_id=self.invoice_id,
                user_id=user_id
            )

            if payment_id:
                QMessageBox.information(
                    self, "Succès",
                    f"Règlement de {format_money(amount)} DA enregistré avec succès (Réf: #{payment_id})."
                )
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'enregistrement du règlement en base de données.")
        except Exception as e:
            logging.error(f"Error saving invoice payment: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement: {e}")
