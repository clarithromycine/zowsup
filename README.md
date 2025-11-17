# zowsup

zowsup is a python whatsapp-protocol project based on [yowsup](https://github.com/tgalal/yowsup/).

Since the original yowsup project has not been maintained for a long time, we forked yowsup and some associated projects(axolotl, consonance) and intergrated into an All-In-One Project and keep updating with latest version of WhatsApp.

```
- ZOWSUP VERSION : 0.6.5

- UPDATE TIME : 2025-11-16

- WHATSAPP VERSION : 
    2.25.29.75(Android) 
    2.25.32.75(SMB Android) 
    2.25.32.77(iOS) 
    2.25.32.77(SMB iOS) 

```

## Discussion Groups
 * telegram:  [zowsup](https://t.me/+au1dTQz7jyU0YjU5)

## What's New 0.6.5
 * new interactive mode

## What's New 0.6.0
 * new commands mdlink and mdremove
 * linkcode for companion device registration

## What's New 0.5.0
 * Latest version(6.3) of noise-protocol and token-dictionary
 * Multi-Environment support (android,smb_android,ios,smb_ios)
 * Multi-Device protocol support
 * Display a QR to Login as a companion device 
 * 6-parts account support (import / export )
 * Proxy support
 * Threading command architecture 
 * Bubbling up all the config variables to the top layer ( app and conf folder)
 * Mass of WA-protocol updates
 
## Subsequent update promise
 * Critical protocol update
 * Version update with latest WhatsApp 
 

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
 python script/import6.py [6-parts-account-data] --env android             # env : android/smb_android/ios/smb_ios is available

```

 * Export accounts to 6-parts-account-data
 
```
 python script/export6.py [account-number]

```

 * Run

```
 python script/main.py [account-number] --env android                        # env : android/smb_android/ios/smb_ios is available

```

then you can enter interactive mode with 'CMD > ' prompt


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


[command]                     |   [description]
----------------------------------------------------------------------------
account.getavatar             | get account avatar
account.getemail              | get account email
account.init                  | initialize the account (for the 1st login)
account.set2fa                | set account 2fa
account.setavatar             | set account avatar
account.setemail              | set account email
account.setname               | set account name
account.verifyemail           | request email verification
account.verifyemailcode       | verify email code
contact.getavatar             | get account avatar
contact.sync                  | sync contacts
contact.trust                 | trust contact
group.add                     | add member(s) to group
group.approve                 | approve participants to join the group
group.create                  | create a group
group.demote                  | demote group member(s) from admin
group.getinvite               | get the invite code of group
group.info                    | show group information
group.join                    | join group with an invite code
group.leave                   | leave group
group.list                    | list all groups
group.promote                 | promote group member(s) to admin
group.remove                  | remove a member from group
group.seticon                 | set icon for group
md.link                       | link to companion device with qrcode-str
md.remove                     | remove companion device(s)
msg.edit                      | edit message
msg.revoke                    | revoke message
msg.send                      | send message
msg.sendmedia                 | send media message
----------------------------------------------------------------------------
```


 * Proxy 

```
 python script/main.py [account-number] --proxy "host:port:username:password"  

 dynamic [location] and [session_id] replacement in the proxy string is supported 

```


