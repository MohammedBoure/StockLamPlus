# ui/widgets/sales_history/pdf_export.py

import os
from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QFileDialog

from ui.formatting import format_money, format_quantity

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def export_invoice_to_pdf(data_manager, invoice_data, parent_widget):
    """
    Exporte une facture de vente au format PDF A4 avec ReportLab.
    """
    print("\n" + "🚀" * 10 + " PDF EXPORT START " + "🚀" * 10)

    if not HAS_REPORTLAB:
        QMessageBox.warning(parent_widget, "Erreur", "La bibliothèque 'reportlab' est manquante.")
        return

    try:
        settings = data_manager.company_settings.get_settings()
        if os.path.exists("config.json"):
            import json
            with open("config.json", "r", encoding="utf-8") as f:
                local_settings = json.load(f)
                for k, v in local_settings.items():
                    if k not in settings or not settings[k]:
                        settings[k] = v
    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur", f"Configuration error: {str(e)}")
        return

    try:
        invoice_id = invoice_data['Invoice_ID']
        details_data = data_manager.sales.get_invoice_details_with_profit(invoice_id)
        client_name = invoice_data.get('Client_Name') or 'Vente comptoir'
    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur BD", str(e))
        return

    document_title = "FACTURE"

    try:
        raw_date = str(invoice_data.get('Invoice_Date', ''))
        year_val = raw_date.split('-')[0] if '-' in raw_date else str(datetime.now().year)
        formatted_ref = invoice_data.get('Invoice_No') or f"{year_val}/{int(invoice_id):03d}"
    except Exception:
        formatted_ref = str(invoice_id)

    client_clean = str(client_name).replace(" ", "_")
    safe_ref_for_filename = formatted_ref.replace("/", "-")
    default_name = f"Facture_{client_clean}_{safe_ref_for_filename}.pdf"

    path, _ = QFileDialog.getSaveFileName(parent_widget, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
    if not path:
        return

    try:
        PAGE_WIDTH, PAGE_HEIGHT = A4
        default_color = settings.get('theme_color', '#0b666a')
        primary_color = colors.HexColor(default_color)
        banner_h_cm = settings.get('banner_height_cm', 4.8)
        table_start_y_cm = settings.get('table_start_y_cm', 9.5)

        doc = SimpleDocTemplate(
            path, pagesize=A4, rightMargin=40, leftMargin=40,
            topMargin=table_start_y_cm * cm, bottomMargin=50
        )

        elements = []
        styles = getSampleStyleSheet()
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')

        lab_name = settings.get('lab_name', 'Laboratoire')
        lab_addr = settings.get('lab_address', '')
        lab_nif = settings.get('lab_nif', '')
        lab_rc = settings.get('lab_rc', '')

        lab_info_lines = [
            f"<font size=14 color='{default_color}'><b>{document_title} N°: {formatted_ref}</b></font><br/>",
            f"<font size=10><b>{lab_name}</b></font>"
        ]

        def clean_str(val):
            if not val:
                return ""
            v = str(val).replace('\n', '').replace('\r', '').strip()
            if v.lower() in ["none", "n/a", "null", "nan", "-", "", "."]:
                return ""
            return v

        if clean_str(lab_addr):
            lab_info_lines.append(f"<font size=9>{clean_str(lab_addr)}</font>")
        if clean_str(lab_nif):
            lab_info_lines.append(f"<font size=9>NIF : {clean_str(lab_nif)}</font>")
        if clean_str(lab_rc):
            lab_info_lines.append(f"<font size=9>RC : {clean_str(lab_rc)}</font>")

        bank_name = settings.get('bank_name', '')
        bank_acc = settings.get('bank_acc', '')

        if clean_str(bank_name):
            lab_info_lines.append(f"<font size=9>Banque : {clean_str(bank_name)}</font>")
        if clean_str(bank_acc):
            lab_info_lines.append(f"<font size=9>RIB : {clean_str(bank_acc)}</font>")

        bon_date = raw_date
        lab_info_lines.append("")
        if bon_date:
            lab_info_lines.append(f"<font size=9>Date : {bon_date}</font>")
        lab_info_lines.append(f"<font size=9>Date d'édition : {current_time}</font>")

        left_text_top = "<br/>".join(lab_info_lines)

        dest_label = 'Client :'
        p_name_clean = str(client_name).replace('\n', '').replace('\r', '').strip()
        right_text_lines = [
            f"<b>{dest_label}</b>",
            "",
            f"<font size=11><b>{p_name_clean}</b></font>",
        ]

        right_text = "<br/>".join(right_text_lines)

        def draw_header_compact(canvas, doc):
            canvas.saveState()
            img_x = settings.get('banner_img_x_cm', 0.0) * cm
            img_w = settings.get('banner_img_w_cm', 21.0) * cm
            img_h = settings.get('banner_img_h_cm', 4.8) * cm
            y_offset = settings.get('banner_img_y_cm', 0.2) * cm
            img_y = PAGE_HEIGHT - img_h - y_offset

            img_bytes = data_manager.company_settings.get_banner_image()
            if img_bytes:
                from reportlab.lib.utils import ImageReader
                import io
                img = ImageReader(io.BytesIO(img_bytes))
                canvas.drawImage(img, img_x, img_y, width=img_w, height=img_h)
            else:
                canvas.setStrokeColor(colors.red)
                canvas.rect(img_x, img_y, img_w, img_h, stroke=1)

            total_h_cm = settings.get('banner_height_cm', 4.8) * cm
            top_y = PAGE_HEIGHT - total_h_cm - 0.5 * cm

            left_p = Paragraph(left_text_top, styles["Normal"])
            left_w, left_h = left_p.wrap(9.5 * cm, 10.0 * cm)
            left_p.drawOn(canvas, doc.leftMargin, top_y - left_h)

            dest_x = settings.get('dest_box_x_cm', 11.5) * cm
            dest_y_abs = PAGE_HEIGHT - settings.get('dest_box_y_cm', 6.0) * cm
            dest_w = settings.get('dest_box_w_cm', 8.0) * cm

            right_p = Paragraph(right_text, styles["Normal"])
            right_w, right_h = right_p.wrap(dest_w - 0.5 * cm, 10.0 * cm)
            box_h = max(right_h + 1.0 * cm, 2.5 * cm)

            canvas.setFillColor(colors.HexColor("#f8f9fa"))
            canvas.setStrokeColor(colors.lightgrey)
            canvas.setLineWidth(0.5)
            canvas.rect(dest_x, dest_y_abs - box_h, dest_w, box_h, fill=1, stroke=1)

            right_p.drawOn(canvas, dest_x + 0.25 * cm, dest_y_abs - right_h - 0.5 * cm)
            canvas.restoreState()

        has_remise = any(float(item.get('Discount_Percent', 0)) > 0 for item in details_data)
        has_tva = any(float(item.get('TVA_Percent', 0)) > 0 for item in details_data)

        header_row = ["Désignation", "Qté", "Prix U. HT"]
        if has_remise:
            header_row.append("Remise")
        if has_tva:
            header_row.append("TVA")
        header_row.append("Total TTC")

        table_data = [header_row]

        for item in details_data:
            qty = float(item.get('Qty_Sold', 0))
            price = float(item.get('Unit_Price_HT', 0))
            remise = float(item.get('Discount_Percent', 0))
            tva = float(item.get('TVA_Percent', 0))
            line_val_ttc = float(item.get('Line_Total_TTC', 0))

            p_info = f"<b>{item.get('Product_Name', '-')}</b>"

            row = [
                Paragraph(p_info, styles["Normal"]),
                format_quantity(qty),
                f"{price:,.2f}"
            ]

            if has_remise:
                row.append(f"{remise}%" if remise > 0 else "-")
            if has_tva:
                row.append(f"{tva}%" if tva > 0 else "-")

            row.append(f"{line_val_ttc:,.2f}")
            table_data.append(row)

        col_widths = [8.0 * cm, 1.5 * cm, 2.5 * cm]
        if has_remise:
            col_widths.append(1.5 * cm)
        else:
            col_widths[0] += 1.5 * cm

        if has_tva:
            col_widths.append(1.5 * cm)
        else:
            col_widths[0] += 1.5 * cm
        col_widths.append(3.0 * cm)

        items_table = Table(table_data, colWidths=col_widths)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ALIGN', (1, 0), (len(header_row) - 1, -1), 'CENTER'),
            ('ALIGN', (len(header_row) - 1, 0), (len(header_row) - 1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(items_table)

        tot_ht_net = float(invoice_data.get('Total_Amount_HT', 0))
        tot_discount = float(invoice_data.get('Total_Discount', 0))
        tot_tva = float(invoice_data.get('Total_TVA', 0))
        tot_ttc = float(invoice_data.get('Total_Amount_TTC', 0))

        tot_ht_gross = tot_ht_net + tot_discount

        tot_data = [
            ["Total HT :", f"{tot_ht_gross:,.2f} DA"],
        ]

        if has_remise or tot_discount > 0:
            tot_data.append(["Remise :", f"{tot_discount:,.2f} DA"])
        if has_tva or tot_tva > 0:
            tot_data.append(["Total TVA :", f"{tot_tva:,.2f} DA"])

        tot_data.append(["TOTAL TTC À PAYER :", f"{tot_ttc:,.2f} DA"])

        payment_lines = invoice_data.get("payments") or []
        if not payment_lines and hasattr(data_manager, "pos_features"):
            payment_lines = data_manager.pos_features.get_invoice_payments(invoice_id)
        if payment_lines:
            for payment in payment_lines:
                method = payment.get("Payment_Method") or payment.get("method") or "-"
                amount = float(payment.get("Amount") or payment.get("amount") or 0)
                reference = payment.get("Reference") or payment.get("reference")
                label = f"Paiement {method}"
                if reference:
                    label += f" ({reference})"
                tot_data.append([label + " :", f"{amount:,.2f} DA"])
                change = float(payment.get("Change_Amount") or payment.get("change") or 0)
                if change > 0:
                    tot_data.append(["Rendu :", f"{change:,.2f} DA"])
        else:
            tot_data.append(["Paiement :", str(invoice_data.get("Payment_Method") or "-")])
        tot_table = Table(tot_data, colWidths=[14.0 * cm, 4.0 * cm])

        tot_style = [
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, len(tot_data) - 1), (1, len(tot_data) - 1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, len(tot_data) - 1), (1, len(tot_data) - 1), colors.HexColor("#f4f6f6")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]

        tot_table.setStyle(TableStyle(tot_style))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(tot_table)

        doc.build(elements, onFirstPage=draw_header_compact, onLaterPages=draw_header_compact)

        if os.name == 'nt':
            os.startfile(path)
        else:
            os.system(f'xdg-open "{path}"')

    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur PDF", f"Échec de création du PDF: {str(e)}")

    print("=" * 50 + " PDF EXPORT END " + "=" * 50)
