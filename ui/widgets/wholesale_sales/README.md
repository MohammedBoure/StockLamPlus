# Module Vente en Gros B2B (`ui/widgets/wholesale_sales`)

Ce dossier regroupe l'interface utilisateur et les composants dédiés à la vente en gros et demi-gros B2B, fonctionnant indépendamment des sessions de caisse POS.

## Fichiers et Rôles

- `wholesale_sales_tab.py` : Interface principale de vente en gros (`WholesaleSalesTab`). Permet la sélection des clients B2B, l'application et la liaison automatique des grilles tarifaires (Prix 1 à Prix 4 avec bannière d'alerte en cas d'application du tarif détail), le contrôle strict des plafonds de crédit et soldes dus avec dérogation superviseur, la répartition multi-lots (FIFO ou sélection manuelle), la saisie d'échantillons/gratuités autorisant le prix nul, et la génération de Factures, Bons de Livraison (BL), Bons de Commande (BC) ou Devis. Intègre une ergonomie 100% clavier (saisie en chaîne Entrée, F1/Ctrl+F recherche, F2 client, F3 tarif, F10 validation, Suppr avec confirmation), un support tactile complet (hauteurs de lignes de 44px, scroll au pixel) et le clavier virtuel bi-mode partagé (`TouchKeypadDialog`).
- `lot_split_dialog.py` : Boîte de dialogue de répartition multi-lots (`MultiLotSelectionDialog`). Permet la sélection et ventilation d'un article sur plusieurs lots/emplacements de stockage avec allocation automatique FIFO, réinitialisation, suivi de demande vs alloué en temps réel, et renvoi atomique des allocations.
- `supervisor_override_dialog.py` : Boîte de dialogue de dérogation superviseur (`SupervisorOverrideDialog`). Déclenchée lors du dépassement du plafond de crédit autorisé lors d'une vente à crédit, requérant l'authentification sécurisée d'un administrateur/responsable (mot de passe ou code PIN) et un motif de justification enregistré dans l'historique.
- `pdf_export.py` : Module d'exportation PDF ReportLab (`export_wholesale_document_pdf`). Génère des documents commerciaux A4 complets avec en-tête d'entreprise, coordonnées client (NIF/RC), grille détaillée des lots/prix/remises/TVA, et récapitulatif financier.
- `__init__.py` : Point d'entrée du package exportant `WholesaleSalesTab` et `export_wholesale_document_pdf`.
