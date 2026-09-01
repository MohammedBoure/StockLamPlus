# UI Widgets - Ventes & Point de Vente (`ui/widgets/sales`)

Composants PySide6 pour le point de vente (POS), l'encaissement et l'historique des ventes.

## Fichiers et Rôles

- `__init__.py` : Expose les composants de vente (`PointOfSaleTab`, `SalesHistoryTab`).
- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace (barre supérieure ultra-fine avec net à payer dynamique, contrôles client/date sur une ligne, panier à défilement tactile intégral, barre d'actions inférieure et panneau droit pour produits favoris).
- `sales_history_tab.py` : Historique des tickets de caisse, remboursements et clôtures de session.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens (espèces, carte, etc.).
- `dialogs.py` : Dialogues du point de vente (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `QuickCashPaymentDialog`).



