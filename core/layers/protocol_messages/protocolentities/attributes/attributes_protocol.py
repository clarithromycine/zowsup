from .....layers.protocol_messages.protocolentities.attributes.attributes_message_key import MessageKeyAttributes
from typing import Optional, Any, List, Dict, Union


class ProtocolAttributes:
    TYPE_REVOKE = 0
    TYPE_EPHEMERAL_SETTING = 3
    TYPE_EPHEMERAL_SYNC_RESPONSE = 4
    TYPE_HISTORY_SYNC_NOTIFICATION = 5
    TYPE_APP_STATE_SYNC_KEY_SHARE = 6
    TYPE_APP_STATE_SYNC_KEY_REQUEST = 7
    TYPE_MSG_FANOUT_BACKFILL_REQUEST = 8
    TYPE_INITIAL_SECURITY_NOTIFICATION_SETTING_SYNC = 9
    TYPE_APP_STATE_FATAL_EXCEPTION_NOTIFICATION = 10
    TYPE_SHARE_PHONE_NUMBER = 11
    TYPE_MESSAGE_EDIT = 14
    TYPE_PEER_DATA_OPERATION_REQUEST_MESSAGE = 16
    TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE = 17
    TYPE_REQUEST_WELCOME_MESSAGE = 18
    TYPE_BOT_FEEDBACK_MESSAGE = 19
    TYPE_MEDIA_NOTIFY_MESSAGE = 20    

    TYPES = {
        TYPE_REVOKE: "REVOKE", 
        TYPE_EPHEMERAL_SETTING:"EPHEMERAL_SETTING",
        TYPE_EPHEMERAL_SYNC_RESPONSE:"EPHEMERAL_SYNC_RESPONSE",        
        TYPE_HISTORY_SYNC_NOTIFICATION :"HISTORY_SYNC_NOTIFICATION",
        TYPE_APP_STATE_SYNC_KEY_SHARE :"APP_STATE_SYNC_KEY_SHARE",
        TYPE_APP_STATE_SYNC_KEY_REQUEST:"APP_STATE_SYNC_KEY_REQUEST",
        TYPE_MSG_FANOUT_BACKFILL_REQUEST:"MSG_FANOUT_BACKFILL_REQUEST",            
        TYPE_INITIAL_SECURITY_NOTIFICATION_SETTING_SYNC :"INITIAL_SECURITY_NOTIFICATION_SETTING_SYNC",
        TYPE_APP_STATE_FATAL_EXCEPTION_NOTIFICATION :"APP_STATE_FATAL_EXCEPTION_NOTIFICATION",
        TYPE_SHARE_PHONE_NUMBER:"SHARE_PHONE_NUMBER",
        TYPE_MESSAGE_EDIT:"MESSAGE_EDIT",
        TYPE_PEER_DATA_OPERATION_REQUEST_MESSAGE:"PEER_DATA_OPERATION_REQUEST_MESSAGE",
        TYPE_REQUEST_WELCOME_MESSAGE:"REQUEST_WELCOME_MESSAGE",
        TYPE_BOT_FEEDBACK_MESSAGE:"BOT_FEEDBACK_MESSAGE",
        TYPE_MEDIA_NOTIFY_MESSAGE:"MEDIA_NOTIFY_MESSAGE"
    }

    def __init__(self, 
                 key=None, 
                 type=None,
                 ephemeral_expiration=None,
                 ephemeral_setting_timestamp=None,
                 history_sync_notification=None,
                 app_state_sync_key_share=None,
                 app_state_sync_key_request=None,
                 initial_security_notification_setting_sync=None,
                 app_state_fatal_exception_notification=None,
                 disappearing_mode=None,
                 edited_message=None,
                 timestamp_ms=None,
                 peer_data_operation_request_message=None,
                 peer_data_operation_request_response_message=None,
                 bot_feedback_message=None,
                 request_welcome_message_metadata=None,
                 media_notify_message=None
                ) -> None:
        self._key = key
        self._type = type
        self._initial_security_notification_setting_sync = initial_security_notification_setting_sync
        self._ephemeral_expiration=ephemeral_expiration
        self._ephemeral_setting_timestamp=ephemeral_setting_timestamp
        self._history_sync_notification=history_sync_notification
        self._app_state_sync_key_share=app_state_sync_key_share
        self._app_state_sync_key_request=app_state_sync_key_request
        self._app_state_fatal_exception_notification=app_state_fatal_exception_notification
        self._disappearing_mode=disappearing_mode
        self._edited_message=edited_message
        self._timestamp_ms=timestamp_ms
        self._peer_data_operation_request_message=peer_data_operation_request_message
        self._peer_data_operation_request_response_message=peer_data_operation_request_response_message
        self._bot_feedback_message=bot_feedback_message
        self._request_welcome_message_metadata=request_welcome_message_metadata
        self._media_notify_message=media_notify_message

    def __str__(self):
        return f"[type={self.TYPES[self.type]}, key={self.key}]"

    @property
    def key(self) -> Any:
        return self._key

    @key.setter
    def key(self, value: Any) -> None:
        assert isinstance(value, MessageKeyAttributes), type(value)
        self._key = value

    @property
    def type(self) -> Any:
        return self._type

    @type.setter
    def type(self, value: Any) -> None:
        assert value in self.TYPES, "Unknown type: %s" % value
        self._type = value

    @property
    def initial_security_notification_setting_sync(self) -> Any:
        return self._initial_security_notification_setting_sync

    @initial_security_notification_setting_sync.setter
    def initial_security_notification_setting_sync(self, value: Any) -> None:        
        self._initial_security_notification_setting_sync = value

    @property
    def ephemeral_expiration(self) -> Any:
        return self._ephemeral_expiration

    @ephemeral_expiration.setter
    def ephemeral_expiration(self, value: Any) -> None:        
        self._ephemeral_expirationc = value

    @property
    def history_sync_notification(self) -> Any:
        return self._history_sync_notification

    @history_sync_notification.setter
    def history_sync_notification(self, value: Any) -> None:        
        self._history_sync_notification = value    

    @property
    def app_state_sync_key_share(self) -> Any:
        return self._app_state_sync_key_share

    @app_state_sync_key_share.setter
    def app_state_sync_key_share(self, value: Any) -> None:        
        self._app_state_sync_key_share = value    

    @property
    def app_state_sync_key_request(self) -> Any:
        return self._app_state_sync_key_request

    @app_state_sync_key_request.setter
    def app_state_sync_key_request(self, value: Any) -> None:        
        self._app_state_sync_key_request = value   

    @property
    def app_state_fatal_exception_notification(self) -> Any:
        return self._app_state_fatal_exception_notification

    @app_state_fatal_exception_notification.setter
    def app_state_fatal_exception_notification(self, value: Any) -> None:        
        self._app_state_fatal_exception_notification = value   

    @property
    def disappearing_mode(self) -> Any:
        return self._disappearing_mode

    @disappearing_mode.setter
    def disappearing_mode(self, value: Any) -> None:        
        self._disappearing_mode = value   

    @property
    def edited_message(self) -> Any:
        return self._edited_message

    @edited_message.setter
    def edited_message(self, value: Any) -> None:        
        self._edited_message = value   

    @property
    def timestamp_ms(self) -> Any:
        return self._timestamp_ms

    @timestamp_ms.setter
    def timestamp_ms(self, value: Any) -> None:        
        self._timestamp_ms = value      

    @property
    def peer_data_operation_request_message(self) -> Any:
        return self._peer_data_operation_request_message

    @peer_data_operation_request_message.setter
    def peer_data_operation_request_message(self, value: Any) -> None:        
        self._peer_data_operation_request_message = value  

    @property
    def bot_feedback_message(self) -> Any:
        return self._bot_feedback_message

    @bot_feedback_message.setter
    def bot_feedback_message(self, value: Any) -> None:        
        self._bot_feedback_message = value  

    @property
    def invoker_jid(self) -> Any:
        return self._invoker_jid

    @invoker_jid.setter
    def invoker_jid(self, value: Any) -> None:        
        self._invoker_jid = value  

    @property
    def request_welcome_message_metadata(self) -> Any:
        return self._request_welcome_message_metadata

    @request_welcome_message_metadata.setter
    def request_welcome_message_metadata(self, value: Any) -> None:        
        self._request_welcome_message_metadata = value  

    @property
    def media_notify_message(self) -> Any:
        return self._media_notify_message

    @media_notify_message.setter
    def media_notify_message(self, value: Any) -> None:        
        self._media_notify_message = value                                                                                          

