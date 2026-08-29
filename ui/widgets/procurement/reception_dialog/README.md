# UI Widgets - Boîte de Dialogue de Réception (`ui/widgets/procurement/reception_dialog`)

Composants dédiés à la saisie et validation des réceptions de commandes (Bons de Réception).

## Fichiers et Rôles

- `__init__.py` : Expose `ReceptionDialog`.
- `reception_dialog.py` : Classe principale de la boîte de dialogue de réception.
- `reception_dialog_ui.py` : Mixin construisant l'interface graphique et les champs de saisie.
- `reception_dialog_logic.py` : Mixin contenant la logique métier, les calculs de taxes et la validation.
- `auto_select_widgets.py` : Widgets d'entrée avec sélection automatique du texte au focus.
