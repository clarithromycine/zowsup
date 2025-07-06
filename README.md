# zowsup

zowsup 是一个基于 [yowsup](https://github.com/tgalal/yowsup/) 的 Python WhatsApp 协议项目。

由于原始的 yowsup 项目长期未维护，我们 fork 了 yowsup 及其相关项目（axolotl、consonance），并将其整合为一个一体化项目，持续更新以支持最新版本的 WhatsApp。

```
- ZOWSUP 版本 : 0.6.1

- 更新时间 : 2025-07-06

- WHATSAPP 版本 :
    2.25.18.80(Android)
    2.25.18.82(SMB Android)
    2.25.5.74(iOS)
    2.25.5.74(SMB iOS)

```


## 讨论群组
 * Telegram:  [zowsup](https://t.me/+au1dTQz7jyU0YjU5)


## 0.6.0 版本新功能
 * 新增 mdlink 和 mdremove 命令
 * 支持配套设备注册的链接码功能

## 0.5.0 版本新功能
 * 最新版本(6.3)的 noise-protocol 和 token-dictionary
 * 多环境支持 (android、smb_android、ios、smb_ios)
 * 多设备协议支持
 * 显示二维码以作为配套设备登录
 * 6部分账户支持（导入/导出）
 * 代理支持
 * 线程化命令架构
 * 将所有配置变量提升到顶层（app 和 conf 文件夹）
 * 大量 WA 协议更新

## 后续更新承诺
 * 关键协议更新
 * 与最新 WhatsApp 版本同步更新


## 项目快速开始

 * 安装依赖

```
 pip install -r requirements.txt

```
 * 基础配置

```
复制 ./conf/config.conf.example 到 ./conf/config.conf 并根据您的系统修改 config.conf 中的变量

ACCOUNT_PATH=/data/account/               #存储账户数据的位置
DOWNLOAD_PATH=/data/tmp/                  #下载路径
UPLOAD_PATH=/data/tmp/                    #上传路径
LOG_PATH=/data/log/                       #日志路径
DEFAULT_ENV=android                       #默认环境

```

 * 从6部分账户数据导入账户

```
 python script/import6.py [6部分账户数据] --env android             # env : android/smb_android/ios/smb_ios 可用

```

 * 导出账户为6部分账户数据

```
 python script/export6.py [账户号码]

```

 * 运行

```
 python script/main.py [账户号码] --env android                        # env : android/smb_android/ios/smb_ios 可用

```

* 注册为配套设备

```
 [二维码方式]
 python script/regwithscan.py

 [链接码方式]
 python script/regwithlinkcode.py [账户号码]

```

* 基本命令

```
main.py [账户号码] [命令] [命令参数]

[命令]                        |   [描述]
----------------------------------------------------------------------------
account.getavatar             | 获取账户头像
account.getemail              | 获取账户邮箱
account.init                  | 初始化账户（首次登录）
account.set2fa                | 设置账户双重验证
account.setavatar             | 设置账户头像
account.setemail              | 设置账户邮箱
account.setname               | 设置账户名称
account.verifyemail           | 请求邮箱验证
account.verifyemailcode       | 验证邮箱验证码
contact.getavatar             | 获取联系人头像
contact.sync                  | 同步联系人
contact.trust                 | 信任联系人
group.add                     | 添加成员到群组
group.approve                 | 批准参与者加入群组
group.create                  | 创建群组
group.demote                  | 将群组成员从管理员降级
group.getinvite               | 获取群组邀请码
group.info                    | 显示群组信息
group.join                    | 使用邀请码加入群组
group.leave                   | 离开群组
group.promote                 | 将群组成员提升为管理员
group.remove                  | 从群组移除成员
group.seticon                 | 设置群组图标
md.link                       | 使用二维码字符串链接到配套设备
md.remove                     | 移除配套设备
msg.edit                      | 编辑消息
msg.revoke                    | 撤回消息
msg.send                      | 发送消息
msg.sendmedia                 | 发送媒体消息
----------------------------------------------------------------------------
```


 * 代理设置

```
 python script/main.py [账户号码] --proxy "主机:端口:用户名:密码"

 支持在代理字符串中动态替换 [location] 和 [session_id]

```


## 技术更新说明

### 🔧 加密库迁移 (2025-07-06)
本项目已成功从 `python-axolotl-curve25519` 迁移到现代的 `cryptography` 库：

* ✅ **性能提升**: 使用行业标准的 cryptography 库，性能更优
* ✅ **安全增强**: 获得定期安全更新和最新加密标准支持
* ✅ **兼容性**: 完全向后兼容，无需修改现有代码
* ✅ **稳定性**: 解决了在新版 macOS 上的编译问题

### 🛠️ 开发者说明
如果您是开发者，所有 Curve25519 相关的加密操作现在都通过 `axolotl/ecc/crypto_adapter.py` 适配层处理，确保了：
- X25519 密钥协商的完整支持
- Ed25519 数字签名的完整支持
- 与原有 API 的 100% 兼容性



