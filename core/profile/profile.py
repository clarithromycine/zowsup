from typing import Optional, Any
from ..config.manager import ConfigManager
from ..config.v1.config import Config
from ..axolotl.manager import AxolotlManager
from ..axolotl.factory import AxolotlManagerFactory
import logging

logger = logging.getLogger(__name__)


class YowProfile:
    def __init__(self, profile_name: str, config: Optional[Any] = None) -> None:
        """
        :param profile_name:  profile name
        :param config: A supplied config will disable loading configs using the Config manager and provide that config
        instead
        """
        logger.debug("Constructed Profile(profile_name=%s)" % profile_name)
        self._profile_name = profile_name
        self._config = config
        self._config_manager = ConfigManager()
        self._axolotl_manager = None

    def __str__(self) -> str:
        return "YowProfile(profile_name=%s)" % self._profile_name

    def _load_config(self) -> Any:
        logger.debug("load_config for %s" % self._profile_name)
        return self._config_manager.load(self._profile_name)

    def _load_axolotl_manager(self) -> Any:
        return AxolotlManagerFactory().get_manager(self._profile_name, self.username)

    def write_config(self, config: Optional[Any] = None) -> None:
        if config is None:
            config = self.config        
        logger.debug("write_config for %s" % self._profile_name)
        self._config_manager.save(self._profile_name, config) 

    @property
    def config(self) -> Any:
        if self._config is None:
            self._config = self._load_config()
        return self._config

    @property
    def axolotl_manager(self) -> Any:
        if self._axolotl_manager is None:
            self._axolotl_manager = self._load_axolotl_manager()
        return self._axolotl_manager

    @property
    def username(self) -> Any:
        config = self.config
        return config.login or config.phone or self._profile_name
