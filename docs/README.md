# مجلد التوثيق والدراسات الفنية (`docs`)

يحتوي هذا المجلد على التقارير الفنية، دراسات التصميم المعماري، خطط ترحيل قواعد البيانات، وتوثيق المميزات والتحديثات المنفذة في **GstockSW4**.

## الفهرس والملفات

### 🏗️ دراسات التصميم المعماري لنظام المخزون الموحد (معمارية رؤية المواقع والتفكيك الداخلي)
- **[`architecture_depot_rayon_gros_detail.md`](file:///D:/git/GstockSW4/docs/architecture_depot_rayon_gros_detail.md)**: وثيقة التصميم المعماري الموحد لإدارة المخزون متعدد المستويات عبر جدول الدفعات الموحد `Inventory_Batches` ومنظومة رؤية المواقع (Private vs Public)، وشرح آليتي النقل المباشر (Direct) والتفكيك والاستخراج (Unpack) وتوليد الباركود والسندات الداخلية.
- **[`database_migration_plan_gros_detail.md`](file:///D:/git/GstockSW4/docs/database_migration_plan_gros_detail.md)**: المخطط الهيكلي لقاعدة البيانات (DDL)، تحديثات جدول المواقع `Locations`، تتبع شجرة الدفعات `Parent_Batch_ID`، جدول سندات التحويل والتفكيك `Internal_Transfers`، وسكريبت الترحيل الآمن.
- **[`ui_ux_redesign_inventory_sales.md`](file:///D:/git/GstockSW4/docs/ui_ux_redesign_inventory_sales.md)**: دليل تصميم وتطوير واجهات المستخدم الموحدة: شاشة دفعات المستودع الخاص، حوار التفكيك والاستخراج وطباعة الباركود `UnpackingTransferDialog`، كاشير التجزئة للرفوف العامة، واجهة بيع الجملة B2B، وسجل التحويلات.

### 📱 تقارير وتوثيق الميزات السابقة والترحيل
- `mobile_inventory_scanner.md`: توثيق تطبيق الموبايل Flutter للماسح الضوئي والجرد الميداني.
- `pos-migration-verification.md`: تقرير التحقق من ترحيل وتكامل نقطة البيع POS.
- `stocklam_feature_gap_report.md`: تقرير تحليل الفوارق والميزات بين StockLam و GstockSW4.
- `stocklam_migration_*.md`: سجلات مراحل ترحيل ميزات StockLam التاريخية.
