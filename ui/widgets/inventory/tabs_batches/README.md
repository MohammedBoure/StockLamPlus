# Batches Tab Sub-package (`ui/widgets/inventory/tabs_batches/`)

Modular sub-package responsible for displaying and managing inventory batches (lots).

## Files and Purpose

- **`__init__.py`**: Main package entry point and definition of the `BatchesTab` widget class.
- **`_ui.py`**: Builds the filter panels, search bar, table columns configuration with prices in first priority, and pure white theme styling.
- **`_table.py`**: Manages table row rendering (`_fill_row`), lazy loading, infinite scroll, and multi-column sorting with prioritized pricing and inventory columns.
- **`_filters.py`**: Handles local and global filter application (families, suppliers, expiry dates, stock status, and waste/loss filter).
- **`_actions.py`**: Handles batch operations (FEFO validation, direct use, transfer, unpack & retail unit transfer, sales prices adjustment, price change history audit, POS priority group assignment (Liste N°), reclamation notes).
- **`_export.py`**: Exports filtered batch data to Excel, PDF, and prints batch barcode labels matching the prioritized column layout.
- **`_combos.py`**: Populates filter combo boxes (families, manufacturers, automates, suppliers).
- **`_context_menu.py`**: Context menu for right-click actions on batch rows (quick consume, transfer, unpack to retail unit, sales price adjustment, price change history, assign POS priority group (Liste N°), batch details).
- **`_permissions.py`**: Role-based permissions enforcing visibility of financial and pricing columns (columns 2 through 5 and 18 through 20) and bottom bar price action button.
- **`quick_add_dialog.py`**: Dialog for fast batch creation with supplier and barcode scanning support.
- **`_.py`**: Legacy reference implementation.
