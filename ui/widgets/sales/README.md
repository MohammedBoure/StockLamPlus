# UI Widgets - Ventes & Point de Vente (`ui/widgets/sales`)

Composants PySide6 pour le point de vente (POS), la vente en gros B2B, l'encaissement et l'historique des ventes.

## Fichiers et Rôles

- `__init__.py` : Expose les composants de vente (`PointOfSaleTab`, `SalesHistoryTab`, `WholesaleSalesTab`).
- `wholesale_sales_tab.py` : Interface indépendante pour la Vente en Gros B2B (sans session de caisse POS obligatoire) :
  - Sélection de client avec solde débiteur en temps réel, plafond de crédit, marge disponible et badge de catégorie tarifaire.
  - Gestion des documents commerciaux : Devis, Bon de Commande (brouillons sans déduction de stock), Bon de Livraison et Facture (validation avec déduction atomique du stock).
  - Sélection des échéances prédéfinies (+15, +30, +60 jours, Fin de mois).
  - Grille d'articles avec résolution dynamique des prix multi-tarifs (Prix 1 à 4) selon le `Price_Tier` du client.
  - Génération et impression automatique de factures/BL au format PDF A4 ReportLab.
- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace :
  - Restriction stricte des recherches d'articles et de lots aux emplacements configurés en `Visibility = 'Public'` et `Allow_POS_Sales = True`.
  - Garde-fou code-barres (Barcode Guard) : interception instantanée avec alerte visuelle non-bloquante lors du scan d'un article situé dans un emplacement privé ou non autorisé au POS.
  - Barre supérieure ultra-fine avec net à payer dynamique, bouton d'actualisation F5, contrôles client/date/emplacement sur une ligne.
  - Panier multi-colonnes avec changement direct de l'emplacement de retrait, support complet des codes-barres multiples et favoris dynamiques illimités.
- `sales_history_tab.py` : Historique complet des ventes, tickets POS et documents de gros :
  - Suivi des créances clients et du vieillissement de la dette (AR Aging : Toutes Échues, 1-30j, 31-60j, >60j).
  - Nouvelle colonne "Retard (Jours)" avec formatage visuel d'alerte (badge rouge pour factures en retard, vert pour factures soldées).
  - Menu contextuel sur clic droit et bouton d'action dédié "💳 Encaisser Paiement" ouvrant `InvoicePaymentDialog`.
  - Remplacement du dialogue de retour manuel par le dialogue graphique moderne `ReturnProductSelectionDialog`.
  - Export CSV incluant les dates d'échéances et les jours de retard.
- `invoice_payment_dialog.py` : Dialogue d'encaissement et de règlement direct d'une facture client impayée ou échue avec enregistrement dans `Client_Payments` et mise à jour automatique du statut de la facture.
- `return_dialog.py` : Dialogue `ReturnProductSelectionDialog` pour les retours sans facture avec recherche textuelle/code-barres, sélection du lot dans une grille, choix de l'emplacement de réintégration et du mode de remboursement.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens pour le POS (espèces, carte, virement, crédit).
- `dialogs.py` : Dialogues auxiliaires de caisse (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `CashSessionDetailsDialog`, `QuickCashPaymentDialog`, `SelectBatchBarcodeDialog`, `EnterProductBarcodeDialog`).
- `touch_keypad.py` : Clavier tactile virtuel bi-mode compact et flottant (pavé numérique `123` et clavier complet `ABC`).
