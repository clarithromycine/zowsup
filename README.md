# zowsup

zowsup is a python whatsapp-protocol project based on [yowsup](https://github.com/tgalal/yowsup/).

Since the original yowsup project has not been maintained for a long time, we forked yowsup and some associated projects(axolotl, consonance) and integrated into an All-In-One Project and keep updating with the latest version of WhatsApp.

```
- ZOWSUP VERSION : 0.9.5

- UPDATE TIME : 2026-06-15

- WHATSAPP VERSION : 
    2.26.21.75(Android) 
    2.26.21.75(SMB Android) 
    2.26.13.74(iOS) 
    2.26.13.74(SMB iOS) 

```

## Discussion Groups
 * telegram:  [zowsup](https://t.me/+au1dTQz7jyU0YjU5)

## What's New 0.9.5
 * **Agent cluster** — multi-agent deployment with transparent Router proxy; auto-registration, heartbeat, centralized escalation & plugin config
 * **Plugin system** — pluggable translation (Google / LLM / Anthropic) and AI auto-reply (OpenAI / Anthropic / GLM / DeepSeek / Qwen) with keyword escalation
 * **Web Console** — single-page management UI with 4 tabs: Escalations, Conversations (with real-time WebSocket + message status ticks), Plugins, Bots
 * **Conversation CRUD** — SQLite-backed E2E conversation & message persistence with LID/PN resolution and contact notify_name
 * **Escalation queue** — claim / reply / resolve workflow for human takeover of AI-escalated conversations
 * **Bot last-active tracking** — runtime cache with periodic flush to account store
 * **Automated bot migration** — stop → tar+base64 export → import → start → cleanup across agents

## What's New 0.9.0
IMPORTANT NOTICE:  0.9.0 architecture is not compatible with 0.6.5, so if you have already work in 0.6.5, don't update,  you can track on old code from the branch "legacy"
 * **Asyncio command architecture** — all commands are now fully async (`async def execute()`), powered by `asyncio` event loop
 * **`AsyncCommandExec`** replaces the old threading-based command executor; login wait is non-blocking
 * **`BotCommand` base class** — unified base for every command module with built-in IQ helpers (`send_iq`, `send_iq_expect`), parameter helpers, and structured `success` / `fail` response builders
 * **`ZowBotLayer` decomposition** — protocol layer split into 8 focused managers (`ConnectionManager`, `IqManager`, `PairingManager`, `MessageHandler`, `NotificationHandler`, `MediaManager`, `ContactManager`, `SyncManager`)
 * **`DeviceEnv` simplification** — eliminated 25+ manual pass-through methods via `__getattr__` auto-delegation
 * **Thread model cleanup** — all `threading.Event` replaced with `asyncio.Event` in async command modules
 * New commands: `account.getname`, `account.info`, `contact.getdevices`, `contact.getprofile`, `contact.list`, `contact.setmsgdisappearing`, `md.devices`, `md.inputcode`, `msg.quotedreply`, `msg.sendad`, `msg.sendinteractive`, `msgshortlink.*`, `newsletter.*`, `misc.*`

## What's New 0.6.5
 * New interactive mode

## Subsequent update promise
 * Critical protocol update
 * Version update with latest WhatsApp


## Agent — Multi-Bot Management Service

A FastAPI-based HTTP + WebSocket service for remote multi-bot WhatsApp management:

- Start / stop bots in batch
- Execute bot commands remotely (`msg.send`, `group.create`, etc.)
- Real-time log streaming and structured event push (WebSocket)
- Account import / export (6-segment CSV format)
- Optional access key authentication

### Standalone Mode

Single agent manages all bots directly. Good for single-machine deployments.

```
┌──────────┐
│  Client  │──→ HTTP/WS ──→ ┌─────────┐
│ (Web UI) │                │  Agent  │──→ WhatsApp
└──────────┘                │ (bots)  │
                            └─────────┘
```

```bash
python -m agent                    # No auth, listens on 0.0.0.0:8000
python -m agent --accesskey mykey  # Auth required
python -m agent --port 9090        # Custom port

# Open http://localhost:8000/ for Web Console
```

### Cluster Mode

Multiple agents behind a transparent Router. The Router exposes the same API as a single agent — clients don't need to know about the cluster.

```
                         ┌──────────────┐
                         │   Browser    │
                         │ (Web Console)│
                         └──────┬───────┘
                                │ HTTP/WS
                         ┌──────▼───────┐
                         │    Router    │  ← transparent proxy, port 8000
                         └──┬───┬───┬───┘
                            │   │   │
                   ┌────────┘   │   └────────┐
                   ▼            ▼            ▼
              ┌────────┐  ┌────────┐  ┌────────┐
              │Agent A │  │Agent B │  │Agent C │
              │ :8001  │  │ :8002  │  │ :8003  │
              │ bot1   │  │ bot3   │  │ bot5   │
              │ bot2   │  │ bot4   │  │ bot6   │
              └────────┘  └────────┘  └────────┘
```

**Each agent must have its own `ACCOUNT_PATH`.** A bot belongs to whichever agent's `ACCOUNT_PATH` contains its directory. Migration = tar + scp the directory.

**Start Router:**
```bash
python -m agent.cluster --host 0.0.0.0 --port 8000
```

**Start Agents (connect to Router):**
```bash
# Agent A
AGENT_ID=node-1 ROUTER_URL=http://localhost:8000 python -m agent --port 8001

# Agent B (different ACCOUNT_PATH)
ACCOUNT_PATH=/data/accounts-b/ AGENT_ID=node-2 ROUTER_URL=http://localhost:8000 python -m agent --port 8002
```

**Router manages the cluster:**
- `GET /api/cluster/agents` — list all agents, bot counts, status
- `POST /api/cluster/agents` — register new agent (automatic via `ROUTER_URL`)
- `POST /api/cluster/migrate` — automated bot migration between agents
- Plugin config sync: Router is the source of truth, pushes to agents on change
- Escalation queue: centralized on Router, all agents forward to it
- Health check: 15s ping, 3 consecutive failures → mark offline

**Features available in both modes:**
| Feature | Standalone | Cluster |
|---------|-----------|---------|
| Web Console (4 tabs) | ✅ | ✅ (via Router) |
| Translation plugin | ✅ | ✅ (config synced from Router) |
| AI auto-reply + escalation | ✅ | ✅ (escalation centralized) |
| Conversation CRUD | ✅ | ✅ (per-agent, proxied) |
| Message status ticks | ✅ | ✅ |
| WebSocket real-time events | ✅ | ✅ (relayed by Router) |

Full API reference: [`docs/agent-api.md`](docs/agent-api.md)
Plugin system docs: [`docs/plugin-system.md`](docs/plugin-system.md)
Cluster design: [`docs/agent-cluster-design.md`](docs/agent-cluster-design.md)


## Command Architecture Overview

```
script/main.py
    └── ZowBot                         # Core bot instance (asyncio event loop)
          ├── ZowBotLayer (facade)      # Thin protocol facade — delegates to managers
          │     ├── ConnectionManager   # Connection lifecycle (login/logout/reconnect)
          │     ├── IqManager           # IQ request/response + heartbeat
          │     ├── PairingManager      # QR / LinkCode companion registration
          │     ├── MessageHandler      # Incoming message parsing + ack delivery
          │     ├── NotificationHandler # Server push notification dispatch
          │     ├── MediaManager        # Media download & decryption
          │     ├── ContactManager      # Contact sync & pre-send assurance
          │     └── SyncManager         # App-state sync / FCM / device logout
          ├── AsyncCommandExec          # Async command executor (non-blocking login wait)
          └── zowbot_cmd/              # Command modules (one file per command)
                ├── BotCommand          # Base class: execute(), send_iq(), success(), fail()
                ├── account/            # Account management commands
                ├── contact/            # Contact commands
                ├── group/              # Group management commands
                ├── md/                 # Multi-device (companion) commands
                ├── msg/                # Messaging commands
                ├── msgshortlink/       # Message short-link commands
                ├── newsletter/         # Newsletter / channel commands
                └── misc/               # Miscellaneous / utility commands
```

Each command is an independent class that inherits `BotCommand` and implements a single `async def execute(params, options)` method. The `AsyncCommandExec` engine waits for the bot to finish login (via `asyncio.sleep` polling on `loginEventComplete`) before dispatching the command, then disconnects cleanly on completion.


## Project Architecture

```
zowsup/
├── app/                          # Application layer
│   ├── zowbot.py                 # Core ZowBot (asyncio event loop, command queue)
│   ├── zowbot_layer.py           # Thin protocol facade (delegates to managers)
│   ├── async_command_exec.py     # Async command executor
│   ├── zowbot_values.py          # Bot type & status enums
│   ├── bot_env.py / device_env.py / network_env.py  # Environment wrappers
│   ├── layer/                    # Protocol layer managers (extracted from ZowBotLayer)
│   │   ├── connection.py         # ConnectionManager
│   │   ├── iq_manager.py         # IqManager
│   │   ├── pairing.py            # PairingManager
│   │   ├── message_handler.py    # MessageHandler
│   │   ├── notification_handler.py  # NotificationHandler
│   │   ├── media.py              # MediaManager
│   │   ├── contacts.py           # ContactManager
│   │   └── sync.py               # SyncManager
│   ├── device_env_config/        # Device environment profiles
│   │   ├── env_tools.py          # DeviceEnvBase + EnvTools utilities
│   │   ├── env_android.py        # Android device profile
│   │   ├── env_ios.py            # iOS device profile
│   │   ├── env_smb_android.py    # SMB Android device profile
│   │   └── env_smb_ios.py        # SMB iOS device profile
│   └── zowbot_cmd/               # Bot command modules
├── core/                         # Protocol stack (from yowsup)
│   ├── layers/                   # ~20 protocol layers
│   ├── stacks/                   # YowStack / YowStackBuilder
│   ├── profile/                  # YowProfile (account config + axolotl)
│   └── axolotl/ / common/ / config/ / registration/
├── axolotl/                      # Signal protocol (E2E encryption)
├── consonance/                   # Noise protocol (transport security)
├── zargo/                        # WhatsApp Argo wire-type decoder
├── zwam/                         # WAM (WhatsApp Application Metrics)
├── proto/                        # Protobuf definitions
├── conf/                         # Configuration (config.conf, constants)
├── common/                       # Shared utilities
├── script/                       # Entry points (main, registration, import/export)
└── data/                         # Static data (MCC/MNC, supported devices)
```


## Quick start for the project

 * Installation 

```
pip install -r requirements.txt
```

 * Basic configuration

```
copy ./conf/config.conf.example to ./conf/config.conf and modify variables in config.conf according to your system

ACCOUNT_PATH=/data/account/               #location you store the account data
DOWNLOAD_PATH=/data/tmp/                  #download path
UPLOAD_PATH=/data/tmp/                    #upload path
LOG_PATH=/data/log/                       #log path
DEFAULT_ENV=android                       #default environment
```

 * Import account from 6-parts-account-data

```
python script/import6.py [6-parts-account-data] --env android     # env : android/smb_android/ios/smb_ios
```

 * Export accounts to 6-parts-account-data

```
python script/export6.py [account-number]
```

 * Run

```
python script/main.py [account-number] --env android               # env : android/smb_android/ios/smb_ios
```

With only `[account-number]` (no command), the bot enters **interactive mode** with a `CMD > ` prompt.

* Register as a companion device

```
[QRCODE]
python script/regwithscan.py 

[LINKCODE]
python script/regwithlinkcode.py [account-number]
```

* Basic commands

```
python script/main.py [account-number] [command] [commandParams] #in shell console

or

[command] [commandParams]   #in the interactive mode 


[command]                        |   [description]
-------------------------------------------------------------------------------
account.getavatar                | get account avatar
account.getemail                 | get account email
account.getname                  | get account display name
account.info                     | show account information
account.init                     | initialize the account (for the 1st login)
account.set2fa                   | set account 2FA passcode
account.setavatar                | set account avatar
account.setemail                 | set account email
account.setname                  | set account display name
account.verifyemail              | request email verification
account.verifyemailcode          | verify email code
contact.getavatar                | get contact avatar
contact.getdevices               | list registered devices for a contact
contact.getprofile               | get contact profile info
contact.list                     | list all contacts
contact.setmsgdisappearing       | set disappearing messages for a contact
contact.sync                     | sync contacts
contact.trust                    | trust contact
group.add                        | add member(s) to group
group.approve                    | approve participants to join the group
group.create                     | create a group
group.demote                     | demote group member(s) from admin
group.getinvite                  | get the invite code of group
group.info                       | show group information
group.join                       | join group with an invite code
group.leave                      | leave group
group.list                       | list all groups
group.promote                    | promote group member(s) to admin
group.remove                     | remove a member from group
group.seticon                    | set icon for group
md.devices                       | list linked companion devices
md.inputcode                     | input pairing code for companion device
md.link                          | link to companion device with qrcode-str
md.remove                        | remove companion device(s)
msg.edit                         | edit a sent message
msg.quotedreply                  | send a quoted reply to a message
msg.revoke                       | revoke (delete) a message
msg.send                         | send a text message
msg.sendad                       | send an ad message
msg.sendinteractive              | send an interactive message
msg.sendmedia                    | send a media message
msgshortlink.decode              | decode a message short-link
msgshortlink.get                 | get the short-link for a message
msgshortlink.reset               | reset message short-link
msgshortlink.setmsg              | set the message for a short-link
newsletter.directorylist         | list newsletter directory
newsletter.directorysearch       | search newsletter directory
newsletter.join                  | join a newsletter / channel
newsletter.leave                 | leave a newsletter / channel
newsletter.metadata              | get newsletter metadata
newsletter.recommended           | get recommended newsletters
misc.bizfeatures                 | get business features
misc.bizintegrity                | check business integrity
misc.checkactive                 | check if account is active
misc.prekeycount                 | get pre-key count
misc.reachouttimelock            | check reach-out time lock
misc.regfcm                      | register FCM push token
-------------------------------------------------------------------------------
```


 * Proxy

```
python script/main.py [account-number] --proxy "host:port:username:password"

dynamic [location] and [session_id] replacement in the proxy string is supported
```


