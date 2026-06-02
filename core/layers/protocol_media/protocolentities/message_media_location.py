from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_location import LocationAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class LocationMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, location_attrs, message_meta_attrs) -> None:
        # type: (LocationAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "location", MessageAttributes(location=location_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.contact

    @property
    def degrees_latitude(self) -> Any:
        return self.media_specific_attributes.degrees_latitude

    @degrees_latitude.setter
    def degrees_latitude(self, value: Any) -> None:
        self.media_specific_attributes.degrees_latitude = value

    @property
    def degrees_longitude(self) -> Any:
        return self.media_specific_attributes.degrees_longitude

    @degrees_longitude.setter
    def degrees_longitude(self, value: Any) -> None:
        self.media_specific_attributes.degrees_longitude = value

    @property
    def name(self) -> Any:
        return self.media_specific_attributes.name

    @name.setter
    def name(self, value: Any) -> None:
        self.media_specific_attributes.name = value

    @property
    def address(self) -> Any:
        return self.proto.addrees

    @address.setter
    def address(self, value: Any) -> None:
        self.media_specific_attributes.address = value

    @property
    def url(self) -> Any:
        return self.media_specific_attributes.url

    @url.setter
    def url(self, value: Any) -> None:
        self.media_specific_attributes.url = value

    @property
    def duration(self) -> Any:
        return self.media_specific_attributes.duration

    @duration.setter
    def duration(self, value: Any) -> None:
        self.media_specific_attributes.duration = value

    @property
    def accuracy_in_meters(self) -> Any:
        return self.media_specific_attributes.accuracy_in_meters

    @accuracy_in_meters.setter
    def accuracy_in_meters(self, value: Any) -> None:
        self.media_specific_attributes.accuracy_in_meters = value

    @property
    def speed_in_mps(self) -> Any:
        return self.media_specific_attributes.speed_in_mps

    @speed_in_mps.setter
    def speed_in_mps(self, value: Any) -> None:
        self.media_specific_attributes.speed_in_mps = value

    @property
    def degrees_clockwise_from_magnetic_north(self) -> Any:
        return self.media_specific_attributes.degrees_clockwise_from_magnetic_north

    @degrees_clockwise_from_magnetic_north.setter
    def degrees_clockwise_from_magnetic_north(self, value: Any) -> None:
        self.media_specific_attributes.degrees_clockwise_from_magnetic_north = value

    @property
    def axolotl_sender_key_distribution_message(self) -> Any:
        return self.media_specific_attributes.axolotl_sender_key_distribution_message

    @axolotl_sender_key_distribution_message.setter
    def axolotl_sender_key_distribution_message(self, value: Any) -> None:
        self.media_specific_attributes.axolotl_sender_key_distribution_message = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self.media_specific_attributes.jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.jpeg_thumbnail = value
