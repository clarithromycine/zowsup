from typing import Any
class LocationAttributes:
    def __init__(self,
                 degrees_latitude, degrees_longitude,
                 name=None, address=None, url=None,
                 accuracy_in_meters=None, speed_in_mps=None, degrees_clockwise_from_magnetic_north=None,
                 comment=None,jpeg_thumbnail=None,context_info=None) -> None:
        """
        :param degrees_latitude: Actual location, Place
        :param degrees_longitude:  Actual location, Place
        :param name: Place
        :param address: Place
        :param url: Place
        :param duration:
        :param accuracy_in_meters:
        :param speed_in_mps:
        :param degrees_clockwise_from_magnetic_north:
        :param axolotl_sender_key_distribution_message:
        :param jpeg_thumbnail: Actual location, Place
        """

        self._degrees_latitude = degrees_latitude
        self._degrees_longitude = degrees_longitude
        self._name = name
        self._address = address
        self._url = url        
        self._accuracy_in_meters = accuracy_in_meters
        self._speed_in_mps = speed_in_mps
        self._degrees_clockwise_from_magnetic_north = degrees_clockwise_from_magnetic_north
        self._comment = comment
        self._jpeg_thumbnail = jpeg_thumbnail        
        self._context_info = context_info


    def __str__(self):
        attrs = []
        if self.degrees_latitude is not None:
            attrs.append(("degrees_latitude", self.degrees_latitude))
        if self.degrees_longitude is not None:
            attrs.append(("degrees_longitude", self.degrees_longitude))
        if self.name is not None:
            attrs.append(("name", self.name))
        if self.address is not None:
            attrs.append(("address", self.address))
        if self.url is not None:
            attrs.append(("url", self.url))
        if self.accuracy_in_meters is not None:
            attrs.append(("accuracy_in_meters", self.accuracy_in_meters))
        if self.speed_in_mps is not None:
            attrs.append(("speed_in_mps", self.speed_in_mps))
        if self.degrees_clockwise_from_magnetic_north is not None:
            attrs.append(("degrees_clockwise_from_magnetic_north", self.degrees_clockwise_from_magnetic_north))
        if self.comment is not None:
            attrs.append("comment")
        if self.jpeg_thumbnail is not None:
            attrs.append(("jpeg_thumbnail", "[binary data]"))        

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def degrees_latitude(self) -> Any:
        return self._degrees_latitude

    @degrees_latitude.setter
    def degrees_latitude(self, value: Any) -> None:
        self._degrees_latitude = value

    @property
    def degrees_longitude(self) -> Any:
        return self._degrees_longitude

    @degrees_longitude.setter
    def degrees_longitude(self, value: Any) -> None:
        self._degrees_longitude = value

    @property
    def name(self) -> Any:
        return self._name

    @name.setter
    def name(self, value: Any) -> None:
        self._name = value

    @property
    def address(self) -> Any:
        return self._address

    @address.setter
    def address(self, value: Any) -> None:
        self._address = value

    @property
    def url(self) -> Any:
        return self._url

    @url.setter
    def url(self, value: Any) -> None:
        self._url = value

    @property
    def accuracy_in_meters(self) -> Any:
        return self._accuracy_in_meters

    @accuracy_in_meters.setter
    def accuracy_in_meters(self, value: Any) -> None:
        self._accuracy_in_meters = value

    @property
    def speed_in_mps(self) -> Any:
        return self._speed_in_mps

    @speed_in_mps.setter
    def speed_in_mps(self, value: Any) -> None:
        self._speed_in_mps = value

    @property
    def degrees_clockwise_from_magnetic_north(self) -> Any:
        return self._degrees_clockwise_from_magnetic_north

    @degrees_clockwise_from_magnetic_north.setter
    def degrees_clockwise_from_magnetic_north(self, value: Any) -> None:
        self._degrees_clockwise_from_magnetic_north = value

    @property
    def comment(self) -> Any:
        return self._comment

    @comment.setter
    def comment(self, value: Any) -> None:
        self._comment = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self._jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self._jpeg_thumbnail = value


    @property
    def context_info(self) -> Any:
        return self._context_info

    @context_info.setter
    def context_info(self, value: Any) -> None:
        self._context_info = value        
