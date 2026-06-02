from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_buttons_response import ButtonsResponseAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class ProductMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, product_attr, message_meta_attrs) -> None:
        # type: (ProductAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "product", MessageAttributes(product=product_attr), message_meta_attrs
        )

    @property
    def product_image(self) -> Any:
        return self.message_attributes.product.product_image

    @product_image.setter
    def product_image(self, value: Any) -> None:
        self.message_attributes.product.product_image = value

    @property
    def title(self) -> Any:
        return self.message_attributes.product.title

    @title.setter
    def title(self, value: Any) -> None:
        self.message_attributes.product.title = value

    @property
    def description(self) -> Any:
        return self.message_attributes.product.description

    @description.setter
    def description(self, value: Any) -> None:
        self.message_attributes.product.description = value

    @property
    def product_id(self) -> Any:
        return self.message_attributes.product.product_id

    @product_id.setter
    def product_id(self, value: Any) -> None:
        self.message_attributes.product.product_id = value

    @property
    def business_owner_jid(self) -> Any:
        return self.message_attributes.product.business_owner_jid

    @business_owner_jid.setter
    def business_owner_jid(self, value: Any) -> None:
        self.message_attributes.product.business_owner_jid = value