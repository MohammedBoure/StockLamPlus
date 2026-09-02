# ui/widgets/inventory/tabs_batches/_table.py
"""
عرض بيانات الجدول: التحميل الكسول، الفرز، تلوين الصفوف
"""

import logging
import json

from PySide6.QtWidgets import QTableWidgetItem, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from ui.formatting import format_money, format_quantity


# ---------------------------------------------------------------------------
# أيقونات مخصصة
# ---------------------------------------------------------------------------
from ui.icons import get_reclamation_icon

# ---------------------------------------------------------------------------
# مساعد بناء خلية والتحقق من الصلاحيات
# ---------------------------------------------------------------------------

def _make_item(val, align=Qt.AlignCenter, color=None, font=None, bg_color=None):
    from PySide6.QtGui import QBrush
    s_val = str(val) if val is not None else ""
    it = QTableWidgetItem(s_val)
    it.setTextAlignment(align)
    if color:
        it.setForeground(color)
    if bg_color:
        it.setBackground(QBrush(bg_color))
    if font:
        it.setFont(font)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _can_view_financials(widget):
    """دالة تتحقق مما إذا كان المستخدم يملك صلاحية رؤية القيم المالية بشكل آمن"""
    try:
        # 1. محاولة جلب المستخدم من النافذة الرئيسية مباشرة
        main_window = widget.window()
        user = getattr(main_window, 'current_user', None)

        # 2. إذا لم يعثر عليه (الواجهة قيد البناء ولم تدمج بعد بالنافذة)
        # نقوم بالبحث صعوداً في شجرة المكونات الآباء
        if user is None:
            parent = widget.parent()
            while parent:
                if hasattr(parent, 'current_user'):
                    user = parent.current_user
                    break
                parent = parent.parent()

        # 3. إذا لم نعثر على المستخدم في أي مكان
        if not user:
            return False

        perms = user.get('Permissions', {})

        # معالجة الصلاحيات
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except json.JSONDecodeError:
                perms = {}

        if isinstance(perms, list):
            return "tab_inv_financials" in perms
        elif isinstance(perms, dict):
            return perms.get("tab_inv_financials", False)

        return False
    except Exception as e:
        logging.error(f"Error checking financial permissions: {e}")
        return False


# ---------------------------------------------------------------------------
# التحميل الكسول (Lazy Loading / Infinite Scroll)
# ---------------------------------------------------------------------------

def on_scroll_value_changed(self, value):
    """تحميل المزيد عند الاقتراب من قاع الجدول"""
    bar = self.table.verticalScrollBar()
    if value >= bar.maximum() - 20:
        load_more_data(self)


def load_more_data(self):
    """إضافة الدفعة التالية من الصفوف للجدول"""
    total = len(self.filtered_data)
    if self.loaded_count >= total:
        return

    start = self.loaded_count
    end   = min(start + self.batch_size, total)
    _append_rows(self, self.filtered_data[start:end])
    self.loaded_count = end
    self.lbl_count_info.setText(f"Affichage: {self.loaded_count} / {total}")


def _append_rows(self, chunk):
    """إضافة chunk من الصفوف إلى نهاية الجدول"""
    hide_fin = not _can_view_financials(self)
    start_row = self.table.rowCount()

    for i, b in enumerate(chunk):
        r = start_row + i
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    for col in (2, 3, 4, 5, 18, 19, 20):
        self.table.setColumnHidden(col, hide_fin)


# ---------------------------------------------------------------------------
# عرض صفحة كاملة (مع حساب المجموع)
# ---------------------------------------------------------------------------

def populate_table(self, data):
    """عرض شريحة محددة مع حساب المجموع الكلي من filtered_data"""
    self.table.setSortingEnabled(False)
    self.table.setRowCount(0)

    hide_fin = not _can_view_financials(self)

    # حساب المجموع من كامل القائمة المفلترة
    total_value = 0.0
    if not hide_fin:
        for b in self.filtered_data:
            try:
                qty = float(b.get('Quantity_Current', 0))
                if qty > 0:
                    p = float(b.get('Unit_Price_Received', 0))
                    d = float(b.get('Discount_Percent', 0)) / 100.0
                    t = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                    total_value += qty * p * (1 - d) * (1 + t)
            except Exception:
                pass

    for r, b in enumerate(data):
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    self.table.setSortingEnabled(False)
    for col in (2, 3, 4, 5, 18, 19, 20):
        self.table.setColumnHidden(col, hide_fin)

    if hide_fin:
        self.lbl_total_value.hide()
    else:
        self.lbl_total_value.show()
        self.lbl_total_value.setText(f"💰 Total Filtré : {format_money(total_value, 'DA')}")


def _fill_row(table, r, b, hide_fin):
    """ملء صف واحد بالبيانات مع الأولوية للأسعار الرئيسية بعد المنتج والكمية، وتأخير أسعار 2 و 3 و 4 قبل الشكاوى"""
    qty = float(b.get('Quantity_Current', 0))
    raw_note = b.get('Reception_Note')
    reclamation = str(raw_note).strip() if raw_note is not None else ""
    if reclamation.lower() in ("none", "null"):
        reclamation = ""

    bg_color = QColor("#ffe4cd") if reclamation else None

    prod_name = b.get('Product_Name', '---')

    # 0. Désignation Produit
    prod_item = _make_item(
        prod_name,
        Qt.AlignLeft | Qt.AlignVCenter,
        bg_color=bg_color
    )
    prod_item.setData(Qt.UserRole, b)
    table.setItem(r, 0, prod_item)

    # 1. Stock (Actuel)
    table.setItem(r, 1, _make_item(
        format_quantity(qty),
        color=QColor("#27ae60"),
        font=QFont("", -1, QFont.Bold),
        bg_color=bg_color
    ))

    # تطبيق الفلتر المالي على الأسعار الرئيسية ذات الأولوية الأولى (2 إلى 5)
    if not hide_fin:
        p  = float(b.get('Unit_Price_Received', 0) or 0)
        d  = float(b.get('Discount_Percent', 0) or 0) / 100.0
        t  = float(b.get('Tax_Rate_Percent', 0) or 0) / 100.0
        p_ttc = p * (1 - d) * (1 + t)
        lv = qty * p_ttc
        sv1 = float(b.get('Selling_Price_HT') or 0)

        # 2. Prix U. HT
        table.setItem(r, 2, _make_item(format_money(p), bg_color=bg_color))
        # 3. Prix U. TTC
        table.setItem(r, 3, _make_item(format_money(p_ttc), bg_color=bg_color))
        # 4. Valeur (DA)
        table.setItem(r, 4, _make_item(format_money(lv), bg_color=bg_color))
        # 5. Prix Vente 1
        table.setItem(r, 5, _make_item(format_money(sv1), bg_color=bg_color))
    else:
        for col in range(2, 6):
            table.setItem(r, col, _make_item('', bg_color=bg_color))

    # 6. N° Lot
    table.setItem(r, 6,  _make_item(b.get('Lot_Number', '---'), bg_color=bg_color))
    # 7. Date Exp.
    table.setItem(r, 7,  _make_item(str(b.get('Expiry_Date', ''))[:10], bg_color=bg_color))
    # 8. Qté Init.
    table.setItem(r, 8,  _make_item(format_quantity(b.get('Quantity_Initial', 0)), bg_color=bg_color))
    # 9. Code-Barres
    table.setItem(r, 9,  _make_item(
        b.get('Internal_Barcode') or b.get('Barcode'),
        bg_color=bg_color
    ))
    # 10. Code Ext
    table.setItem(r, 10, _make_item(b.get('External_Barcode') or '---', bg_color=bg_color))
    # 11. Emplacement
    table.setItem(r, 11, _make_item(b.get('Location_Name', '---'), bg_color=bg_color))

    # 12. Famille
    table.setItem(r, 12, _make_item(b.get('Family_Name', '---'), bg_color=bg_color))
    # 13. Marque
    table.setItem(r, 13, _make_item(b.get('Manuf_Name', '---'), bg_color=bg_color))
    # 14. Automate
    table.setItem(r, 14, _make_item(b.get('Automate_Name', '---'), bg_color=bg_color))
    # 15. Fournisseur
    table.setItem(r, 15, _make_item(b.get('Supplier_Name', '---'), bg_color=bg_color))
    # 16. Ref PO
    table.setItem(r, 16, _make_item(str(b.get('PO_ID') or '---'), bg_color=bg_color))
    # 17. Date Entrée
    table.setItem(r, 17, _make_item(
        str(b.get('Date_Received') or b.get('Created_At', ''))[:10],
        bg_color=bg_color
    ))

    # 18-20. Prix Vente 2, 3, 4 (في نهاية الجدول قبل الشكاوى)
    if not hide_fin:
        sv2 = float(b.get('Selling_Price_HT_2') or 0)
        sv3 = float(b.get('Selling_Price_HT_3') or 0)
        sv4 = float(b.get('Selling_Price_HT_4') or 0)
        table.setItem(r, 18, _make_item(format_money(sv2), bg_color=bg_color))
        table.setItem(r, 19, _make_item(format_money(sv3), bg_color=bg_color))
        table.setItem(r, 20, _make_item(format_money(sv4), bg_color=bg_color))
    else:
        for col in (18, 19, 20):
            table.setItem(r, col, _make_item('', bg_color=bg_color))

    # 21. Réclamation
    rec_item = _make_item(reclamation, bg_color=bg_color)
    if reclamation:
        rec_item.setIcon(get_reclamation_icon())
    table.setItem(r, 21, rec_item)

    # 22. Groupe Vente (Priorité Caisse)
    pos_grp = b.get('POS_Priority_Group')
    grp_str = f"⭐ {pos_grp}" if pos_grp else "---"
    grp_item = _make_item(grp_str, align=Qt.AlignCenter, bg_color=bg_color)
    if pos_grp:
        grp_item.setForeground(QColor("#007572"))
        grp_item.setFont(QFont("", -1, QFont.Bold))
    table.setItem(r, 22, grp_item)

    # تعيين الهيدر العمودي (رقم الصف وأيقونة الشكوى الدائرية إذا وجدت)
    v_header_item = QTableWidgetItem(str(r+1))
    if reclamation:
        v_header_item.setIcon(get_reclamation_icon())
        v_header_item.setToolTip(f"Réclamation: {reclamation}")
        v_header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    else:
        v_header_item.setTextAlignment(Qt.AlignCenter)
    table.setVerticalHeaderItem(r, v_header_item)


# ---------------------------------------------------------------------------
# الفرز
# ---------------------------------------------------------------------------

COL_MAP = {
    0: 'Product_Name',          1: 'Quantity_Current',
    2: 'Unit_Price_Received',   3: 'Unit_Price_Received_TTC',
    4: 'Total_Value',           5: 'Selling_Price_HT',
    6: 'Lot_Number',            7: 'Expiry_Date',
    8: 'Quantity_Initial',      9: 'Internal_Barcode',
    10: 'External_Barcode',     11: 'Location_Name',
    12: 'Family_Name',          13: 'Manuf_Name',
    14: 'Automate_Name',        15: 'Supplier_Name',
    16: 'PO_ID',                17: 'Date_Received',
    18: 'Selling_Price_HT_2',   19: 'Selling_Price_HT_3',
    20: 'Selling_Price_HT_4',   21: 'Reception_Note'
}

NUMERIC_COLS = {1, 2, 3, 4, 5, 8, 18, 19, 20}
DATE_COLS    = {7, 17}


def _sort_key(col_index, item):
    if col_index == 4:
        try:
            qty = float(item.get('Quantity_Current', 0))
            p  = float(item.get('Unit_Price_Received', 0))
            d  = float(item.get('Discount_Percent', 0)) / 100.0
            t  = float(item.get('Tax_Rate_Percent', 0)) / 100.0
            return qty * p * (1 - d) * (1 + t)
        except Exception:
            return 0.0
    elif col_index == 3:
        try:
            p  = float(item.get('Unit_Price_Received', 0))
            d  = float(item.get('Discount_Percent', 0)) / 100.0
            t  = float(item.get('Tax_Rate_Percent', 0)) / 100.0
            return p * (1 - d) * (1 + t)
        except Exception:
            return 0.0
    elif col_index in NUMERIC_COLS:
        try:
            return float(item.get(COL_MAP.get(col_index), 0) or 0)
        except Exception:
            return 0.0

    key_name = COL_MAP.get(col_index)
    val = item.get(key_name)

    if val is None:
        return -1 if col_index in NUMERIC_COLS else ""

    if col_index in NUMERIC_COLS:
        try:
            return float(val)
        except Exception:
            return 0.0
    elif col_index in DATE_COLS:
        return str(val)[:10]
    else:
        return str(val).lower()


def on_header_clicked(self, col_index):
    """عكس الاتجاه أو تعيين عمود جديد ثم تطبيق الفرز"""
    if self.current_sort_col == col_index:
        self.current_sort_asc = not self.current_sort_asc
    else:
        self.current_sort_col = col_index
        self.current_sort_asc = True
    apply_sorting(self)


def apply_sorting(self):
    """فرز filtered_data كاملاً ثم إعادة العرض من الصفر"""
    if self.current_sort_col == -1:
        return

    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()

    try:
        col = self.current_sort_col
        asc = self.current_sort_asc

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(
            col,
            Qt.AscendingOrder if asc else Qt.DescendingOrder
        )

        key_name = COL_MAP.get(col)
        if not key_name and col not in (3, 4):
            return

        self.filtered_data.sort(
            key=lambda item: _sort_key(col, item),
            reverse=not asc
        )

        # إعادة العرض من الصفر (lazy loading)
        self.table.setRowCount(0)
        self.loaded_count = 0
        load_more_data(self)

    except Exception as e:
        logging.error(f"Sorting Error: {e}")
    finally:
        QApplication.restoreOverrideCursor()
