from ...config.base.transform import ConfigTransform
from ...config.transforms.props import PropsTransform
from typing import Any, Optional, Dict, List, Tuple



class MetaPropsTransform(ConfigTransform):
    META_FORMAT = "__%s__"

    def __init__(self, meta_props=None, meta_format=META_FORMAT) -> None:
        meta_props = meta_props or ()
        meta_format = meta_format
        transform_map = {}
        reverse_map = {}
        for prop in meta_props:
            formatted = meta_format % prop
            transform_map[prop] = lambda key, val, formatted=formatted: (formatted, val)
            reverse_map[formatted] = lambda key, val, prop=prop: (prop, val)

        self._props_transform = PropsTransform(transform_map=transform_map, reverse_map=reverse_map)

    def transform(self, data) -> Any:
        return self._props_transform.transform(data)

    def reverse(self, data) -> Any:
        return self._props_transform.reverse(data)
