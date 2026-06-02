# zowsup

zowsup is a python whatsapp-protocol project based on [yowsup](https://github.com/tgalal/yowsup/).

Since the original yowsup project has not been maintained for a long time, we forked yowsup and some associated projects(axolotl, consonance) and integrated into an All-In-One Project and keep updating with the latest version of WhatsApp.

```
- ZOWSUP VERSION : 0.9.0

- UPDATE TIME : 2026-06-02

- WHATSAPP VERSION : 
    2.26.17.72(Android) 
    2.26.17.72(SMB Android) 
    2.26.13.74(iOS) 
    2.26.13.74(SMB iOS) 

```

## Discussion Groups
 * telegram:  [zowsup](https://t.me/+au1dTQz7jyU0YjU5)

## What's New 0.7.0
 * **Asyncio command architecture** — all commands are now fully async (`async def execute()`), powered by `asyncio` event loop
 * **`AsyncCommandExec`** replaces the old threading-based command executor; login wait is non-blocking
 * **`BotCommand` base class** — unified base for every command module with built-in IQ helpers (`send_iq`, `send_iq_expect`), parameter helpers, and structured `success` / `fail` response builders
 * New commands: `account.getname`, `account.info`, `contact.getdevices`, `contact.getprofile`, `contact.list`, `contact.setmsgdisappearing`, `md.devices`, `md.inputcode`, `msg.quotedreply`, `msg.sendad`, `msg.sendinteractive`, `msgshortlink.*`, `newsletter.*`, `misc.*`

## What's New 0.6.5
 * New interactive mode

## What's New 0.6.0
 * New commands `md.link` and `md.remove`
 * Linkcode for companion device registration

## What's New 0.5.0
 * Latest version (6.3) of noise-protocol and token-dictionary
 * Multi-Environment support (android, smb_android, ios, smb_ios)
 * Multi-Device protocol support
 * Display a QR to login as a companion device
 * 6-parts account support (import / export)
 * Proxy support
 * Bubbling up all config variables to the top layer (app and conf folder)
 * Mass of WA-protocol updates

## Subsequent update promise
 * Critical protocol update
 * Version update with latest WhatsApp


## Command Architecture Overview

```
script/main.py
    └── ZowBot                     # Core bot instance (asyncio event loop)
          ├── ZowBotLayer          # Protocol layer — handles IQ send/receive
          ├── AsyncCommandExec     # Async command executor (non-blocking login wait)
          └── zowbot_cmd/          # Command modules (one file per command)
                ├── BotCommand     # Base class: execute(), send_iq(), success(), fail()
                ├── account/       # Account management commands
                ├── contact/       # Contact commands
                ├── group/         # Group management commands
                ├── md/            # Multi-device (companion) commands
                ├── msg/           # Messaging commands
                ├── msgshortlink/  # Message short-link commands
                ├── newsletter/    # Newsletter / channel commands
                └── misc/          # Miscellaneous / utility commands
```

Each command is an independent class that inherits `BotCommand` and implements a single `async def execute(params, options)` method. The `AsyncCommandExec` engine waits for the bot to finish login (via `asyncio.sleep` polling on `loginEvent`) before dispatching the command, then disconnects cleanly on completion.


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


