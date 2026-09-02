# UI Widgets - Ventes & Point de Vente (`ui/widgets/sales`)

Composants PySide6 pour le point de vente (POS), l'encaissement et l'historique des ventes.

## Fichiers et Rôles

- `__init__.py` : Expose les composants de vente (`PointOfSaleTab`, `SalesHistoryTab`).
- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace (barre supérieure ultra-fine avec net à payer dynamique, bouton d'actualisation '🔄 Actualiser' situé dans l'espace vide naturel sans encombrement avec raccourci F5, contrôles client/date/emplacement sur une ligne avec auto-sélection intégrale au clic/focus sur la recherche, le client, les quantités et remises, panier à largeur dynamique illimitée affichant l'intégralité des codes-barres internes et externes ainsi que les noms complets avec barre de défilement tactile fluide, bouton de suppression prioritaire en tête, colonnes commerciales au centre, nouvelle colonne 'Emplacement (Lieu de retrait)' interactive permettant de choisir ou changer l'endroit de sortie du produit directement depuis le panier, colonnes Stock/Lot/TVA, support complet des codes-barres multiples avec découpage et indexation automatique, sélection tactile du lieu/lot/code lors du clic depuis la liste des favoris ou la recherche si présent dans plusieurs endroits, double-clic sur la cellule code-barres du panier pour saisie directe, bouton d'action '🏷️ Saisie Code-Barres', barre d'actions inférieure et panneau droit dynamique affichant les boutons de numéros simples ultra-compacts `1`, `2`, `3`... s'organisant automatiquement en nouvelles lignes/barres complètes dès qu'une ligne est pleine (8 boutons par ligne avec hauteur adaptative), permettant d'accueillir un nombre illimité de listes favorites et d'y basculer d'un simple toucher).
- `sales_history_tab.py` : Historique des tickets de caisse, remboursements et clôtures de session.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens (espèces, carte, etc.).
- `dialogs.py` : Dialogues du point de vente (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `QuickCashPaymentDialog`, `SelectBatchBarcodeDialog` avec choix et filtrage de lieu de retrait, `EnterProductBarcodeDialog`).
- `touch_keypad.py` : Clavier tactile virtuel bi-mode compact et flottant (pavé numérique `123` et clavier complet de lettres `ABC` avec disposition AZERTY/QWERTY et Maj), agissant exactement comme un clavier physique (envoi direct de frappes à l'élément actif sans perte de focus), avec poignée de déplacement dédiée, filtrage intelligent des cibles et raccourcis rapides.



