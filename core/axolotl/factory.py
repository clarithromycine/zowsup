from ..axolotl.manager import AxolotlManager
from ..common.tools import StorageTools
from ..axolotl.store.sqlite.liteaxolotlstore import LiteAxolotlStore
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class AxolotlManagerFactory:
    DB = "axolotl.db"

    def get_manager(self, profile_name: str, username: str) -> "AxolotlManager":
        logger.debug(f"get_manager(profile_name={profile_name}, username={username})")
        dbpath = StorageTools.constructPath(profile_name, self.DB)
        store = LiteAxolotlStore(dbpath)
        return AxolotlManager(store, username)
    


    

