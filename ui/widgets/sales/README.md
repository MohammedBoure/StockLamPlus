# UI Widgets - Ventes & Point de Vente (`ui/widgets/sales`)

Composants PySide6 pour le point de vente (POS), l'encaissement et l'historique des ventes.

## Fichiers et Rôles

- `__init__.py` : Expose les composants de vente (`PointOfSaleTab`, `SalesHistoryTab`).
- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace (barre supérieure ultra-fine avec net à payer dynamique, contrôles client/date sur une ligne avec auto-sélection intégrale au clic/focus sur la recherche, le client, les quantités et remises, panier avec bouton de suppression prioritaire en tête, colonnes commerciales au centre et colonnes Stock/Lot/TVA en fin de tableau, barre d'actions inférieure et panneau droit pour produits favoris).
- `sales_history_tab.py` : Historique des tickets de caisse, remboursements et clôtures de session.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens (espèces, carte, etc.).
- `dialogs.py` : Dialogues du point de vente (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `QuickCashPaymentDialog`).
- `touch_keypad.py` : Clavier tactile virtuel flottant agissant comme un clavier physique (envoi direct de frappes à l'élément actif sans perte de focus), avec poignée de déplacement dédiée et raccourcis de ciblage rapide.



