from ...config.base.transform import ConfigTransform
from typing import Any, Optional, Dict, List, Tuple



class ConfigDictTransform(ConfigTransform):
    def __init__(self, cls) -> None:
        self._cls = cls

    def transform(self, config) -> Any:
        """
        :param config:
        :type config: dict
        :return:
        :rtype: yowsup.config.config.Config
        """
        out = {}
        for prop in vars(config):
            out[prop] = getattr(config, prop)
        return out

    def reverse(self, data) -> Any:
        """
        :param data:
        :type data: yowsup,config.config.Config
        :return:
        :rtype: dict
        """
        return self._cls(**data)
