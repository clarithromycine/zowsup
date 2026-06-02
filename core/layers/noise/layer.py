from ...layers import YowLayer, EventCallback
from typing import Optional, Any, List, Dict, Union
from ...layers.auth.layer_authentication import YowAuthenticationProtocolLayer
from ...layers.network.layer import YowNetworkLayer
from ...layers.noise.layer_noise_segments import YowNoiseSegmentsLayer
from ...layers import YowLayerEvent
from ...structs.protocoltreenode import ProtocolTreeNode
from ...layers.coder.encoder import WriteEncoder
from ...layers.coder.tokendictionary import TokenDictionary
from ...common.tools import WATools
from consonance.async_protocol import WANoiseProtocolAsync
from consonance.config.client import ClientConfig
from consonance.config.useragent import UserAgentConfig
from consonance.streams.segmented.async_layer import AsyncLayerSegmentedStream
from consonance.structs.keypair import KeyPair
import asyncio
import logging,uuid,base64
from common.utils import Utils
from app.zowbot_values import ZowBotType

logger = logging.getLogger(__name__)

class YowNoiseLayer(YowLayer):
    DEFAULT_PUSHNAME = "yowsup"
    HEADER = b'WA\x06\x03'
    EDGE_HEADER = b'ED\x00\x01'
    EVENT_HANDSHAKE_FAILED = "org.whatsapp.yowsup.layer.noise.event.handshake_failed"
    def __init__(self) -> None:
        super().__init__()
        self._wa_noiseprotocol = WANoiseProtocolAsync(
            6, 3, protocol_state_callbacks=self._on_protocol_state_changed
        )

        self._handshake_task = None
        self._stream = AsyncLayerSegmentedStream(self._write_to_lower)
        self._profile = None
        self._rs = None

    def __str__(self):
        return "Noise Layer"

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def on_disconnected(self, event) -> Any:
        if self._handshake_task is not None and not self._handshake_task.done():
            self._handshake_task.cancel()
            self._handshake_task = None
        self._wa_noiseprotocol.reset()
        self._stream = AsyncLayerSegmentedStream(self._write_to_lower)

    async def _write_to_lower(self, data) -> Any:
        """Write callback for AsyncLayerSegmentedStream → routes through layer pipeline."""
        await self.toLower(data)

    @EventCallback(YowAuthenticationProtocolLayer.EVENT_AUTH)
    async def on_auth(self, event) -> Any:        

        logger.debug("Received auth event")
        self._profile = self.getProp("profile")

        if self.getProp("botType")==ZowBotType.TYPE_REG_COMPANION_SCANQR or self.getProp("botType")==ZowBotType.TYPE_REG_COMPANION_LINKCODE:
                           
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

            passive = True
            
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
            await self.toLower(self.HEADER)            
            self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)                    
            
            if not self._in_handshake():
                logger.debug("Performing reg handshake")
                self._handshake_task = asyncio.ensure_future(
                    self._do_handshake(
                        client_config, keypair, rs=None,
                        mode="reg",
                        identity=identity, regid=regid, signedprekey=signedprekey,
                        deviceid=deviceid if jid is not None else None
                    )
                )                
                        
        else :
            
            config = self._profile.config  # type: yowsup.config.v1.config.Config
            # event's keypair will override config's keypair
            local_static = config.client_static_keypair            
            username = int(self._profile.username)            
            device = config.device            
            
            if local_static is None:                
                logger.error("client_static_keypair is not defined in specified config, disconnecting")
                await self.broadcastEvent(
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
                    await self.toLower(self.EDGE_HEADER)
                    self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)
                    await self.toLower(config.edge_routing_info)
                    self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, False)

                

                await self.toLower(self.HEADER)
                self.setProp(YowNoiseSegmentsLayer.PROP_ENABLED, True)
                            
                remote_static = config.server_static_public
                self._rs = remote_static

                cc = Utils.getMobileCC(str(username))       
                lg,lc = Utils.getLGLC(cc)                
                
                client_config = ClientConfig(
                    username=username,
                    passive=False,
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
                    self._handshake_task = asyncio.ensure_future(
                        self._do_handshake(
                            client_config, local_static, rs=remote_static,
                            deviceid=int(device) if device is not None else None
                        )
                    )

    async def _do_handshake(self, client_config, keypair, rs=None, **kwargs) -> Any:
        """Run the noise handshake as an asyncio coroutine (replaces HandshakeWorker thread)."""
        try:
            await self._wa_noiseprotocol.start(
                self._stream, client_config, keypair, rs, **kwargs
            )
            logger.debug("Handshake completed successfully")
            # Drain any application data segments that arrived in the same TCP
            # packet as the final handshake message.  During IK handshake the
            # server may push app data immediately after its response; these
            # segments were fed into _stream._read_queue but skipped by
            # receive() because _in_handshake() was still True at that point.
            await self._drain_pending_segments()
        except Exception as e:
            logger.error("An error occurred during handshake, try login again.")
            await self.emitEvent(YowLayerEvent(self.EVENT_HANDSHAKE_FAILED, reason=e))
            data = WriteEncoder(TokenDictionary()).protocolTreeNodeToBytes(
                ProtocolTreeNode("failure", {"reason": str(e)})
            )
            await self.toUpper(data)

    async def _drain_pending_segments(self) -> Any:
        """Process any segments already queued during the handshake phase."""
        queue = self._stream._read_queue
        while not queue.empty():
            try:
                decrypted = await self._wa_noiseprotocol.receive()
                logger.debug("Drained pending segment (%d bytes)", len(decrypted))
                await self.toUpper(decrypted)
            except Exception:
                logger.exception("Error draining pending segment")
                break

    def _in_handshake(self) -> Any:
        return self._wa_noiseprotocol.state == WANoiseProtocolAsync.STATE_HANDSHAKE

    def _on_protocol_state_changed(self, state) -> Any:
        if state == WANoiseProtocolAsync.STATE_TRANSPORT:
            if self._rs != self._wa_noiseprotocol.rs:
                if self._profile is not None:
                    config = self._profile.config
                    config.server_static_public = self._wa_noiseprotocol.rs
                    self._profile.write_config(config)
                    self._rs = self._wa_noiseprotocol.rs

    async def send(self, data) -> Any:
        data = bytes(data) if type(data) is not bytes else data
        await self._wa_noiseprotocol.send(data)

    async def receive(self, data) -> Any:
        self._stream.feed_segment(data)
        if not self._in_handshake():
            decrypted = await self._wa_noiseprotocol.receive()
            await self.toUpper(decrypted)

