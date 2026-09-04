# Tests Unitaires (`test`)

Suite de tests automatisés vérifiant le bon fonctionnement des modules backend, des APIs mobiles et des utilitaires de formatage.

## Fichiers et Rôles

- `__init__.py` : Initialisation du package de tests.
- `test_ui_formatting.py` : Validation du formatage monétaire (espace milliers, virgule décimale) et des quantités.
- `test_inventory_mobile_api.py` : Tests d'intégration de l'API REST mobile (sessions, scans, consommations, transferts).
- `test_inventory_count_manager.py` : Tests du gestionnaire de sessions d'inventaire physique.
- `test_inventory_count_ui.py` : Tests de l'interface graphique de comptage d'inventaire.
- `test_local_settings.py` : Tests du stockage des préférences locales.
- `test_navigation_permissions.py` : Tests du contrôle d'accès et des permissions de navigation.
- `test_receipt_config.py` : Tests de configuration des reçus et tickets.
- `test_history_widget.py` : Tests de la vue d'historique et de traçabilité.
- `test_theme_and_settings_fixes.py` : Tests de séparation des onglets de paramètres (Laboratoire et Sauvegarde Automatique) et corrections visuelles (tailles de champs dates, code-barres).
