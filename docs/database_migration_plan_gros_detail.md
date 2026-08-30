# خطة تكييف وترحيل قاعدة البيانات (Database Schema & Migration Plan)
## معمارية المخزون الموحد عبر رؤية المواقع وسندات التحويل والتفكيك الداخلي

---

## 1. المبادئ الفنية للتصميم الهيكلي

1. **الاعتماد الكلي على جدول الدفعات القائم (`Inventory_Batches`)**: عدم إنشاء أي جدول منفصل لأرصدة الرفوف، وتوحيد إدارة المخزون المالي والمادي في جدول واحد.
2. **رؤية المواقع في جدول `Locations`**: التمييز بين المستودع والمعرض من خلال حقل الرؤية `Visibility ENUM('Private', 'Public')` وصلاحية البيع المباشر `Allow_POS_Sales`.
3. **شجرة تتبع الدفعات المفككة (`Parent_Batch_ID`)**: تمكين الدفعات المستخرجة للرفوف من الإشارة إلى الدفعة الأم الأصلية بالمستودع لضمان تتبع تواريخ الصلاحية والتكلفة وسلسلة التوريد.
4. **توثيق التحويلات والتفكيك (`Internal_Transfers`)**: تسجيل سندات النقل المباشر وسندات التفكيك الداخلي مع حفظ الباركود المولد ومعامل التحويل.

---

## 2. مخطط التعديلات الهيكلية (DDL Scripts)

### 2.1. تحديث جدول المواقع (`Locations`)
```sql
-- 1. إضافة حقل الرؤية (Private للمستودع / Public للرفوف والمعرض)
ALTER TABLE Locations 
ADD COLUMN Visibility ENUM('Private', 'Public') NOT NULL DEFAULT 'Private' AFTER Location_Type;

-- 2. إضافة علم السماح بنقاط البيع بالتجزئة (POS)
ALTER TABLE Locations
ADD COLUMN Allow_POS_Sales BOOLEAN NOT NULL DEFAULT FALSE AFTER Visibility;

-- 3. إنشاء فهارس للبحث السريع
CREATE INDEX idx_locations_visibility_pos ON Locations(Visibility, Allow_POS_Sales);
```

### 2.2. تحديث جدول الدفعات الموحد (`Inventory_Batches`)
```sql
-- 1. إضافة حقل الدفعة الأم للربط التتبعي عند التفكيك
ALTER TABLE Inventory_Batches
ADD COLUMN Parent_Batch_ID INT UNSIGNED NULL AFTER Batch_ID;

-- 2. إضافة تصنيف نوع الدفعة (جملة/مستودع أو تجزئة مفككة)
ALTER TABLE Inventory_Batches
ADD COLUMN Batch_Type ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk' AFTER Status;

-- 3. إضافة القيد المرجعي والفهرس
ALTER TABLE Inventory_Batches
ADD CONSTRAINT fk_batch_parent FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL;

CREATE INDEX idx_batch_parent ON Inventory_Batches(Parent_Batch_ID);
CREATE INDEX idx_batch_type_location ON Inventory_Batches(Batch_Type, Location_ID);
```

### 2.3. جدول سندات التحويل الداخلي (`Internal_Transfers`)
```sql
CREATE TABLE IF NOT EXISTS Internal_Transfers (
    Transfer_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Transfer_No VARCHAR(100) NOT NULL UNIQUE,       -- رقم السند التسلسلي (مثلاً: TRF-2026-0001)
    Source_Location_ID INT UNSIGNED NOT NULL,       -- الموقع المصدر (المستودع الخاص)
    Destination_Location_ID INT UNSIGNED NOT NULL,  -- الموقع الهدف (الرف العام)
    Transfer_Type ENUM('Direct', 'Unpack') NOT NULL DEFAULT 'Direct', -- نوع التحويل: مباشر أو تفكيك
    Transfer_Date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status ENUM('Draft', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Completed',
    Created_By INT UNSIGNED NULL,                   -- الموظف المنشئ
    Received_By INT UNSIGNED NULL,                  -- الموظف المستلم على الرف
    Notes TEXT NULL,                                -- الملاحظات والغرض
    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (Source_Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Destination_Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    FOREIGN KEY (Received_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    
    INDEX idx_transfers_type_date (Transfer_Type, Transfer_Date),
    INDEX idx_transfers_status (Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.4. جدول تفاصيل بنود التحويل والتفكيك (`Internal_Transfer_Items`)
```sql
CREATE TABLE IF NOT EXISTS Internal_Transfer_Items (
    Item_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Transfer_ID BIGINT UNSIGNED NOT NULL,
    Product_ID INT UNSIGNED NOT NULL,
    Source_Batch_ID INT UNSIGNED NOT NULL,          -- الدفعة المصدر في المستودع
    Destination_Batch_ID INT UNSIGNED NULL,         -- الدفعة المستهدفة أو الدفعة الجديدة الناتجة
    Qty_Transferred DECIMAL(15, 3) NOT NULL,        -- الكمية المخصومة بوحدة التخزين
    Source_Unit VARCHAR(50) NOT NULL,               -- وحدة التخزين (مثلاً: Carton)
    Conversion_Factor DECIMAL(10, 3) NOT NULL DEFAULT 1.000, -- معامل التفكيك (مثلاً: 24)
    Qty_Received DECIMAL(15, 3) NOT NULL,           -- الكمية المضافة بوحدة الاستخدام (Qty * Factor)
    Destination_Unit VARCHAR(50) NOT NULL,          -- وحدة الاستخدام (مثلاً: Pièce)
    Generated_Barcode VARCHAR(100) NULL,            -- الباركود الداخلي المولد للدفعة الجديدة
    Notes VARCHAR(255) NULL,
    
    FOREIGN KEY (Transfer_ID) REFERENCES Internal_Transfers(Transfer_ID) ON DELETE CASCADE,
    FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Source_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Destination_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL,
    
    INDEX idx_trf_items_source_batch (Source_Batch_ID),
    INDEX idx_trf_items_dest_batch (Destination_Batch_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.5. تحديث جدول فواتير المبيعات (`Sales_Invoices`)
```sql
-- 1. إضافة نوع المبيعات (تجزئة عبر الكاشير أو جملة للشركات والتجار)
ALTER TABLE Sales_Invoices 
ADD COLUMN Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS' AFTER Status;

-- 2. إضافة حقل تاريخ الاستحقاق لمبيعات الجملة بالدين
ALTER TABLE Sales_Invoices
ADD COLUMN Due_Date DATE NULL AFTER Invoice_Date;

CREATE INDEX idx_sales_type ON Sales_Invoices(Sale_Type, Invoice_Date);
```

---

## 3. سكريبت ترحيل وتهيئة البيانات (Idempotent Data Migration Script)

يتم تشغيل هذا السكريبت بسلاسة لضمان تكييف البيانات الحالية وتصنيف المواقع:

```sql
-- الخطوة 1: ضمان وجود موقع عام للرفوف والمعرض (Public Store Shelf)
INSERT INTO Locations (Location_Name, Location_Type, Visibility, Allow_POS_Sales, Description)
SELECT 'Rayon Principal - Magasin', 'Store', 'Public', TRUE, 'المعرض والرفوف الرئيسية لنقاط البيع'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM Locations WHERE Visibility = 'Public' OR Allow_POS_Sales = TRUE LIMIT 1
);

-- الخطوة 2: تحديث كافة المواقع الحالية الأخرى لتكون مواقع خاصة بالمستودع افتراضياً
UPDATE Locations 
SET Visibility = 'Private', Allow_POS_Sales = FALSE 
WHERE Visibility IS NULL OR (Location_Name NOT LIKE '%Rayon%' AND Location_Name NOT LIKE '%Magasin%');

-- الخطوة 3: تعيين المواقع التي تحمل اسم رفوف أو متجر كمواقع عامة للبيع بالتجزئة
UPDATE Locations 
SET Visibility = 'Public', Allow_POS_Sales = TRUE 
WHERE Location_Name LIKE '%Rayon%' OR Location_Name LIKE '%Magasin%' OR Location_Name LIKE '%Comptoir%';

-- الخطوة 4: تحديث كافة دفعات المخزون الحالية لتكون دفعات قياسية افتراضياً
UPDATE Inventory_Batches 
SET Batch_Type = 'Standard_Bulk' 
WHERE Batch_Type IS NULL;
```

---

## 4. الإجراءات المخزنية والتتبع في السجلات (Movement Log Integrity)

عند تنفيذ العمليات في المنظومة الجديدة، تسجل الحركات في `Stock_Movement_Log` كالتالي:

1. **التحويل المباشر (Direct Transfer)**:
   - سجل حركة واحد: `Movement_Type = 'Internal_Transfer'`, يوثق تغيير `Location_ID` من الموقع الخاص إلى الموقع العام مع ثبات الكمية ورقم الدفعة.
2. **التحويل مع التفكيك (Unpacking Transfer)**:
   - حركة خصم من الدفعة الأم في المستودع: `Qty_Change = -X (Stock_Unit)`, `Movement_Type = 'Unpack_Source_Deduction'`.
   - حركة إضافة للدفعة الجديدة في الرف: `Qty_Change = +Y (Usage_Unit)`, `Movement_Type = 'Unpack_Retail_Creation'`, مع توثيق `Parent_Batch_ID` والباركود المولد.
3. **مبيعات التجزئة (Retail POS)**:
   - حركة خصم من الدفعة العامة: `Qty_Change = -Qty`, `Movement_Type = 'Sale'`.
4. **مبيعات الجملة (Wholesale Sales)**:
   - حركة خصم من دفعة المستودع الخاصة: `Qty_Change = -Qty`, `Movement_Type = 'Wholesale_Sale'`.

---
*هذا المخطط الهيكلي يضمن أداءً فائقاً وسلامة تامة لبيانات المخزون دون الحاجة لأي جداول أرصدة مكررة.*
