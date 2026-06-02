from ...config.base import config
import logging
from typing import Optional, Any, List

logger = logging.getLogger(__name__)


class Config(config.Config):
    def __init__(self, phone: Optional[Any] = None, cc: Optional[Any] = None, login: Optional[Any] = None, pushname: Optional[Any] = None, id: Optional[Any] = None, mcc: Optional[Any] = None, mnc: Optional[Any] = None, sim_mcc: Optional[Any] = None, sim_mnc: Optional[Any] = None, client_static_keypair: Optional[Any] = None, server_static_public: Optional[Any] = None, expid: Optional[Any] = None, fdid: Optional[Any] = None, edge_routing_info: Optional[Any] = None, chat_dns_domain: Optional[Any] = None, device: Optional[Any] = None, device_identity: Optional[Any] = None, device_list: Optional[Any] = None, # 主号专用，记录其它companion的index_id数组
            lid: Optional[Any] = None, platform: Optional[Any] = None, os_name: Optional[Any] = None, os_version: Optional[Any] = None, manufacturer: Optional[Any] = None, device_name: Optional[Any] = None, device_model_type: Optional[Any] = None, c2dm_reg_id: Optional[Any] = None, fcm_creds: Optional[Any] = None, fcm_cat: Optional[Any] = None, aid: Optional[Any] = None, ge: Optional[Any] = None, ga: Optional[Any] = None, gp: Optional[Any] = None) -> None:
        super().__init__(1)

        self._phone = str(phone) if phone is not None else None  # type: str
        self._cc = cc  # type: int
        self._login = str(login) if login is not None else None # type: str
        self._pushname = pushname  # type: str
        self._id = id
        self._client_static_keypair = client_static_keypair
        self._server_static_public = server_static_public
        self._expid = expid
        self._fdid = fdid
        self._mcc = mcc
        self._mnc = mnc
        self._sim_mcc = sim_mcc
        self._sim_mnc = sim_mnc
        self._edge_routing_info = edge_routing_info
        self._chat_dns_domain = chat_dns_domain
        self._device = device        
        self._device_identity = device_identity
        self._device_list = device_list
        self._lid = lid

        self._platform = platform
        self._os_name = os_name
        self._os_version=os_version
        self._manufacturer=manufacturer
        self._device_name=device_name
        self._device_model_type = device_model_type

        self._c2dm_reg_id = c2dm_reg_id
        self._fcm_creds = fcm_creds
        self._fcm_cat = fcm_cat

        self._aid = aid
        self._ge = ge
        self._ga = ga
        self._gp = gp

    def __str__(self) -> str:
        from ...config.v1.serialize import ConfigSerialize
        from ...config.transforms.dict_json import DictJsonTransform
        return DictJsonTransform().transform(ConfigSerialize(self.__class__).serialize(self))

    @property
    def phone(self) -> Any:
        return self._phone

    @phone.setter
    def phone(self, value: Any) -> None:
        self._phone = str(value) if value is not None else None

    @property
    def cc(self) -> Any:
        return self._cc

    @cc.setter
    def cc(self, value: Any) -> None:
        self._cc = value

    @property
    def login(self) -> Any:
        return self._login

    @login.setter
    def login(self, value: Any) -> None:
        self._login= value

    @property
    def pushname(self) -> Any:
        return self._pushname

    @pushname.setter
    def pushname(self, value: Any) -> None:
        self._pushname = value

    @property
    def mcc(self) -> Any:
        return self._mcc

    @mcc.setter
    def mcc(self, value: Any) -> None:
        self._mcc = value

    @property
    def mnc(self) -> Any:
        return self._mnc

    @mnc.setter
    def mnc(self, value: Any) -> None:
        self._mnc = value

    @property
    def sim_mcc(self) -> Any:
        return self._sim_mcc

    @sim_mcc.setter
    def sim_mcc(self, value: Any) -> None:
        self._sim_mcc = value

    @property
    def sim_mnc(self) -> Any:
        return self._sim_mnc

    @sim_mnc.setter
    def sim_mnc(self, value: Any) -> None:
        self._sim_mnc = value

    @property
    def id(self) -> Any:
        return self._id

    @id.setter
    def id(self, value: Any) -> None:
        self._id = value

    @property
    def client_static_keypair(self) -> Any:
        return self._client_static_keypair

    @client_static_keypair.setter
    def client_static_keypair(self, value: Any) -> None:
        self._client_static_keypair = value

    @property
    def server_static_public(self) -> Any:
        return self._server_static_public

    @server_static_public.setter
    def server_static_public(self, value: Any) -> None:
        self._server_static_public = value

    @property
    def expid(self) -> Any:
        return self._expid

    @expid.setter
    def expid(self, value: Any) -> None:
        self._expid = value

    @property
    def fdid(self) -> Any:
        return self._fdid

    @fdid.setter
    def fdid(self, value: Any) -> None:
        self._fdid = value

    @property
    def edge_routing_info(self) -> Any:
        return self._edge_routing_info

    @edge_routing_info.setter
    def edge_routing_info(self, value: Any) -> None:
        self._edge_routing_info = value

    @property
    def chat_dns_domain(self) -> Any:
        return self._chat_dns_domain

    @chat_dns_domain.setter
    def chat_dns_domain(self, value: Any) -> None:
        self._chat_dns_domain = value

    @property
    def device(self) -> Any:
        return self._device

    @device.setter
    def device(self, value: Any) -> None:
        self._device = value        

    @property
    def device_identity(self) -> Any:
        return self._device_identity

    @device_identity.setter
    def device_identity(self, value: Any) -> None:
        self._device_identity = value          

    @property
    def device_list(self) -> Any:
        return self._device_list

    @device_list.setter
    def device_list(self, value: Any) -> None:
        self._device_list = value          


    def get_new_device_index(self) -> int:
        if  self._device_list is None:
            new_id =1
        else:
            new_id = max(self._device_list)+1       
        return new_id 
    
    def add_device_to_list(self, value: Any) -> List[Any]:        
        if self._device_list is None:
            self._device_list = []        
        self._device_list.append(value)        
        return self._device_list
        
    @property
    def platform(self) -> Any:
        return self._platform

    @platform.setter
    def platform(self, value: Any) -> None:
        self._platform = value   

    @property
    def os_name(self) -> Any:
        return self._os_name

    @os_name.setter
    def os_name(self, value: Any) -> None:
        self._os_name = value  

    @property
    def os_version(self) -> Any:
        return self._os_version

    @os_version.setter
    def os_version(self, value: Any) -> None:
        self._os_version = value   

    @property
    def manufacturer(self) -> Any:
        return self._manufacturer

    @manufacturer.setter
    def manufacturer(self, value: Any) -> None:
        self._manufacturer = value   

    @property
    def device_name(self) -> Any:
        return self._device_name

    @device_name.setter
    def device_name(self, value: Any) -> None:
        self._device_name = value   

    @property
    def device_model_type(self) -> Any:
        return self._device_model_type

    @device_model_type.setter
    def device_model_type(self, value: Any) -> None:
        self._device_model_type = value   

    @property
    def os_build_number(self) -> Any:
        return self._os_build_number

    @os_build_number.setter
    def os_build_number(self, value: Any) -> None:
        self._os_build_number = value   

    @property
    def c2dm_reg_id(self) -> Any:
        return self._c2dm_reg_id

    @c2dm_reg_id.setter
    def c2dm_reg_id(self,value):
        self._c2dm_reg_id = value

    @property
    def fcm_creds(self) -> Any:
        return self._fcm_creds

    @fcm_creds.setter
    def fcm_creds(self,value):
        self._fcm_creds = value

    @property
    def fcm_cat(self) -> Any:
        return self._fcm_cat

    @fcm_cat.setter
    def fcm_cat(self,value):
        self._fcm_cat = value

    @property
    def aid(self) -> Any:
        return self._aid

    @aid.setter
    def aid(self,value):
        self._aid = value        

    @property
    def ge(self) -> Any:
        return self._ge

    @ge.setter
    def ge(self,value):
        self._ge = value                


    @property
    def ga(self) -> Any:
        return self._ga

    @ga.setter
    def ga(self,value):
        self._ga = value                


    @property
    def gp(self) -> Any:
        return self._gp

    @gp.setter
    def gp(self,value):
        self._gp = value            

    @property
    def lid(self) -> Any:
        return self._lid

    @lid.setter
    def lid(self,value):
        self._lid = value