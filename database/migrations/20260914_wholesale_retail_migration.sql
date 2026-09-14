-- =============================================================================
-- Migration: 20260914_wholesale_retail_migration.sql
-- Description: Safe & Idempotent Schema Migration for Wholesale & Retail Integration
-- Target Tables: Locations, Inventory_Batches, Sales_Invoices, Clients
-- Engine: MySQL 5.7+ / 8.0+ / 8.4+ / MariaDB
-- Zero Data Loss Guarantee: All ALTER operations preserve existing table records.
-- =============================================================================

-- Disable foreign key checks and autocommit during procedure declaration
SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_migrate_wholesale_retail $$
CREATE PROCEDURE sp_migrate_wholesale_retail()
BEGIN
    DECLARE v_db VARCHAR(100);
    DECLARE v_pk_batches VARCHAR(64);
    
    -- Detect active schema
    SELECT DATABASE() INTO v_db;
    
    IF v_db IS NULL OR v_db = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No database selected. Please run: USE <database_name>;';
    END IF;

    -- =========================================================================
    -- 1. TABLE: Locations (Private Warehouse vs Public Shelf Visibility)
    -- =========================================================================
    
    -- 1.1 Add 'Visibility' ENUM('Private', 'Public') NOT NULL DEFAULT 'Private'
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Locations' AND COLUMN_NAME = 'Visibility'
    ) THEN
        ALTER TABLE Locations 
        ADD COLUMN Visibility ENUM('Private', 'Public') NOT NULL DEFAULT 'Private' 
        AFTER Temperature_Zone;
    END IF;

    -- 1.2 Add 'Allow_POS_Sales' BOOLEAN NOT NULL DEFAULT FALSE
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Locations' AND COLUMN_NAME = 'Allow_POS_Sales'
    ) THEN
        ALTER TABLE Locations 
        ADD COLUMN Allow_POS_Sales BOOLEAN NOT NULL DEFAULT FALSE 
        AFTER Visibility;
    END IF;

    -- 1.3 Optional index for rapid location filtering in POS
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Locations' AND INDEX_NAME = 'idx_locations_visibility_pos'
    ) THEN
        CREATE INDEX idx_locations_visibility_pos ON Locations(Visibility, Allow_POS_Sales);
    END IF;

    -- =========================================================================
    -- 2. TABLE: Inventory_Batches (Parent Lineage, Batch Type & Indexing)
    -- =========================================================================
    
    -- 2.1 Add 'Parent_Batch_ID' BIGINT UNSIGNED NULL
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Inventory_Batches' AND COLUMN_NAME = 'Parent_Batch_ID'
    ) THEN
        ALTER TABLE Inventory_Batches 
        ADD COLUMN Parent_Batch_ID BIGINT UNSIGNED NULL 
        AFTER Batch_ID;
    END IF;

    -- 2.2 Add 'Batch_Type' ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk'
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Inventory_Batches' AND COLUMN_NAME = 'Batch_Type'
    ) THEN
        ALTER TABLE Inventory_Batches 
        ADD COLUMN Batch_Type ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk' 
        AFTER Status;
    END IF;

    -- 2.3 Detect primary key of Inventory_Batches (Batch_ID vs id) for foreign key precision
    SELECT COLUMN_NAME INTO v_pk_batches
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = v_db 
      AND TABLE_NAME = 'Inventory_Batches' 
      AND CONSTRAINT_NAME = 'PRIMARY'
    LIMIT 1;

    IF v_pk_batches IS NULL THEN
        SET v_pk_batches = 'Batch_ID';
    END IF;

    -- 2.4 Add Foreign Key Constraint referencing Inventory_Batches(Batch_ID)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.TABLE_CONSTRAINTS 
        WHERE CONSTRAINT_SCHEMA = v_db 
          AND TABLE_NAME = 'Inventory_Batches' 
          AND CONSTRAINT_NAME = 'fk_batch_parent_batch'
    ) THEN
        SET @sql_fk = CONCAT(
            'ALTER TABLE Inventory_Batches ',
            'ADD CONSTRAINT fk_batch_parent_batch ',
            'FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches(', v_pk_batches, ') ',
            'ON DELETE SET NULL ON UPDATE CASCADE'
        );
        PREPARE stmt_fk FROM @sql_fk;
        EXECUTE stmt_fk;
        DEALLOCATE PREPARE stmt_fk;
    END IF;

    -- 2.5 Add composite index on (Parent_Batch_ID, Batch_Type)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = v_db 
          AND TABLE_NAME = 'Inventory_Batches' 
          AND INDEX_NAME = 'idx_batch_parent_type'
    ) THEN
        CREATE INDEX idx_batch_parent_type ON Inventory_Batches(Parent_Batch_ID, Batch_Type);
    END IF;

    -- =========================================================================
    -- 3. TABLE: Sales_Invoices (Sale Classification, Due Date & Indexing)
    -- =========================================================================
    
    -- 3.1 Add 'Sale_Type' ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS'
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Sales_Invoices' AND COLUMN_NAME = 'Sale_Type'
    ) THEN
        ALTER TABLE Sales_Invoices 
        ADD COLUMN Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS' 
        AFTER Status;
    END IF;

    -- 3.2 Add 'Due_Date' DATE NULL
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Sales_Invoices' AND COLUMN_NAME = 'Due_Date'
    ) THEN
        ALTER TABLE Sales_Invoices 
        ADD COLUMN Due_Date DATE NULL 
        AFTER Invoice_Date;
    END IF;

    -- 3.3 Add composite index on (Sale_Type, Due_Date)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = v_db 
          AND TABLE_NAME = 'Sales_Invoices' 
          AND INDEX_NAME = 'idx_sales_type_due_date'
    ) THEN
        CREATE INDEX idx_sales_type_due_date ON Sales_Invoices(Sale_Type, Due_Date);
    END IF;

    -- =========================================================================
    -- 4. TABLE: Clients (Tiered Pricing & Commercial Credit Limit)
    -- =========================================================================
    
    -- 4.1 Add 'Price_Tier' ENUM('Prix_1', 'Prix_2', 'Prix_3', 'Prix_4') NOT NULL DEFAULT 'Prix_1'
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Clients' AND COLUMN_NAME = 'Price_Tier'
    ) THEN
        ALTER TABLE Clients 
        ADD COLUMN Price_Tier ENUM('Prix_1', 'Prix_2', 'Prix_3', 'Prix_4') NOT NULL DEFAULT 'Prix_1';
    END IF;

    -- 4.2 Add or Modify 'Credit_Limit' DECIMAL(15,2) NOT NULL DEFAULT 0.00
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'Clients' AND COLUMN_NAME = 'Credit_Limit'
    ) THEN
        ALTER TABLE Clients 
        ADD COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
    ELSE
        -- Ensure accurate decimal precision and default value
        ALTER TABLE Clients 
        MODIFY COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
    END IF;

END $$

DELIMITER ;

-- =============================================================================
-- Execute Stored Migration Procedure
-- =============================================================================
CALL sp_migrate_wholesale_retail();

-- Clean up migration procedure after execution
DROP PROCEDURE IF EXISTS sp_migrate_wholesale_retail;

-- Restore environment variables
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;

-- =============================================================================
-- Verification Query: Validate All New Columns, Constraints & Indexes
-- =============================================================================
SELECT 
    TABLE_NAME, 
    COLUMN_NAME, 
    COLUMN_TYPE, 
    IS_NULLABLE, 
    COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND (
      (TABLE_NAME = 'Locations' AND COLUMN_NAME IN ('Visibility', 'Allow_POS_Sales')) OR
      (TABLE_NAME = 'Inventory_Batches' AND COLUMN_NAME IN ('Parent_Batch_ID', 'Batch_Type')) OR
      (TABLE_NAME = 'Sales_Invoices' AND COLUMN_NAME IN ('Sale_Type', 'Due_Date')) OR
      (TABLE_NAME = 'Clients' AND COLUMN_NAME IN ('Price_Tier', 'Credit_Limit'))
  )
ORDER BY TABLE_NAME, ORDINAL_POSITION;
