# UI Widgets - Données de Base (`ui/widgets/master_data`)

Ce dossier regroupe les interfaces de gestion des référentiels de données du laboratoire.

## Fichiers et Rôles

- `master_data_tabs.py` : Onglet principal organisant les sous-onglets de données de base.
- `products_tab.py` : Gestion du catalogue des produits et réactifs, avec affichage du groupe prioritaire de caisse (Liste N°).
- `suppliers_tab.py` : Gestion des fournisseurs et contacts.
- `manufacturers_tab.py` : Gestion des fabricants et marques.
- `automates_tab.py` : Gestion des automates de laboratoire.
- `locations_tab.py` : Gestion hiérarchique des emplacements de stockage (armoires, frigos, bacs).
- `location_types_manager.py` : Gestion des types d'emplacements.
- `product_families_tab.py` : Gestion des familles de produits.
- `packaging_units_tab.py` : Gestion des unités de conditionnement et facteurs de conversion.
- `waste_reasons_tab.py` : Gestion des motifs de mise au rebut / perte.
- `external_partners_tab.py` : Gestion des partenaires et sous-traitants externes.
- `clients_tab.py` : Gestion des clients pour le point de vente.
- `dialogs.py` : Boîtes de dialogue d'ajout et de modification pour chaque type de donnée de base (incluant l'assignation de groupe prioritaire POS sans limite).
