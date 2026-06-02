from ...config.base import serialize
from ...config.transforms.filter import FilterTransform
from ...config.transforms.meta import MetaPropsTransform
from ...config.transforms.map import MapTransform
from ...config.transforms.config_dict import ConfigDictTransform
from ...config.transforms.props import PropsTransform

from consonance.structs.keypair import KeyPair
from consonance.structs.publickey import PublicKey
import base64


class ConfigSerialize(serialize.ConfigSerialize):
    def __init__(self, config_class):
        super().__init__(
            transforms=(
                ConfigDictTransform(config_class),
                FilterTransform(
                    transform_filter=lambda key, val: val is not None,
                    reverse_filter=lambda key, val: key != "version"
                ),
                MapTransform(transform_map=lambda key, val: (key[1:], val)),
                PropsTransform(
                    transform_map={
                        "server_static_public": lambda key, val: (key, base64.b64encode(val.data).decode()),
                        "client_static_keypair": lambda key, val: (key, base64.b64encode(val.private.data + val.public.data).decode()),
                        "id": lambda key, val: (key, base64.b64encode(val).decode()),
                        "expid": lambda key, val: (key, base64.b64encode(val).decode()),
                        "edge_routing_info": lambda key, val: (key, base64.b64encode(val).decode()),
                        "fcm_cat": lambda key, val: (key, base64.b64encode(val).decode())
                    },
                    reverse_map={
                        "server_static_public": lambda key, val: (key, PublicKey(base64.b64decode(val))),
                        "client_static_keypair": lambda key, val: (key, KeyPair.from_bytes(base64.b64decode(val))),
                        "id": lambda key, val: (key, base64.b64decode(val)),
                        "expid": lambda key, val: (key, base64.b64decode(val)),
                        "edge_routing_info": lambda key, val: (key, base64.b64decode(val)),
                        "fcm_cat": lambda key, val: (key, base64.b64decode(val))
                    }
                ),
                MetaPropsTransform(meta_props=("version", )),
            )
        )
