# ui/widgets/wholesale_sales/__init__.py
"""
Wholesale Sales Module (Vente en Gros B2B)
"""

from .wholesale_sales_tab import WholesaleSalesTab
from .pdf_export import export_wholesale_document_pdf

__all__ = ["WholesaleSalesTab", "export_wholesale_document_pdf"]
