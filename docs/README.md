# مجلد التوثيق والدراسات الفنية (`docs`)

يحتوي هذا المجلد على التقارير الفنية، دراسات التصميم المعماري، خطط ترحيل قواعد البيانات، وتوثيق المميزات والتحديثات المنفذة في **GstockSW4**.

## الفهرس والملفات

### 🏗️ دراسات التصميم المعماري لنظام المخزون والمبيعات الثنائي (Warehouse Bulk + Store Shelves / Wholesale vs Retail)
- **[`architecture_depot_rayon_gros_detail.md`](file:///D:/git/GstockSW4/docs/architecture_depot_rayon_gros_detail.md)**: وثيقة التحليل والتصميم المعماري الشامل للانتقال إلى نظام المخزون ثنائي المستوى (مستودع الجملة الكبير والتخزين + رفوف المتجر ومعرض التجزئة).
- **[`database_migration_plan_gros_detail.md`](file:///D:/git/GstockSW4/docs/database_migration_plan_gros_detail.md)**: المخطط الهيكلي لقاعدة البيانات (DDL)، الجداول الجديدة (`Store_Shelf_Inventory`, `Internal_Shelf_Transfers`)، وسيناريو ترحيل الأرصدة القائمة.
- **[`ui_ux_redesign_inventory_sales.md`](file:///D:/git/GstockSW4/docs/ui_ux_redesign_inventory_sales.md)**: دليل تصميم وتطوير واجهات المستخدم المحدثة والجديدة (واجهة المستودع الكبير، واجهة بيع الجملة B2B، واجهة POS التجزئة، وشاشة تزويد الرفوف).

### 📱 تقارير وتوثيق الميزات السابقة والترحيل
- `mobile_inventory_scanner.md`: توثيق تطبيق الموبايل Flutter للماسح الضوئي والجرد الميداني.
- `pos-migration-verification.md`: تقرير التحقق من ترحيل وتكامل نقطة البيع POS.
- `stocklam_feature_gap_report.md`: تقرير تحليل الفوارق والميزات بين StockLam و GstockSW4.
- `stocklam_migration_*.md`: سجلات مراحل ترحيل ميزات StockLam التاريخية.
