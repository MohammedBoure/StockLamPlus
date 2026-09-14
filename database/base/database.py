# database/base/database.py
import logging

from .connection import Database as _DatabaseBase
from .schema_initializer import SchemaInitializerMixin, _ALL_PERMISSIONS
from .backup_manager import BackupManagerMixin
from .archive_view_manager import ArchiveViewManagerMixin

ALL_PERMISSIONS = _ALL_PERMISSIONS


class Database(SchemaInitializerMixin, BackupManagerMixin, ArchiveViewManagerMixin, _DatabaseBase):
    """
    Main Database class.

    Assembled from focused mixins:
      - connection.py         → connection pool, get_db_connection, get_raw_connection
      - schema_initializer.py → _initialize_schema (CREATE TABLE, migrations, indexes)
      - backup_manager.py     → CSV / Excel backup & restore, export_and_purge_tables
      - archive_view_manager.py → activate/deactivate archive view mode
    """

    @classmethod
    def get_all_permissions(cls):
        """Retourne la liste complète de toutes les permissions gérées par le système."""
        return list(_ALL_PERMISSIONS)

    def sync_admin_permissions(self):
        """Assure que le compte administrateur possède l'ensemble des permissions existantes."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                self._ensure_default_admin(cursor)
                conn.commit()
                logging.info("Admin permissions synchronized successfully.")
                return True
        except Exception as e:
            logging.error(f"Error synchronizing admin permissions: {e}")
            return False
