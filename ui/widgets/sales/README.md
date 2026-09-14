# UI Widgets - Point de Vente Caisse POS (`ui/widgets/sales`)

Composants PySide6 pour le point de vente tactile au détail (POS), les règlements de caisse et les retours d'articles.

> **Note d'architecture :** La Vente en Gros B2B et l'Historique des Ventes disposent désormais de leurs propres dossiers dédiés sous `ui/widgets/` :
> - `ui/widgets/wholesale_sales/` : Interface B2B, tarification dynamique, gestion BL/BC/Factures et export PDF.
> - `ui/widgets/sales_history/` : Historique des ventes, suivi des créances (AR Aging), encaissements et détails de factures.

## Fichiers et Rôles

- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace :
  - Restriction stricte des recherches d'articles et de lots aux emplacements configurés en `Visibility = 'Public'` et `Allow_POS_Sales = True`.
  - Garde-fou code-barres (Barcode Guard) : interception instantanée avec alerte visuelle non-bloquante lors du scan d'un article situé dans un emplacement privé ou non autorisé au POS.
  - Barre supérieure ultra-fine avec net à payer dynamique, bouton d'actualisation F5, contrôles client/date/emplacement sur une ligne.
  - Panier multi-colonnes avec changement direct de l'emplacement de retrait, support complet des codes-barres multiples et favoris dynamiques illimités.
- `return_dialog.py` : Dialogue modal ergonomique `ReturnProductSelectionDialog` pour les retours d'articles sans facture :
  - Champ de recherche auto-focus avec capture immédiate des codes-barres et filtrage temps-réel.
  - Grille des résultats complète affichant Produit, Code-barres/SKU, N° Lot, Stock, Péremption, Prix Vente HT/TTC.
  - Configuration du retour : Quantité avec garde-fou, emplacement de destination (priorité automatique à la zone Quarantaine/Retour), motif du retour (liste déroulante normalisée) et mode de remboursement.
  - Traitement transactionnel atomique avec incrémentation du stock, écriture dans l'historique de mouvements et génération d'un Bon de Retour (Avoir) A4 ReportLab.
- `debts_management_tab.py` : Interface complète de gestion des créances et suivi des dettes clients (`DebtsManagementTab`) :
  - Cartes KPI modernisées à fond blanc unifié, typographie hiérarchisée (titre 11px semi-bold, valeur 20px extra-bold) avec badge icône vectoriel 2D et alerte dynamique conditionnelle rouge (`#dc2626`) en cas de retard.
  - Barre de filtrage ergonomique avec étiquettes supérieures normalisées (Top Labels), autocomplétion nom/téléphone (`SearchableClientComboBox`), statut et seuil minimum de dette.
  - Séparateur équilibré (Splitter 50/50 avec persistance) entre le répertoire maître des clients débiteurs et le détail des pièces.
  - Entêtes de tables à fort contraste (`#0f172a` sur fond `#f8fafc` avec bordure inférieure `2px solid #007572`), alignement rigoureux des données (texte à gauche, montants financiers et soldes à droite, dates et statuts au centre).
  - Boutons d'actions vectoriels à largeur fixe (`185px` pour la colonne, `80px` par bouton) évitant tout tronquage horizontal.
  - Gestion contextuelle de l'état vide (Empty State via `QStackedWidget`) guidant l'utilisateur lorsqu'aucun client n'est sélectionné ou qu'aucune facture impayée n'existe.
  - Dialogue de règlement global / acompte (`GlobalPaymentDialog`) avec ventilation automatique FIFO ou acompte libre.
  - Dialogue d'audit d'intégrité comptable (`ClientDebtAuditDialog`).
- `searchable_client_combo.py` : Widget de sélection client avec autocomplétion instantanée (`SearchableClientComboBox`) :
  - Recherche bi-mode en temps réel par Nom du Client et par Numéro de Téléphone (`Qt.MatchContains`).
  - Formatage standardisé `Nom Client (Téléphone)` et préservation de l'élément spécial `Tous les Clients`.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens pour le POS (espèces, carte, virement, crédit).
- `invoice_payment_dialog.py` : Dialogue d'encaissement et de règlement direct d'une facture client impayée ou échue avec enregistrement dans `Client_Payments`.
- `dialogs.py` : Dialogues auxiliaires de caisse (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `CashSessionDetailsDialog`, `QuickCashPaymentDialog`, `SelectBatchBarcodeDialog`, `EnterProductBarcodeDialog`).
- `touch_keypad.py` : Clavier tactile virtuel bi-mode compact et flottant (pavé numérique `123` et clavier complet `ABC`), partagé et synchronisé dynamiquement entre le Point de Vente Caisse (POS) et la Vente en Gros B2B (`WholesaleSalesTab`).
- `__init__.py` : Point d'entrée du package exportant `PointOfSaleTab`, `ReturnProductSelectionDialog`, `DebtsManagementTab`, et `SearchableClientComboBox`.

