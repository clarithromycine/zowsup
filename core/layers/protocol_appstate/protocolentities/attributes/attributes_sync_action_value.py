import time
from typing import Optional, Any, List, Dict, Union

from proto import protocol_pb2
from .....layers.protocol_appstate.protocolentities.attributes import *

import json

class SyncActionValueAttribute:
    def __init__(self,                  
                 timestamp=None,
                 contactAction=None,
                 localeSetting=None,
                 pushNameSetting=None,
                 timeFormatAction=None,
                 primaryVersionAction=None,
                 nuxAction=None
        ) -> None:
        if timestamp is None:
            self.timestamp = int(time.time()) *1000       
        else:
            self.timestamp = timestamp
        
        self.contactAction= contactAction
        self.localeSetting = localeSetting
        self.pushNameSetting =pushNameSetting
        self.timeFormatAction = timeFormatAction
        self.primaryVersionAction=primaryVersionAction
        self.nuxAction = nuxAction

        self.args = None


    def action(self) -> Any:
        if self.contactAction is not None:
            return self.contactAction
    
        if self.timeFormatAction is not None:
            return self.timeFormatAction
        
        if self.primaryVersionAction is not None:
            return self.primaryVersionAction
        
        if self.nuxAction is not None:
            return self.nuxAction
        
        return None

    def setting(self) -> Any:
        if self.localeSetting is not None:
            return self.localeSetting
        if self.pushNameSetting is not None:
            return self.pushNameSetting
        return None    
    
    def getIndexName(self) -> Any:
        r = []
        action = self.action()
        if action is not None:
            r.append(action.indexName())
            if self.args is not None:
                r.extend(self.args)
        
        setting = self.setting()
        if setting is not None:
            r.append(setting.indexName())
        
        if len(r)>0:
            return json.dumps(r)
        
        #来到这里说明action未被识别        
        return None
    
    def getVersion(self) -> Any:
        action = self.action()
        if action is not None:
            return action.actionVersion()        
        
        setting = self.setting()
        if setting is not None:
            return setting.actionVersion()              
        
        return None
    
    def setArgs(self,args) -> Any:
        self.args = args
        return self

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue()
        if self.timestamp is not None:
            pb_obj.timestamp = self.timestamp
        if self.contactAction is not None:
            pb_obj.contactAction.MergeFrom(self.contactAction.encode())
        if self.localeSetting is not None:
            pb_obj.localeSetting.MergeFrom(self.localeSetting.encode())
        if self.pushNameSetting is not None:
            pb_obj.pushNameSetting.MergeFrom(self.pushNameSetting.encode())
        if self.timeFormatAction is not None:
            pb_obj.timeFormatAction.MergeFrom(self.timeFormatAction.encode())
        if self.primaryVersionAction is not None:
            pb_obj.primaryVersionAction.MergeFrom(self.primaryVersionAction.encode())
        if self.nuxAction is not None:
            pb_obj.nuxAction.MergeFrom(self.nuxAction.encode())


        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):        
        timestamp = pb_obj.timestamp if pb_obj.HasField("timestamp") else None
        contactAction = SyncActionContactActionAttribute.decodeFrom(pb_obj.contactAction) if pb_obj.HasField("contactAction") else None
        localeSetting = SyncActionLocaleSettingAttribute.decodeFrom(pb_obj.localeSetting) if pb_obj.HasField("localeSetting") else None
        pushNameSetting = SyncActionPushnameSettingAttribute.decodeFrom(pb_obj.pushNameSetting) if pb_obj.HasField("pushNameSetting") else None
        timeFormatAction = SyncActionTimeFormatActionAttribute.decodeFrom(pb_obj.timeFormatAction) if pb_obj.HasField("timeFormatAction") else None
        primaryVersionAction = SyncActionPrimaryVersionActionAttribute.decodeFrom(pb_obj.primaryVersionAction) if pb_obj.HasField("primaryVersionAction") else None
        nuxAction = SyncActionNuxActionAttribute.decodeFrom(pb_obj.nuxAction) if pb_obj.HasField("nuxAction") else None


        return SyncActionValueAttribute(
            timestamp=timestamp,
            contactAction=contactAction,
            localeSetting=localeSetting,
            pushNameSetting=pushNameSetting,
            timeFormatAction=timeFormatAction,
            primaryVersionAction=primaryVersionAction,
            nuxAction=nuxAction
        )