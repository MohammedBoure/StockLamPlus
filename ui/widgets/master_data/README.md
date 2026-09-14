# UI Widgets - Données de Base (`ui/widgets/master_data`)

Ce dossier regroupe les interfaces de gestion des référentiels de données du laboratoire et de l'ERP commercial.

## Fichiers et Rôles

- `master_data_tabs.py` : Onglet principal organisant les sous-onglets de données de base.
- `products_tab.py` : Gestion du catalogue des produits et réactifs, avec affichage du groupe prioritaire de caisse (Liste N°).
- `suppliers_tab.py` : Gestion des fournisseurs et contacts.
- `manufacturers_tab.py` : Gestion des fabricants et marques.
- `automates_tab.py` : Gestion des automates de laboratoire.
- `locations_tab.py` : Gestion hiérarchique des emplacements de stockage (armoires, frigos, bacs) avec colonnes "Visibilité" (Public / Privé) et "Vente POS" (Oui / Non).
- `location_types_manager.py` : Gestion des types d'emplacements.
- `product_families_tab.py` : Gestion des familles de produits.
- `packaging_units_tab.py` : Gestion des unités de conditionnement et facteurs de conversion.
- `waste_reasons_tab.py` : Gestion des motifs de mise au rebut / perte.
- `external_partners_tab.py` : Gestion des partenaires et sous-traitants externes.
- `clients_tab.py` : Gestion des clients pour le point de vente et la vente en gros :
  - Colonnes "Catégorie" (Prix 1 à 4), "Plafond Crédit" et "Solde Actuel" en temps réel.
  - Badge styling et coloration QBrush : Vert pastel lorsque Solde $\le$ Plafond de Crédit, et Rouge pastel en cas de dépassement (Solde > Plafond).
  - Bouton d'action et menu contextuel sur clic droit : "📄 Générer Relevé de Compte".
- `client_statement_dialog.py` : Dialogue interactif de Relevé de Compte Client ("Extrait de Compte") :
  - Affichage plein écran maximisé (`showMaximized()`, 100vw × 100vh) avec barre d'outils utilitaire supérieure dédiée (Période, Sélecteurs de dates, Actualiser, Imprimer, Exporter PDF, Fermer).
  - Filtres temporels : Ce mois, Mois précédent, Dernier trimestre, 30 derniers jours, Cette année, Tout l'historique et Période personnalisée.
  - Cartes KPI synthétiques : Solde Antérieur, Total Débit (Factures/BL validés), Total Crédit (Règlements), Nouveau Solde Dû.
  - Grand livre chronologique avec solde progressif et alignement strict à droite en chiffres tabulaires `,0.00 DA` (Date, Type de Document, Référence, Débit +, Crédit -, Solde Progressif, Notes).
  - Ségrégation comptable stricte : les devis et commandes brouillons (`DEV-`, `BC-`) apparaissent marqués `[Hors bilan]` en gris avec débit nul sans altérer le solde progressif ni le solde antérieur.
  - Export PDF A4 ReportLab et impression directe unifiée avec en-tête d'entreprise, coordonnées fiscales du client (NIF, RC), récapitulatif KPI et tableau chronologique.
- `caisses_tab.py` : Gestion et contrôle des caisses (Terminaux POS), statut actif/inactif et suivi du nombre de sessions.
- `dialogs.py` : Boîtes de dialogue de saisie et de modification des entités de base :
  - `LocationDialog` : Contrôles de visibilité (Public / Privé) et case à cocher "Autoriser la vente POS" avec règle stricte d'intégrité (vente POS impossible sur emplacement privé).
  - `ClientDialog` : Sélection de la catégorie tarifaire (`Prix_1` à `Prix_4`) et saisie du plafond de crédit (`Credit_Limit`).
