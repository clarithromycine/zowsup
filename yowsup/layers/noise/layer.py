from ...layers.noise.workers.handshake import WANoiseProtocolHandshakeWorker
from ...layers import YowLayer, EventCallback
from ...layers.auth.layer_authentication import YowAuthenticationProtocolLayer
from ...layers.network.layer import YowNetworkLayer
from ...layers.noise.layer_noise_segments import YowNoiseSegmentsLayer
from ...layers import YowLayerEvent
from ...structs.protocoltreenode import ProtocolTreeNode
from ...layers.coder.encoder import WriteEncoder
from ...layers.coder.tokendictionary import TokenDictionary
from ...common.tools import WATools
from consonance.protocol import WANoiseProtocol
from consonance.config.client import ClientConfig
from consonance.config.useragent import UserAgentConfig
from consonance.streams.segmented.blockingqueue import BlockingQueueSegmentedStream
from consonance.structs.keypair import KeyPair
import threading,logging,uuid,base64
from common.utils import Utils
from app.yowbot_values import YowBotType

logger = logging.getLogger(__name__)
try:
    import Queue
except ImportError:
    import queue as Queue
class YowNoiseLayer(YowLayer):
    DEFAULT_PUSHNAME = "yowsup"
    HEADER = b'WA\x06\x03'
    EDGE_HEADER = b'ED\x00\x01'
    EVENT_HANDSHAKE_FAILED = "org.whatsapp.yowsup.layer.noise.event.handshake_failed"
    def __init__(self):
        super(YowNoiseLayer, self).__init__()
        self._wa_noiseprotocol = WANoiseProtocol(
            6, 3, protocol_state_callbacks=self._on_protocol_state_changed
        )  # type: WANoiseProtocol

        self._handshake_worker = None
        self._stream = BlockingQueueSegmentedStream()  # type: BlockingQueueSegmentedStream
        self._read_buffer = bytearray()
        self._flush_lock = threading.Lock()
        self._incoming_segments_queue = Queue.Queue()
        self._profile = None
        self._rs = None

    def __str__(self):
        return "Noise Layer"

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def on_disconnected(self, event):
        self._wa_noiseprotocol.reset()

    @EventCallback(YowAuthenticationProtocolLayer.EVENT_AUTH)
    def on_auth(self, event):        

        logger.debug("Received auth event")
        self._profile = self.getProp("profile")

        if self.getProp("botType")==YowBotType.TYPE_REG_COMPANION_SCANQR or self.getProp("botType")==YowBotType.TYPE_REG_COMPANION_LINKCODE:
                           
            keypair = self.getProp("reg_info")["keypair"]

            yowsupenv = self.getProp("env").deviceEnv

            '''
            if config.device_name is not None:
                yowsupenv._OS_NAME = config.os_name
                yowsupenv._OS_VERSION = config.os_version
                yowsupenv._MANUFACTURER = config.manufacturer
                yowsupenv._DEVICE_NAME = config.device_name
            else:
                #保存默认值
                config.os_name= yowsupenv.getOSName()
                config.os_version = yowsupenv.getOSVersion()
                config.manufacturer = yowsupenv.getManufacturer()
                config.device_name = yowsupenv.getDeviceName2()
                self._profile.write_config(config)
            '''

            passive = False
            
            #这个client_cofig 的结构是consonance里面的         
            client_config = ClientConfig(          
                username=None,
                pushname=None,                      
                passive=passive,
                useragent=UserAgentConfig(
                    platform=yowsupenv.getPlatform(),
                    app_version=yowsupenv.getVersion(),
                    mcc="000",
                    mnc="000",
                    os_version=yowsupenv.getOSVersion(),
                    manufacturer=yowsupenv.getManufacturer(),
                    device=yowsupenv.getDeviceName2(),
                    os_build_number=yowsupenv.getBuildVersion(),
                    phone_id=str(uuid.uuid4()),
                    locale_lang="en",
                    locale_country="US",
                    device_exp_id=base64.b64encode(WATools.generateDeviceId()).decode(),
                    device_type=0,          #PHONE
                    device_model_type=yowsupenv.getDeviceModelType()
                ),                
                short_connect=True
            )     

            regInfo = self.getProp("reg_info")
            regid  = regInfo["regid"]
            identity = regInfo["identity"]
            signedprekey = regInfo["signedprekey"]

            jid = self.getProp("jid")
            if jid is not None:
                r1,r2,deviceid = WATools.jidDecode(jid)

            self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, False)
            self.toLower(self.HEADER)            
            self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)                    
            
            if not self._in_handshake():
                logger.debug("Performing reg handshake")
                self._handshake_worker = WANoiseProtocolHandshakeWorker(
                    self._wa_noiseprotocol, self._stream, client_config, keypair,rs = None,                    
                    finish_callback = self.on_handshake_finished,
                    mode = "reg",
                    identity = identity,regid = regid,signedprekey = signedprekey,
                    deviceid = deviceid if jid is not None else None
                )
                logger.debug("Starting handshake worker")                
                self._stream.set_events_callback(self._handle_stream_event)
                self._handshake_worker.start()                
                        
        else :
            
            config = self._profile.config  # type: yowsup.config.v1.config.Config
            # event's keypair will override config's keypair
            local_static = config.client_static_keypair            
            username = int(self._profile.username)            
            device = config.device            
            
            if local_static is None:                
                logger.error("client_static_keypair is not defined in specified config, disconnecting")
                self.broadcastEvent(
                    YowLayerEvent(
                        YowNetworkLayer.EVENT_STATE_DISCONNECT,
                        reason="client_static_keypair is not defined in specified config"
                    )
                )
            else:

                
                if type(local_static) is bytes:
                    local_static = KeyPair.from_bytes(local_static)
                assert type(local_static) is KeyPair, type(local_static)
                passive =  event.getArg('passive')        
                yowsupenv = self.getProp("env").deviceEnv

                if config.fdid is None:
                    config.fdid = WATools.generatePhoneId(self.getProp("env"))
                    config.expid = WATools.generateDeviceId()
                    self._profile.write_config(config)                
                
                if config.device_name is not None:
                    yowsupenv.setOSName(config.os_name)
                    yowsupenv.setOSVersion(config.os_version)
                    yowsupenv.setManufacturer(config.manufacturer)
                    yowsupenv.setDeviceName(config.device_name)
                    yowsupenv.setDeviceModelType(config.device_model_type)
                else:
                    #保存默认值

                    config.os_name= yowsupenv.getOSName()
                    config.os_version = yowsupenv.getOSVersion()
                    config.manufacturer = yowsupenv.getManufacturer()
                    config.device_name = yowsupenv.getDeviceName2()
                    config.device_model_type = yowsupenv.getDeviceModelType()
                    
                    self._profile.write_config(config)


                self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, False)

                
                if config.edge_routing_info:                
                    self.toLower(self.EDGE_HEADER)
                    self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)
                    self.toLower(config.edge_routing_info)
                    self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, False)

                

                self.toLower(self.HEADER)
                self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)
                            
                remote_static = config.server_static_public
                self._rs = remote_static

                cc = Utils.getMobileCC(str(username))       
                lg,lc = Utils.getLGLC(cc)                
                
                client_config = ClientConfig(
                    username=username,
                    passive=passive,
                    useragent=UserAgentConfig(
                        platform=yowsupenv.getPlatform(),
                        app_version=yowsupenv.getVersion(),
                        mcc="000",
                        mnc="000",
                        os_version=yowsupenv.getOSVersion(),
                        manufacturer=yowsupenv.getManufacturer(),
                        device=yowsupenv.getDeviceName2(),
                        os_build_number=yowsupenv.getBuildVersion(),
                        phone_id=config.fdid or "",
                        locale_lang=lg,
                        locale_country=lc,
                        device_exp_id = base64.b64encode(config.expid).decode() if config.expid else "",                        
                        device_type=0,  #PHONE
                        device_model_type=yowsupenv.getDeviceModelType()
                    ),
                    pushname=config.pushname or self.DEFAULT_PUSHNAME,
                    short_connect=True                                      
                )

                if not self._in_handshake():
                    logger.debug("Performing handshake [username= %d, passive=%s]" % (username, passive) )
                    self._handshake_worker = WANoiseProtocolHandshakeWorker(
                        self._wa_noiseprotocol, self._stream, client_config, local_static, remote_static,
                        self.on_handshake_finished,
                        deviceid = int(device) if device is not None else None
                    )
                    logger.debug("Starting handshake worker")
                    self._stream.set_events_callback(self._handle_stream_event)
                    self._handshake_worker.start()

    def on_handshake_finished(self, e=None):
        # type: (Exception) -> None
        if e is not None:
            self.emitEvent(YowLayerEvent(self.EVENT_HANDSHAKE_FAILED, reason=e))
            data=WriteEncoder(TokenDictionary()).protocolTreeNodeToBytes(
                ProtocolTreeNode("failure", {"reason": str(e)})
            )
            self.toUpper(data)            
            logger.error("An error occurred during handshake, try login again.")

    def _in_handshake(self):
        """
        :return:
        :rtype: bool
        """
        return self._wa_noiseprotocol.state == WANoiseProtocol.STATE_HANDSHAKE

    def _on_protocol_state_changed(self, state):           
        if state == WANoiseProtocol.STATE_TRANSPORT:            
            if self._rs != self._wa_noiseprotocol.rs:
                if self._profile is not None:
                    config = self._profile.config
                    config.server_static_public = self._wa_noiseprotocol.rs                    
                    self._profile.write_config(config)
                    self._rs = self._wa_noiseprotocol.rs

            self._flush_incoming_buffer()

    def _handle_stream_event(self, event):        
        if event == BlockingQueueSegmentedStream.EVENT_WRITE:
            self.toLower(self._stream.get_write_segment())
        elif event == BlockingQueueSegmentedStream.EVENT_READ:
            self._stream.put_read_segment(self._incoming_segments_queue.get(block=True))

    def send(self, data):
        """
        :param data:
        :type data: bytearray | bytes
        :return:
        :rtype:
        """
        data = bytes(data) if type(data) is not bytes else data        
        self._wa_noiseprotocol.send(data)

    def _flush_incoming_buffer(self):
        self._flush_lock.acquire()
        while self._incoming_segments_queue.qsize():
            self.toUpper(self._wa_noiseprotocol.receive())
        self._flush_lock.release()

    def receive(self, data):
        """
        :param data:
        :type data: bytes
        :return:
        :rtype:
        """                    
        self._incoming_segments_queue.put(data)
        if not self._in_handshake():
            self._flush_incoming_buffer()
