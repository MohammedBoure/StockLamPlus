# Module Vente en Gros B2B (`ui/widgets/wholesale_sales`)

Ce dossier regroupe l'interface utilisateur et les composants dédiés à la vente en gros et demi-gros B2B, fonctionnant indépendamment des sessions de caisse POS.

## Fichiers et Rôles

- `wholesale_sales_tab.py` : Interface principale de vente en gros (`WholesaleSalesTab`). Permet la sélection des clients B2B, l'application automatique des grilles tarifaires (Prix 1 à Prix 4), le contrôle des plafonds de crédit et soldes dus, la sélection des lots du stock général/entrepôt, et la génération de Factures, Bons de Livraison (BL), Bons de Commande (BC) ou Devis.
- `pdf_export.py` : Module d'exportation PDF ReportLab (`export_wholesale_document_pdf`). Génère des documents commerciaux A4 complets avec en-tête d'entreprise, coordonnées client (NIF/RC), grille détaillée des lots/prix/remises/TVA, et récapitulatif financier.
- `__init__.py` : Point d'entrée du package exportant `WholesaleSalesTab` et `export_wholesale_document_pdf`.
