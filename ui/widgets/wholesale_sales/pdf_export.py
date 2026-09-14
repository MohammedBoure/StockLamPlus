# ui/widgets/wholesale_sales/pdf_export.py

import os
import logging
from PySide6.QtWidgets import QMessageBox, QFileDialog

from ui.formatting import format_money

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def export_wholesale_document_pdf(
    data_manager,
    invoice_id,
    doc_no,
    doc_type,
    client,
    cart_items,
    order_date_str,
    due_date_str,
    parent_widget=None
):
    """
    Génère et exporte un document commercial de vente en gros (Facture, BL, BC, Devis)
    au format PDF A4 professionnel via ReportLab.
    """
    if not HAS_REPORTLAB:
        if parent_widget:
            QMessageBox.warning(parent_widget, "PDF", "La bibliothèque ReportLab n'est pas installée.")
        return

    safe_doc_no = str(doc_no or "DOC").replace('/', '_')
    default_filename = f"{doc_type.replace(' ', '_')}_{safe_doc_no}.pdf"
    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, f"Enregistrer le document {doc_type}", default_filename, "Fichiers PDF (*.pdf)"
    )
    if not file_path:
        return

    try:
        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm
        )
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        title_style = ParagraphStyle(
            'WholesaleTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#007572'),
            spaceAfter=6,
            alignment=1
        )
        story = []

        # En-tête Paramètres Société
        company_settings = {}
        if hasattr(data_manager, 'company_settings'):
            company_settings = data_manager.company_settings.get_settings()

        company_name = company_settings.get('Company_Name') or "ENTREPRISE GROS & DISTRIBUTION"
        company_phone = company_settings.get('Phone') or ""
        company_address = company_settings.get('Address') or ""

        header_html = f"<b>{company_name}</b><br/>{company_address}<br/>Tél: {company_phone}"
        story.append(Paragraph(header_html, ParagraphStyle('HeaderM', parent=normal_style, fontSize=9, textColor=colors.HexColor('#475569'))))
        story.append(Spacer(1, 10))

        # Titre et Référence Document
        story.append(Paragraph(f"{doc_type.upper()} N° {doc_no}", title_style))
        story.append(Paragraph(f"Date : <b>{order_date_str}</b> | Échéance : <b>{due_date_str}</b>", ParagraphStyle('Sub', parent=normal_style, alignment=1, fontSize=10)))
        story.append(Spacer(1, 12))

        # Fiche Client B2B
        client = client or {}
        c_info = [
            [Paragraph(f"<b>Client B2B :</b> {client.get('Client_Name', '-')}", normal_style),
             Paragraph(f"<b>Catégorie :</b> {client.get('Price_Tier', 'Prix_1')}", normal_style)],
            [Paragraph(f"<b>Contact :</b> {client.get('Contact_Person', '-')}", normal_style),
             Paragraph(f"<b>Téléphone :</b> {client.get('Phone', '-')}", normal_style)],
            [Paragraph(f"<b>Ville :</b> {client.get('City', '-')}", normal_style),
             Paragraph(f"<b>NIF / RC :</b> {client.get('Tax_ID_Number', '-')} / {client.get('Commercial_Reg_No', '-')}", normal_style)]
        ]
        t_c = Table(c_info, colWidths=[9.5 * cm, 8.5 * cm])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_c)
        story.append(Spacer(1, 14))

        # Tableau des Lignes d'Articles
        grid_data = [["Désignation Produit", "Lot", "Péremp.", "Prix Unit. HT", "Qté", "Remise", "Total HT", "TTC"]]
        tot_ht = 0.0
        tot_ttc = 0.0
        for it in cart_items:
            p = it['unit_price_ht']
            q = it['qty_sold']
            d = it['discount_percent']
            tva = it['tva_percent']
            l_ht = p * q * (1 - d / 100.0)
            l_ttc = l_ht * (1 + tva / 100.0)
            tot_ht += l_ht
            tot_ttc += l_ttc
            grid_data.append([
                it['product_name'],
                it['lot_number'],
                it['expiry_date'],
                f"{format_money(p)}",
                f"{q:.2f}",
                f"{d:.1f}%" if d > 0 else "-",
                f"{format_money(l_ht)}",
                f"{format_money(l_ttc)}"
            ])

        t_grid = Table(grid_data, colWidths=[5.5 * cm, 2.2 * cm, 2.0 * cm, 2.3 * cm, 1.5 * cm, 1.5 * cm, 2.3 * cm, 2.3 * cm], repeatRows=1)
        t_grid.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007572')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(t_grid)
        story.append(Spacer(1, 14))

        # Récapitulatif Financier
        tot_data = [
            ["Total Brut HT :", f"{format_money(tot_ht)} DA"],
            ["Total TVA :", f"{format_money(tot_ttc - tot_ht)} DA"],
            ["NET À PAYER TTC :", f"{format_money(tot_ttc)} DA"]
        ]
        t_tot = Table(tot_data, colWidths=[5 * cm, 4 * cm])
        t_tot.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 10),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e6f4f1')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#007572')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))

        t_wrap = Table([["", t_tot]], colWidths=[10 * cm, 9 * cm])
        t_wrap.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(t_wrap)
        story.append(Spacer(1, 25))

        # Cachets & Signatures
        sign_data = [
            [Paragraph("<b>Visa & Cachet de l'Entreprise :</b>", normal_style),
             Paragraph("<b>Bon pour Accord & Réception Client :</b>", normal_style)]
        ]
        t_sign = Table(sign_data, colWidths=[9.5 * cm, 9.5 * cm])
        story.append(t_sign)

        doc.build(story)
        if os.name == 'nt':
            os.startfile(file_path)
        else:
            import subprocess
            subprocess.call(['xdg-open', file_path])

    except Exception as e:
        logging.error(f"Wholesale PDF Error: {e}", exc_info=True)
        if parent_widget:
            QMessageBox.critical(parent_widget, "Erreur PDF", f"Impossible d'exporter le document PDF :\n{e}")
