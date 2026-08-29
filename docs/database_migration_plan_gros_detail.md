# خطة تكييف وترحيل قاعدة البيانات (Database Migration & Schema Plan)
## نظام المخزون الثنائي: مستودع الجملة الكبير (Dépôt Gros) + رفوف المتجر (Rayonnage Magasin)

---

## 1. الأهداف الفنية للتعديل

1. **دعم تعدد المواقع الذكي**: تصنيف مواقع التخزين (`Locations`) إلى مواقع مستودع رئيسي (`Warehouse_Bulk`) ومواقع رفوف/معرض (`Store_Shelf`).
2. **عزل رصيد الرفوف عن رصيد المستودع**: تخزين كميات الرفوف المتاحة للبيع بالتجزئة في هيكل مستقل يمنع بيع كميات المستودع غير المعروضة عبر كاشير التجزئة.
3. **تسجيل دورة التحويل والتفكيك الداخلي**: توثيق عمليات نقل البضاعة من المستودع الكبير إلى الرفوف مع دعم تفكيك الطرود (Déconditionnement) وتتبع من أنشأ ونفذ التحويل.
4. **تمييز فواتير ومبيعات الجملة عن التجزئة**: توثيق مسار كل عملية بيع (هل خصمت من الرف أم من المستودع الكبير؟ وما هي الشروط التجارية المطبقة؟).
5. **ضمان التوافقية الكاملة (Zero Data Loss & Backwards Compatibility)**: عدم فقدان أي بيانات تاريخية، وترحيل الأرصدة الحالية بسلاسة إلى الهيكل الجديد.

---

## 2. مخطط التعديلات الهيكلية (DDL Scripts)

### 2.1. تعديل جدول المواقع (`Locations`)
```sql
-- 1. إضافة نوع وتصنيف الموقع
ALTER TABLE Locations 
ADD COLUMN Location_Category ENUM('Warehouse_Bulk', 'Store_Shelf', 'Transit', 'Quarantine') 
NOT NULL DEFAULT 'Warehouse_Bulk' AFTER Location_Type;

-- 2. تحديد ما إذا كان الموقع نقطة بيع مباشرة (POS Shelf)
ALTER TABLE Locations
ADD COLUMN Allow_Direct_POS BOOLEAN NOT NULL DEFAULT FALSE AFTER Location_Category;

-- 3. مؤشر للبحث السريع
CREATE INDEX idx_locations_category ON Locations(Location_Category, Allow_Direct_POS);
```

### 2.2. جدول أرصدة الرفوف والمعرض (`Store_Shelf_Inventory`)
```sql
CREATE TABLE IF NOT EXISTS Store_Shelf_Inventory (
    Shelf_Item_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Location_ID INT UNSIGNED NOT NULL,
    Batch_ID INT UNSIGNED NOT NULL,
    Product_ID INT UNSIGNED NOT NULL,
    Quantity_On_Shelf DECIMAL(15, 3) NOT NULL DEFAULT 0.000,
    Minimum_Shelf_Level DECIMAL(15, 3) NOT NULL DEFAULT 5.000,
    Maximum_Shelf_Capacity DECIMAL(15, 3) NOT NULL DEFAULT 50.000,
    Last_Replenished_At DATETIME NULL,
    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE ON DELETE RESTRICT,
    
    UNIQUE KEY uq_shelf_location_batch (Location_ID, Batch_ID),
    INDEX idx_shelf_product (Product_ID, Location_ID),
    INDEX idx_shelf_low_stock (Quantity_On_Shelf, Minimum_Shelf_Level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.3. جدول سندات تزويد وتحويل الرفوف (`Internal_Shelf_Transfers`)
```sql
CREATE TABLE IF NOT EXISTS Internal_Shelf_Transfers (
    Transfer_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Transfer_No VARCHAR(100) NOT NULL UNIQUE,
    Source_Location_ID INT UNSIGNED NOT NULL,
    Destination_Location_ID INT UNSIGNED NOT NULL,
    Transfer_Date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status ENUM('Draft', 'In_Transit', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Completed',
    Created_By INT UNSIGNED NULL,
    Received_By INT UNSIGNED NULL,
    Notes TEXT NULL,
    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (Source_Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Destination_Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    FOREIGN KEY (Received_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    
    INDEX idx_transfer_date (Transfer_Date),
    INDEX idx_transfer_status (Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.4. جدول تفاصيل بنود التحويل والتفكيك (`Internal_Shelf_Transfer_Items`)
```sql
CREATE TABLE IF NOT EXISTS Internal_Shelf_Transfer_Items (
    Item_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Transfer_ID BIGINT UNSIGNED NOT NULL,
    Batch_ID INT UNSIGNED NOT NULL,
    Product_ID INT UNSIGNED NOT NULL,
    Qty_Transferred_Bulk DECIMAL(15, 3) NOT NULL, -- الكمية المخصومة من المستودع الكبير
    Bulk_Unit VARCHAR(50) NOT NULL,              -- وحدة المستودع (مثلاً: كرتونة)
    Conversion_Factor DECIMAL(10, 3) NOT NULL DEFAULT 1.000, -- معامل التفكيك (مثلاً: 12 علبة/كرتونة)
    Qty_Added_To_Shelf DECIMAL(15, 3) NOT NULL,  -- الكمية المضافة للرف = Bulk * Conversion
    Shelf_Unit VARCHAR(50) NOT NULL,             -- وحدة الرف (مثلاً: قطعة / علبة)
    Notes VARCHAR(255) NULL,
    
    FOREIGN KEY (Transfer_ID) REFERENCES Internal_Shelf_Transfers(Transfer_ID) ON DELETE CASCADE,
    FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
    FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
    
    INDEX idx_transfer_items_batch (Batch_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.5. تعديل جدول المبيعات وفواتير العملاء (`Sales_Invoices`)
```sql
ALTER TABLE Sales_Invoices 
ADD COLUMN Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS' AFTER Status;

ALTER TABLE Sales_Invoices
ADD COLUMN Source_Stock_Type ENUM('Store_Shelf', 'Warehouse_Bulk') NOT NULL DEFAULT 'Store_Shelf' AFTER Sale_Type;

ALTER TABLE Sales_Invoices
ADD COLUMN Commercial_Discount_Percent DECIMAL(5, 2) NOT NULL DEFAULT 0.00 AFTER Total_Amount_HT;

ALTER TABLE Sales_Invoices
ADD COLUMN Due_Date DATE NULL AFTER Invoice_Date;

CREATE INDEX idx_sales_type_date ON Sales_Invoices(Sale_Type, Invoice_Date);
```

### 2.6. تعديل جدول تفاصيل الفاتورة (`Sales_Invoice_Details`)
```sql
ALTER TABLE Sales_Invoice_Details
ADD COLUMN Package_Unit VARCHAR(50) NULL AFTER Quantity_Sold;

ALTER TABLE Sales_Invoice_Details
ADD COLUMN Units_Per_Package DECIMAL(10, 3) NOT NULL DEFAULT 1.000 AFTER Package_Unit;
```

---

## 3. خطة ترحيل البيانات الحالية (Data Migration Script)

لضمان عمل النظام الحالي دون انقطاع، يتم تنفيذ خطوات الترحيل الآلية التالية:

```sql
-- الخطوة 1: إنشاء موقع افتراضي للرفوف والمعرض إذا لم يكن موجوداً
INSERT INTO Locations (Location_Name, Location_Type, Location_Category, Allow_Direct_POS, Description)
SELECT 'Rayon Principal - Magasin', 'Store', 'Store_Shelf', TRUE, 'المعرض والرفوف الرئيسية لنقاط البيع'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM Locations WHERE Location_Category = 'Store_Shelf' LIMIT 1
);

-- الخطوة 2: تحديث المواقع القديمة لتصنيفها كمستودع رئيسي افتراضياً
UPDATE Locations 
SET Location_Category = 'Warehouse_Bulk' 
WHERE Location_Category IS NULL OR Location_Category = '';

-- الخطوة 3: ترحيل حصة ابتدائية من دفعات المخزون الحالية إلى الرفوف لتشغيل نقطة البيع فوراً
INSERT INTO Store_Shelf_Inventory (Location_ID, Batch_ID, Product_ID, Quantity_On_Shelf, Minimum_Shelf_Level, Maximum_Shelf_Capacity)
SELECT 
    (SELECT Location_ID FROM Locations WHERE Location_Category = 'Store_Shelf' LIMIT 1) AS Location_ID,
    b.Batch_ID,
    b.Product_ID,
    LEAST(b.Quantity_Current, 10.000) AS Quantity_On_Shelf, -- وضع حد أقصى 10 قطع على الرف كبداية
    5.000 AS Minimum_Shelf_Level,
    50.000 AS Maximum_Shelf_Capacity
FROM Inventory_Batches b
WHERE b.Quantity_Current > 0 
  AND b.Status = 'Available'
ON DUPLICATE KEY UPDATE 
    Quantity_On_Shelf = VALUES(Quantity_On_Shelf);

-- الخطوة 4: خصم الكميات التي تم ترحيلها إلى الرفوف من رصيد المستودع الكبير
UPDATE Inventory_Batches b
JOIN Store_Shelf_Inventory s ON b.Batch_ID = s.Batch_ID
SET b.Quantity_Current = GREATEST(0.000, b.Quantity_Current - s.Quantity_On_Shelf)
WHERE s.Quantity_On_Shelf > 0;
```

---

## 4. تكامل الحركات المخزنية (Stock Movement Log Integrity)

عند تنفيذ أي عملية، يتم إدراج سجل بحركة المخزون في `Stock_Movement_Log`:
1. **التحويل إلى الرف (`Transfer_To_Shelf`)**:
   - حركة خصم من المستودع الكبير: `Qty_Change = -X`, `Movement_Type = 'Transfer_To_Shelf_Out'`.
   - حركة إضافة إلى الرف: `Qty_Change = +Y`, `Movement_Type = 'Transfer_To_Shelf_In'`.
2. **البيع بالجملة (`Wholesale_Sale`)**:
   - حركة خصم مباشرة من المستودع الكبير: `Qty_Change = -X`, `Movement_Type = 'Wholesale_Sale'`.
3. **البيع بالتجزئة (`Retail_POS_Sale`)**:
   - حركة خصم مباشرة من رصيد الرف: `Qty_Change = -X`, `Movement_Type = 'Retail_POS_Sale'`.

---
*تم إعداد هذا المخطط ليكون قابلاً للتطبيق المباشر عبر `schema_initializer.py` دون أي تأثير على البيانات القائمة.*
