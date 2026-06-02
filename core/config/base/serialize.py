from typing import Any, Optional, Dict, List, Tuple

class ConfigSerialize:

    def __init__(self, transforms) -> None:
        self._transforms = transforms

    def serialize(self, config) -> Any:
        """
        :param config:
        :type config: yowsup.config.base.config.Config
        :return:
        :rtype: bytes
        """
        for transform in self._transforms:
            config = transform.transform(config)
        return config

    def deserialize(self, data) -> Any:
        """
        :type cls: type
        :param data:
        :type data: bytes
        :return:
        :rtype: yowsup.config.base.config.Config
        """
        for transform in self._transforms[::-1]:
            data = transform.reverse(data)
        return data
