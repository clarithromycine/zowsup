from .....layers.protocol_messages.protocolentities.attributes.attributes_image import ImageAttributes
from typing import Optional, Any, List, Dict, Union
from .....layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_document import DocumentAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_contact import ContactAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_location import LocationAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_video import VideoAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_audio import AudioAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_sticker import StickerAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_template import TemplateAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_sender_key_distribution_message import \
    SenderKeyDistributionMessageAttributes
from .....layers.protocol_messages.protocolentities.attributes.attributes_protocol import ProtocolAttributes


class MessageAttributes:
    def __init__(
            self,
            conversation=None,
            image=None,
            contact=None,
            location=None,
            extended_text=None,            
            document=None,
            audio=None,
            video=None,
            sticker=None,
            template=None,
            buttons=None,
            buttons_response=None,
            list = None,
            list_response = None,
            poll_creation = None,
            poll_update = None,
            product = None,
            interactive = None,
            reaction = None,
            sender_key_distribution_message=None,
            protocol=None,
            fromMe = False,
            to = None            
    ) -> None:
        self._conversation = conversation  # type: str
        self._image = image  # type: ImageAttributes
        self._contact = contact  # type: ContactAttributes
        self._location = location  # type: LocationAttributes
        self._extended_text = extended_text  # type: ExtendedTextAttributes        
        self._document = document  # type: DocumentAttributes
        self._audio = audio  # type: AudioAttributes
        self._video = video  # type: VideoAttributes
        self._sticker = sticker  # type: StickerAttributes
        self._template = template # type: TemplateAttributes
        self._buttons = buttons
        self._buttons_response = buttons_response
        self._poll_creation = poll_creation
        self._poll_update = poll_update
        self._list = list
        self._list_response = list_response
        self._product = product
        self._interactive = interactive
        self._reaction = reaction
        self._fromMe = fromMe
        self._to = to
        
        self._sender_key_distribution_message = \
            sender_key_distribution_message  # type: SenderKeyDistributionMessageAttributes
        self._protocol = protocol  # type: ProtocolAttributes

    def __str__(self):
        attrs = []
        if self.conversation is not None:
            attrs.append(("conversation", self.conversation))
        if self.image is not None:
            attrs.append(("image", self.image))
        if self.contact is not None:
            attrs.append(("contact", self.contact))
        if self.location is not None:
            attrs.append(("location", self.location))
        if self.extended_text is not None:
            attrs.append(("extended_text", self.extended_text))

        if self.document is not None:
            attrs.append(("document", self.document))
        if self.audio is not None:
            attrs.append(("audio", self.audio))
        if self.video is not None:
            attrs.append(("video", self.video))
        if self.sticker is not None:
            attrs.append(("sticker", self.sticker))
        if self.template is not None:
            attrs.append(("template", self.template))      
        if self.buttons is not None:
            attrs.append(("buttons", self.buttons))    
        if self._buttons_response is not None:
            attrs.append(("buttons_response", self.buttons_response))                        
        if self._poll_creation is not None:
            attrs.append(("poll_creation",self.poll_creation))
        if self._poll_update is not None:
            attrs.append(("poll_update",self.poll_update))            
        
        if self._list is not None:
            attrs.append(("list", self.list))                        
        if self._list_response is not None:
            attrs.append(("list_response", self.list_response))          
        if self._product is not None:
            attrs.append(("product", self.product))       

        if self._interactive is not None:
            attrs.append(("interactive", self.interactive))          


        if self._reaction is not None:
            attrs.append(("reaction", self.reaction))                        

        if self._sender_key_distribution_message is not None:
            attrs.append(("sender_key_distribution_message", self.sender_key_distribution_message))
        if self._protocol is not None:
            attrs.append(("protocol", self.protocol))
        if self.fromMe:
            attrs.append(("fromMe", self.fromMe))
            attrs.append(("to", self.to))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))



    @property
    def fromMe(self) -> Any:
        return self._fromMe

    @fromMe.setter
    def fromMe(self, value: Any) -> None:
        self._fromMe = value

    @property
    def to(self) -> Any:
        return self._to

    @to.setter
    def to(self, value: Any) -> None:
        self._to = value        

    @property
    def conversation(self) -> Any:
        return self._conversation

    @conversation.setter
    def conversation(self, value: Any) -> None:
        self._conversation = value

    @property
    def image(self) -> Any:
        return self._image

    @image.setter
    def image(self, value: Any) -> None:
        self._image = value

    @property
    def contact(self) -> Any:
        return self._contact

    @contact.setter
    def contact(self, value: Any) -> None:
        self._contact = value

    @property
    def location(self) -> Any:
        return self._location

    @location.setter
    def location(self, value: Any) -> None:
        self._location = value

    @property
    def extended_text(self) -> Any:
        return self._extended_text

    @extended_text.setter
    def extended_text(self, value: Any) -> None:
        self._extended_text = value

    @property
    def multitarget_extended_text(self) -> Any:
        return self._multitarget_extended_text

    @extended_text.setter
    def multitarget_extended_text(self, value: Any) -> None:
        self._multitarget_extended_text = value        

    @property
    def document(self) -> Any:
        return self._document

    @document.setter
    def document(self, value: Any) -> None:
        self._document = value

    @property
    def audio(self) -> Any:
        return self._audio

    @audio.setter
    def audio(self, value: Any) -> None:
        self._audio = value

    @property
    def video(self) -> Any:
        return self._video

    @video.setter
    def video(self, value: Any) -> None:
        self._video = value

    @property
    def sticker(self) -> Any:
        return self._sticker

    @sticker.setter
    def sticker(self, value: Any) -> None:
        self._sticker = value

    @property
    def template(self) -> Any:
        return self._template

    @template.setter
    def template(self, value: Any) -> None:
        self._template = value       

    @property
    def buttons(self) -> Any:
        return self._buttons

    @buttons.setter
    def buttons(self, value: Any) -> None:
        self._buttons = value     

    @property
    def buttons_response(self) -> Any:
        return self._buttons_response

    @buttons_response.setter
    def buttons_response(self, value: Any) -> None:
        self._buttons_response = value     

    @property
    def poll_creation(self) -> Any:
        return self._poll_creation

    @poll_creation.setter
    def poll_creation(self, value: Any) -> None:
        self._poll_creation = value                      

    @property
    def poll_update(self) -> Any:
        return self._poll_update

    @poll_update.setter
    def poll_update(self, value: Any) -> None:
        self._poll_update = value                      


    @property
    def list(self) -> Any:
        return self._list

    @list.setter
    def list(self, value: Any) -> None:
        self._list = value       

    @property
    def list_response(self) -> Any:
        return self._list_response

    @list_response.setter
    def list_response(self, value: Any) -> None:
        self._list_response = value        

    @property
    def product(self) -> Any:
        return self._product

    @product.setter
    def product(self, value: Any) -> None:
        self._product = value     

    @property
    def interactive(self) -> Any:
        return self._interactive

    @interactive.setter
    def interactive(self, value: Any) -> None:
        self._interactive = value         

    @property
    def reaction(self) -> Any:
        return self._reaction

    @reaction.setter
    def reaction(self, value: Any) -> None:
        self._reaction = value

    @property
    def sender_key_distribution_message(self) -> Any:
        return self._sender_key_distribution_message

    @sender_key_distribution_message.setter
    def sender_key_distribution_message(self, value: Any) -> None:
        self._sender_key_distribution_message = value

    @property
    def protocol(self) -> Any:
        return self._protocol

    @protocol.setter
    def protocol(self, value: Any) -> None:
        self._protocol = value
