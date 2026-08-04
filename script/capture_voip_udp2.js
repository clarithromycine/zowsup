/**
 * Frida script — capture ALL WhatsApp VoIP UDP traffic (SEND + RECV)
 * Run: frida -U -l capture_voip_udp2.js "WhatsApp Business"
 */

const CAPTURE_ALL_UDP = false;
const RELAY_IPS = {};
function markRelayIP(ip) { if (ip && ip !== "?" && ip !== "0.0.0.0") RELAY_IPS[ip] = true; }
function isRelayIP(ip) { return !!RELAY_IPS[ip]; }
function isInteresting(ip, port, raw) {
    if (port === 3478 || port === 3480) return true;
    if (isRelayIP(ip)) return true;
    if (raw.length >= 20) {
        var mag = (raw[4]<<24)|(raw[5]<<16)|(raw[6]<<8)|raw[7];
        if (mag === 0x2112A442) return true;
    }
    return false;
}
let pkt = 0;

function hx(buf, n) {
    if (!buf) return "";
    var a = new Uint8Array(buf), hex = "";
    for (var i = 0; i < Math.min(a.length, n || a.length); i++) {
        hex += ("0" + a[i].toString(16)).slice(-2);
        if ((i+1)%16===0) hex += "\n"; else if ((i+1)%4===0) hex += " ";
    }
    return hex;
}

function readIovBuffer(iovPtr, iovLen) {
    try {
        var parts = [], total = 0;
        var entrySize = Process.pointerSize * 2;
        for (var i = 0; i < iovLen; i++) {
            var entry = iovPtr.add(i * entrySize);
            var base = entry.readPointer();
            if (base.isNull()) continue;
            var len = entry.add(Process.pointerSize).readU32();
            if (len === 0) continue;
            var part = base.readByteArray(len);
            if (!part) continue;
            var u = new Uint8Array(part);
            parts.push(u); total += u.length;
        }
        var out = new Uint8Array(total), off = 0;
        for (var j = 0; j < parts.length; j++) { out.set(parts[j], off); off += parts[j].length; }
        return out.buffer;
    } catch (e) { return null; }
}

function stunType(raw) {
    if (raw.length < 20) return "";
    var m = (raw[0]<<8)|raw[1];
    var mag = (raw[4]<<24)|(raw[5]<<16)|(raw[6]<<8)|raw[7];
    if (mag !== 0x2112A442) return "";
    var t = {0x0001:"BindingReq",0x0101:"BindingOK",0x0111:"BindingErr",0x0003:"AllocReq",0x0103:"AllocOK",0x0800:"WA_DATA?",0x0801:"Ping"}[m]||"STUN?";
    return "STUN " + t;
}

function logPacket(dir, ip, port, len, raw) {
    pkt++;
    var arr = new Uint8Array(raw);
    var st = arr.length >= 20 ? stunType(arr) : "";
    var first = arr.length >= 2 ? ((arr[0]<<8)|arr[1]).toString(16) : "??";
    
    if (st) {
        var attrs = [];
        var pos = 20;
        while (pos + 4 <= arr.length) {
            var atype = (arr[pos]<<8)|arr[pos+1];
            var alen = (arr[pos+2]<<8)|arr[pos+3];
            pos += 4;
            var anames = {0x4000:"SENDER-SUB",0x4024:"SSRC-LIST",0x4025:"APK-SUB",0x0016:"XOR-REL",0x0008:"HMAC",0x8020:"FP",0x802b:"UNK"};
            attrs.push((anames[atype]||("0x"+atype.toString(16)))+"("+alen+")");
            pos += alen;
            if (pos % 4 !== 0) pos += 4 - (pos % 4);
        }
        console.log("["+dir+" #"+pkt+"] "+ip+":"+port+" ("+len+"b) "+st+" txid="+hx(arr.slice(8,12)).replace(/\s/g,"")+"  attrs=["+attrs.join(",")+"]");
    } else {
        var tag = first.length >= 4 ? first : "??";
        console.log("["+dir+" #"+pkt+"] "+ip+":"+port+" ("+len+"b)");
    }
    console.log("  "+hx(arr, Math.min(arr.length, 64)).replace(/\n/g,"\n  "));
    if (arr.length > 64) console.log("  ... ("+(arr.length-64)+" more bytes)");
}

// ── Track connected FDs ──
var CONN_FD = {};
function markConnFD(fd, ip, port) { CONN_FD[fd] = {ip:ip, port:port}; }
function getConnFD(fd) { return CONN_FD[fd] || null; }
function getPeerAddr(fd) {
    var c = getConnFD(fd); if (c) return c;
    try {
        var sa = Memory.alloc(16), slen = Memory.alloc(4); slen.writeInt(16);
        var getpeername = new NativeFunction(Module.findExportByName("libc.so", "getpeername"), 'int', ['int', 'pointer', 'pointer']);
        if (getpeername(fd, sa, slen) === 0) {
            var port = ((sa.add(2).readU8()<<8)|sa.add(3).readU8());
            var ip = sa.add(4).readU8()+"."+sa.add(5).readU8()+"."+sa.add(6).readU8()+"."+sa.add(7).readU8();
            var peer = { ip: ip, port: port };
            if (port === 3478 || port === 3480) markConnFD(fd, ip, port);
            return peer;
        }
    } catch(e) {}
    return null;
}

// ── sendto ──
var sendto = Module.findExportByName("libc.so", "sendto");
if (sendto) Interceptor.attach(sendto, {
    onEnter(a) { this.fd=a[0].toInt32(); this.buf=a[1]; this.n=a[2].toInt32(); this.addr=a[4]; },
    onLeave(r) {
        if (!this.addr||this.addr.isNull()) return;
        if (this.addr.readU16()!==2) return;
        var port=((this.addr.add(2).readU8()<<8)|this.addr.add(3).readU8());
        var ip=this.addr.add(4).readU8()+"."+this.addr.add(5).readU8()+"."+this.addr.add(6).readU8()+"."+this.addr.add(7).readU8();
        var raw = this.buf.readByteArray(Math.min(this.n,2048));
        var arr = new Uint8Array(raw);
        if (port===3478||port===3480) { markRelayIP(ip); markConnFD(this.fd, ip, port); }
        if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, arr)) return;
        logPacket("SEND", ip, port, this.n, raw);
    }
});

// ── recvfrom ──
var recvfrom = Module.findExportByName("libc.so", "recvfrom");
if (recvfrom) Interceptor.attach(recvfrom, {
    onEnter(a) { this.fd=a[0].toInt32(); this.buf=a[1]; this.n=a[2].toInt32(); this.from=a[4]; },
    onLeave(r) {
        if (r.toInt32()<=0) return;
        var ip="?", port=0;
        if (this.from && !this.from.isNull() && this.from.readU16()===2) {
            port=((this.from.add(2).readU8()<<8)|this.from.add(3).readU8());
            ip=this.from.add(4).readU8()+"."+this.from.add(5).readU8()+"."+this.from.add(6).readU8()+"."+this.from.add(7).readU8();
        } else {
            var peer = getPeerAddr(this.fd);
            if (peer) { ip=peer.ip; port=peer.port; }
        }
        var rawRcv = this.buf.readByteArray(Math.min(r.toInt32(),2048));
        var arrRcv = new Uint8Array(rawRcv);
        if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, arrRcv)) return;
        logPacket("RECV", ip, port, r.toInt32(), rawRcv);
    }
});

// ── recv (wrapped in try-catch, may fail on newer Android) ──
try {
    var recv = Module.findExportByName("libc.so", "recv");
    if (recv) Interceptor.attach(recv, {
        onEnter(a) { this.fd=a[0].toInt32(); this.buf=a[1]; this.n=a[2].toInt32(); },
        onLeave(r) {
            if (r.toInt32()<=0) return;
            var peer = getPeerAddr(this.fd);
            var ip = peer ? peer.ip : "?";
            var port = peer ? peer.port : 0;
            var rawRecv2 = this.buf.readByteArray(Math.min(r.toInt32(),2048));
            var arrRecv2 = new Uint8Array(rawRecv2);
            if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, arrRecv2)) return;
            logPacket("RECV", ip, port, r.toInt32(), rawRecv2);
        }
    });
} catch(e) { console.log("[!] recv hook failed: "+e); }

// ── recvmsg (try-catch) ──
try {
    var recvmsg = Module.findExportByName("libc.so", "recvmsg");
    if (recvmsg) Interceptor.attach(recvmsg, {
        onEnter(a) { this.fd = a[0].toInt32(); this.msg = a[1]; },
        onLeave(r) {
            if (r.toInt32() <= 0 || !this.msg || this.msg.isNull()) return;
            var ip = "?", port = 0;
            try {
                var ptrSize = Process.pointerSize;
                var namePtr = this.msg.readPointer();
                var nameLen = this.msg.add(ptrSize).readU32();
                if (!namePtr.isNull() && nameLen >= 16 && namePtr.readU16() === 2) {
                    port = ((namePtr.add(2).readU8()<<8) | namePtr.add(3).readU8());
                    ip = namePtr.add(4).readU8()+"."+namePtr.add(5).readU8()+"."+namePtr.add(6).readU8()+"."+namePtr.add(7).readU8();
                }
            } catch(e) {}
            if (port === 0) { var p = getPeerAddr(this.fd); if (p) { ip=p.ip; port=p.port; } }
            if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, new Uint8Array(0))) return;
            try {
                var iovPtr = this.msg.add(Process.pointerSize * 2).readPointer();
                var iovLenRawPtr = this.msg.add(Process.pointerSize * 3);
                var iovLen = 0;
                if (!iovLenRawPtr.isNull()) iovLen = Process.pointerSize === 8 ? Number(iovLenRawPtr.readU64()) : iovLenRawPtr.readU32();
                if (!iovPtr.isNull() && iovLen > 0) {
                    var data = readIovBuffer(iovPtr, iovLen);
                    if (data) logPacket("RECV", ip, port, r.toInt32(), data);
                }
            } catch(e) {}
        }
    });
} catch(e) { console.log("[!] recvmsg hook failed: "+e); }

// ── Java DatagramSocket recv (more reliable on Android) ──
try {
    Java.perform(function() {
        var DatagramSocket = Java.use("java.net.DatagramSocket");
        DatagramSocket.receive.overload('java.net.DatagramPacket').implementation = function(pkt) {
            this.receive(pkt);
            var addr = pkt.getAddress();
            var port = pkt.getPort();
            if (addr && (port === 3478 || port === 3480 || isRelayIP(addr.getHostAddress()))) {
                var data = pkt.getData();
                var len = pkt.getLength();
                var buf = Java.array('byte', data);
                logPacket("JAVA_RECV", addr.getHostAddress(), port, len, buf);
            }
        };
        console.log("[+] Java DatagramSocket.receive hooked");
    });
} catch(e) { console.log("[!] Java hook failed: "+e); }

console.log("[+] VoIP UDP capture ready (SEND + RECV)");
