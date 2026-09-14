# Database Base Components (`database/base`)

Ce dossier contient les modules d'infrastructure de base pour la connexion, l'initialisation et la gestion des sauvegardes de la base de données MySQL.

## Fichiers et Rôles

- `__init__.py` : Expose les classes de base (`Database`, `ConfigManager`, `BackupManager`).
- `config.py` : Gestion des paramètres de configuration et de connexion à la base de données.
- `connection.py` : Gestion du pool de connexions MySQL et exécution sécurisée des requêtes.
- `database.py` : Classe principale d'abstraction et d'agrégation de tous les gestionnaires métier, incluant la synchronisation et la liste exhaustive des permissions système (`ALL_PERMISSIONS`, `get_all_permissions`).
- `schema_initializer.py` : Initialisation automatique des tables, contraintes et permissions granulaires système (`_ALL_PERMISSIONS`).
- `backup_manager.py` : Sauvegarde, compression chiffrée et restauration de la base de données.
- `archive_view_manager.py` : Gestion et consultation des archives historiques.
- `_.py` : Utilitaires internes et helpers de base de données.
