# ui/widgets/sales_history/__init__.py
"""
Sales History Module (Historique des Ventes, Factures & Encaissements)
"""

from .sales_history_tab import SalesHistoryTab
from .sale_details_dialog import SaleDetailsDialog
from .pdf_export import export_invoice_to_pdf

__all__ = ["SalesHistoryTab", "SaleDetailsDialog", "export_invoice_to_pdf"]
