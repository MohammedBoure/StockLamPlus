# UI Widgets - Paramètres (`ui/widgets/settings`)

Configuration générale, éditeurs visuels d'étiquettes/tickets et journaux d'audit.

## Fichiers et Rôles

- `settings_tab.py` : Onglet principal des paramètres de l'application orchestrant les sous-onglets de configuration.
- `lab_info_tab.py` : Onglet dédié aux informations administratives et d'identification du laboratoire (Nom, Adresse, NIF, RC).
- `auto_backup_tab.py` : Onglet dédié aux sauvegardes automatiques en arrière-plan et aux opérations de sauvegarde/restauration manuelles.
- `local_settings.py` : Persistance locale des préférences utilisateurs.
- `system_logs_tab.py` : Consultation des journaux d'audit système.
- `receipt_config.py` : Paramètres d'impression des tickets de caisse.
- `receipt_visual_editor.py` : Éditeur visuel interactif de mise en page des tickets.
- `barcode_visual_editor.py` : Éditeur visuel interactif pour les étiquettes code-barres.
- `pdf_config_tab.py` : Onglet de configuration des documents PDF (BL, BR, PO).
- `pdf_visual_editor.py` : Éditeur visuel interactif de disposition des en-têtes/tampons PDF.
