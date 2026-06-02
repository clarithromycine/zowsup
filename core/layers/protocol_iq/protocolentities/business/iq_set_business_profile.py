from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class SetBusinessProfileIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None,address = "default.chinago2", description = "",categoriesIds=['629412378414563']) -> None:
        super().__init__("w:biz" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.address = address
        self.description = description
        self.categoriesIds = categoriesIds

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()                                        
        profile = ProtocolTreeNode("business_profile",{"v":"1908"})
        #profile.addChild(ProtocolTreeNode("verified_name",{"v":"2"},None,"Terry Watkins2".encode("utf-8")))
        profile.addChild(ProtocolTreeNode("address",{},None,self.address.encode("utf-8")))
        profile.addChild(ProtocolTreeNode("description",{},None,self.description.encode("utf-8")))
        
        cats = ProtocolTreeNode("categories",{})        

        for catid in self.categoriesIds:
            cats.addChild(ProtocolTreeNode("category",{"id":catid}))            
                
        profile.addChild(cats)

        business_hours = ProtocolTreeNode("business_hours",{"timezone":"America/New_York"})
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"sun","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"mon","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"tue","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"wed","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"thu","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"fri","mode":"open_24h"}))
        business_hours.addChild(ProtocolTreeNode("business_hours_config",{"day_of_week":"sat","mode":"open_24h"}))

        profile.addChild(business_hours)
        node.addChild(profile)  
               
        return node
