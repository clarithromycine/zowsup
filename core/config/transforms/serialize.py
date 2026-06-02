from ...config.transforms.props import PropsTransform
from typing import Any, Optional, Dict, List, Tuple



class SerializeTransform(PropsTransform):

    def __init__(self, serialize_map) -> None:
        """
        {
            "keystore": serializer
        }
        :param serialize_map:
        :type serialize_map:
        """
        transform_map = {}
        reverse_map = {}
        for key, val in serialize_map:
            transform_map[key] = lambda key, val: key, serialize_map[key].serialize(val)
            reverse_map[key] = lambda key, val: key, serialize_map[key].deserialize(val)

        super().__init__(transform_map=transform_map, reverse_map=reverse_map)

