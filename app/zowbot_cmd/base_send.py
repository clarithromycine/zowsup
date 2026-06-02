


from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging


from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_contacts.protocolentities import ContactGetSyncIqProtocolEntity,ContactResultSyncIqProtocolEntity

logger = logging.getLogger(__name__)
    
class BotSendCommand(BotCommand):

    async def assureContactsAndSend(self,params,options,send_func,redo_func):

        to,*other = params
        isCompanion = "_" in self.bot.botId
        jid = Jid.normalize(to)
        if jid.endswith("@g.us"):
            # Group JIDs need no contact-sync — send directly
            await send_func(params, options)
        elif not jid.endswith("@lid"):
            foundContact = self.bot.botLayer.db._store.findContact(jid)        
            if not foundContact and not isCompanion:      
                try:          
                    entity = ContactGetSyncIqProtocolEntity([to],mode = "delta")    
                    entity_result = await self.send_iq_expect(entity,ContactResultSyncIqProtocolEntity)
                    logger.info("add target to contacts")      

                    jid = []
                    for key,value in entity_result.result.items():
                        if value["type"]=="in":                        
                            self.bot.botLayer.db._store.updateContact(value["jid"],value["lid"],key)      
                            jid.append(value["jid"])
                        else:
                            logger.info("%s not found",key)
                except Exception as e:
                    logger.error(f"Error syncing contacts: {e}")
                    return

                if len(jid)>0:
                    params[0]=','.join(jid)
                    await redo_func(params,options)      
                else:
                    logger.error("target not found in contacts")

            else:
                logger.info("target in contacts")                       
                await send_func(params,options)                         
        else:
            logger.info("lid-target, direct send")  
            await send_func(params,options)          
    

     
