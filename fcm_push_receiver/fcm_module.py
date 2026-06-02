from .push_receiver.android_fcm_register import AndroidFCM
from .push_receiver.push_receiver import PushReceiver

import threading,json,os
import asyncio
import inspect
import logging

from conf.constants import SysVar

logger = logging.getLogger(__name__)


class FcmModule:
    ANDROID_DEFAULT = {
        "api_key":"AIzaSyCGOJbGQ95SWrXxl8wk-_cRQZcJl42bvDU",
        "project_id":"whatsapp-messenger",
        "gcm_sender_id":"293955441834",
        "gms_app_id":"1:293955441834:android:7373a2d0bdfa3228",
        "android_package_name":"com.whatsapp",
        "android_package_cert":"38A0F7D505FE18FEC64FBF343ECAAAF310DBD799"        
    }
    SMB_ANDROID_DEFAULT = {
        "api_key":"AIzaSyCGOJbGQ95SWrXxl8wk-_cRQZcJl42bvDU",
        "project_id":"whatsapp-messenger",
        "gcm_sender_id":"293955441834",
        "gms_app_id":"1:293955441834:android:5705ec20eb95eab3",
        "android_package_name":"com.whatsapp.w4b",
        "android_package_cert":"38A0F7D505FE18FEC64FBF343ECAAAF310DBD799"          
    }

    def __init__(self,fcmConfig,isReg=False,profile=None):
        self.fcm = AndroidFCM()

        if isReg or profile is None or profile.config.fcm_creds is None:

            newDevice=True
            if profile is None and os.path.exists(SysVar.ACCOUNT_PATH+"device/fcm_device.json"):
                
                #说明是注册，不是实际用号
                file = open(SysVar.ACCOUNT_PATH+"device/fcm_device.json" ,'r')   
                if file is not None:
                    self.creds = json.loads(file.read())
                    file.close()
                    newDevice=False
                    
            if newDevice or isReg:                
                self.creds = self.fcm.register(
                    api_key = fcmConfig["api_key"],
                    project_id = fcmConfig["project_id"],
                    gcm_sender_id = fcmConfig["gcm_sender_id"],
                    gms_app_id = fcmConfig["gms_app_id"],
                    android_package_name = fcmConfig["android_package_name"],
                    android_package_cert = fcmConfig["android_package_cert"]
                )
                file = open(SysVar.ACCOUNT_PATH+"device/fcm_device.json" ,'w') 
                file.write(json.dumps(self.creds))
                file.close()                

            if self.creds is not None and profile is not None:
                profile.config.fcm_creds = self.creds
                profile.write_config()
        else:
            self.creds = profile.config.fcm_creds

    def getFcmToken(self):
        #这个相当于c2dm_reg_id
        if self.creds is not None:
            return self.creds["fcm"]["token"]    
        return None
    
    def messageThread(self, callback, loop=None):
        pr = PushReceiver(self.creds)
        pr.listen(callback=self._build_listener_callback(callback, loop=loop))

    def _build_listener_callback(self, callback, loop=None):
        """Wrap callback and support both sync and async styles."""
        def listener_callback(obj, data, p):
            try:
                result = callback(obj, data, p)
                if inspect.isawaitable(result):
                    if loop is not None and loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(result, loop)

                        def _log_future_error(f):
                            try:
                                f.result()
                            except Exception as e:
                                logger.error(f"fcm async callback error: {e}", exc_info=True)

                        future.add_done_callback(_log_future_error)
                    else:
                        # Registration flow may not provide an external event loop.
                        asyncio.run(result)
            except Exception as e:
                logger.error(f"fcm callback dispatch error: {e}", exc_info=True)

        return listener_callback

    def startMessageListener(self, callback, loop=None):
        self.thread = threading.Thread(target=self.messageThread, args=(callback, loop))
        self.thread.daemon = True  #主线程结束，这个就同时结束
        self.thread.start() 





