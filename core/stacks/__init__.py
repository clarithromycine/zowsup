from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from .yowstack import YowStack, YowStackBuilder

from ..layers.auth                        import YowAuthenticationProtocolLayer
from ..layers.coder                       import YowCoderLayer
from ..layers.logger                      import YowLoggerLayer
from ..layers.network                     import YowNetworkLayer
from ..layers.protocol_messages           import YowMessagesProtocolLayer
from ..layers.protocol_media              import YowMediaProtocolLayer
from ..layers.protocol_acks               import YowAckProtocolLayer
from ..layers.protocol_receipts           import YowReceiptProtocolLayer
from ..layers.protocol_groups             import YowGroupsProtocolLayer
from ..layers.protocol_presence           import YowPresenceProtocolLayer
from ..layers.protocol_ib                 import YowIbProtocolLayer
from ..layers.protocol_notifications      import YowNotificationsProtocolLayer
from ..layers.protocol_iq                 import YowIqProtocolLayer
from ..layers.protocol_contacts           import YowContactsIqProtocolLayer
from ..layers.protocol_chatstate          import YowChatstateProtocolLayer
from ..layers.protocol_privacy            import YowPrivacyProtocolLayer
from ..layers.protocol_profiles           import YowProfilesProtocolLayer
from ..layers.protocol_calls              import YowCallsProtocolLayer
from ..layers.noise.layer                 import YowNoiseLayer
from ..layers.noise.layer_noise_segments  import YowNoiseSegmentsLayer



YOWSUP_CORE_LAYERS = (
    YowLoggerLayer,
    YowCoderLayer,
    YowNoiseLayer,
    YowNoiseSegmentsLayer,
    YowNetworkLayer
)


YOWSUP_PROTOCOL_LAYERS_BASIC = (
    YowAuthenticationProtocolLayer, YowMessagesProtocolLayer,
    YowReceiptProtocolLayer, YowAckProtocolLayer, YowPresenceProtocolLayer,
    YowIbProtocolLayer, YowIqProtocolLayer, YowNotificationsProtocolLayer,
    YowContactsIqProtocolLayer, YowChatstateProtocolLayer

)

YOWSUP_PROTOCOL_LAYERS_GROUPS = (YowGroupsProtocolLayer,) + YOWSUP_PROTOCOL_LAYERS_BASIC
YOWSUP_PROTOCOL_LAYERS_MEDIA  = (YowMediaProtocolLayer,) + YOWSUP_PROTOCOL_LAYERS_BASIC
YOWSUP_PROTOCOL_LAYERS_PROFILES  = (YowProfilesProtocolLayer,) + YOWSUP_PROTOCOL_LAYERS_BASIC
YOWSUP_PROTOCOL_LAYERS_CALLS  = (YowCallsProtocolLayer,) + YOWSUP_PROTOCOL_LAYERS_BASIC
YOWSUP_PROTOCOL_LAYERS_FULL = (YowGroupsProtocolLayer, YowMediaProtocolLayer, YowPrivacyProtocolLayer, YowProfilesProtocolLayer, YowCallsProtocolLayer)\
                              + YOWSUP_PROTOCOL_LAYERS_BASIC


YOWSUP_FULL_STACK = (YOWSUP_PROTOCOL_LAYERS_FULL,) +\
                     YOWSUP_CORE_LAYERS
