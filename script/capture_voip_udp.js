/**
 * Frida script — capture ALL WhatsApp VoIP UDP traffic
 * Run: frida -U -l capture_voip_udp.js com.whatsapp
 */
const CAPTURE_ALL_UDP = false;
// Track relay IPs dynamically — log ANY traffic from relay IPs on any port
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

// Read iovec array and return a single ArrayBuffer of concatenated data
function readIovBuffer(iovPtr, iovLen) {
    try {
        var parts = [];
        var total = 0;
        var entrySize = Process.pointerSize * 2; // struct iovec { void *iov_base; size_t iov_len }
        for (var i = 0; i < iovLen; i++) {
            var entry = iovPtr.add(i * entrySize);
            var base = entry.readPointer();
            if (base.isNull()) continue;
            var len = entry.add(Process.pointerSize).readU32();
            if (len === 0) continue;
            var part = base.readByteArray(len);
            if (!part) continue;
            var u = new Uint8Array(part);
            parts.push(u);
            total += u.length;
        }
        var out = new Uint8Array(total);
        var off = 0;
        for (var j = 0; j < parts.length; j++) { out.set(parts[j], off); off += parts[j].length; }
        return out.buffer;
    } catch (e) { return null; }
}

function stunType(raw) {
    if (raw.length < 20) return "";
    var m = (raw[0]<<8)|raw[1], mag = (raw[4]<<24)|(raw[5]<<16)|(raw[6]<<8)|raw[7];
    if (mag !== 0x2112A442) return "";
    var t = {0x0001:"BindingReq",0x0101:"BindingOK",0x0111:"BindingErr",0x0003:"AllocReq",0x0103:"AllocOK",0x0800:"WA_DATA?",0x0801:"Ping"}[m]||"STUN?";
    // Parse attribute types
    var attrs = [];
    var pos = 20;
    while (pos + 4 <= raw.length) {
        var at = (raw[pos]<<8)|raw[pos+1];
        var al = (raw[pos+2]<<8)|raw[pos+3];
        var an = {0x0006:"USER",0x0008:"HMAC",0x000D:"LIFE",0x0016:"XOR-REL",0x0019:"REQ-TRANS",0x0020:"XOR-MAP",0x0024:"PRIO",0x4000:"SENDER-SUB",0x4024:"SSRC-LIST",0x8028:"FINGER",0x8029:"ICE-CTRLD",0x802A:"ICE-CTRLG"}[at]||("0x"+at.toString(16));
        attrs.push(an+"("+al+")");
        pos += 4 + al + ((4 - (al%4))%4);
    }
    return " STUN "+t+" txid="+hx(raw.slice(8,12),4)+" attrs=["+attrs.join(",")+"]";
}

function logPacket(dir, ip, port, len, data) {
    var raw = new Uint8Array(data);
    pkt++;
    console.log("["+dir+" #"+pkt+"] "+ip+":"+port+" ("+len+"b)"+stunType(raw));
    console.log("  "+hx(raw, Math.min(raw.length, 512)));
}

// Resolve peer address for a connected fd (fallback when recvfrom src_addr is null)
// Also track connected fds via connect() hook
var CONN_FD = {}; // fd → {ip, port}
function markConnFD(fd, ip, port) { CONN_FD[fd] = {ip:ip, port:port}; }
function getConnFD(fd) { return CONN_FD[fd] || null; }

function getPeerAddr(fd) {
    // Check our tracked connections first
    var c = getConnFD(fd);
    if (c) return c;
    try {
        var sa = Memory.alloc(16); // sockaddr_in
        var slen = Memory.alloc(4); slen.writeInt(16);
        var getpeername = new NativeFunction(Module.findExportByName("libc.so", "getpeername"), 'int', ['int', 'pointer', 'pointer']);
        if (getpeername(fd, sa, slen) === 0) {
            var port = ((sa.add(2).readU8()<<8) | sa.add(3).readU8());
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

// ── recv (connected sockets use recv, not recvfrom) ──
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

// ── recvmsg (Android often uses this for UDP) ──
var recvmsg = Module.findExportByName("libc.so", "recvmsg");
if (recvmsg) Interceptor.attach(recvmsg, {
    onEnter(a) { this.fd = a[0].toInt32(); this.msg = a[1]; },
    onLeave(r) {
        if (r.toInt32() <= 0 || !this.msg || this.msg.isNull()) return;
        var ip = "?", port = 0;
        try {
            var ptrSize = Process.pointerSize;
            var namePtr = this.msg.readPointer(); // msg_name
            var nameLen = this.msg.add(ptrSize).readU32(); // msg_namelen
            if (!namePtr.isNull() && nameLen >= 16 && namePtr.readU16() === 2) {
                port = ((namePtr.add(2).readU8()<<8) | namePtr.add(3).readU8());
                ip = namePtr.add(4).readU8()+"."+namePtr.add(5).readU8()+"."+namePtr.add(6).readU8()+"."+namePtr.add(7).readU8();
            }
        } catch(e) {}
        if (port === 0) {
            var peer = getPeerAddr(this.fd);
            if (peer) { ip = peer.ip; port = peer.port; }
        }
        if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, new Uint8Array(0))) return;
        try {
            var iovPtr = this.msg.add(Process.pointerSize * 2).readPointer(); // msg_iov
            var iovLenRawPtr = this.msg.add(Process.pointerSize * 3);
            var iovLen = 0;
            if (!iovLenRawPtr.isNull()) {
                if (Process.pointerSize === 8) iovLen = Number(iovLenRawPtr.readU64()); else iovLen = iovLenRawPtr.readU32();
            }
            if (iovPtr.isNull() || iovLen === 0) {
                logPacket("RECV", ip, port, r.toInt32(), new Uint8Array(0).buffer);
            } else {
                var data = readIovBuffer(iovPtr, iovLen);
                if (data) logPacket("RECV", ip, port, r.toInt32(), data);
            }
        } catch(e) {}
    }
});

// ── send (connected sockets use send, not sendto) ──
var send = Module.findExportByName("libc.so", "send");
if (send) Interceptor.attach(send, {
    onEnter(a) { this.fd=a[0].toInt32(); this.buf=a[1]; this.n=a[2].toInt32(); },
    onLeave(r) {
        if (r.toInt32()<=0) return;
        var peer = getPeerAddr(this.fd);
        var ip = peer ? peer.ip : "?";
        var port = peer ? peer.port : 0;
        var rawSend = this.buf.readByteArray(Math.min(r.toInt32(),2048));
        if (port===3478||port===3480) markRelayIP(ip);
        if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, new Uint8Array(rawSend))) return;
        logPacket("SEND", ip, port, r.toInt32(), rawSend);
    }
});

// ── sendmsg (Android may use this for connected UDP) ──
var sendmsg = Module.findExportByName("libc.so", "sendmsg");
if (sendmsg) Interceptor.attach(sendmsg, {
    onEnter(a) { this.fd=a[0].toInt32(); this.msg=a[1]; },
    onLeave(r) {
        if (r.toInt32()<=0||!this.msg||this.msg.isNull()) return;
        var peer = getPeerAddr(this.fd);
        var ip = peer ? peer.ip : "?";
        var port = peer ? peer.port : 0;
        if (port===3478||port===3480) markRelayIP(ip);
        if (!CAPTURE_ALL_UDP && !isInteresting(ip, port, new Uint8Array(0))) return;
        try {
            var iovPtr2 = this.msg.readPointer(); // msg_iov
            var iovLenPtr2 = this.msg.add(Process.pointerSize);
            var iovLen2 = (Process.pointerSize === 8) ? Number(iovLenPtr2.readU64()) : iovLenPtr2.readU32();
            if (!iovPtr2.isNull() && iovLen2 > 0) {
                var data2 = readIovBuffer(iovPtr2, iovLen2);
                if (data2) logPacket("SEND", ip, port, r.toInt32(), data2);
            }
        } catch(e) {}
    }
});

// ── read (catch ALL incoming on connected UDP sockets via fd) ──
var read_ptr = Module.findExportByName("libc.so", "read");
if (read_ptr) Interceptor.attach(read_ptr, {
    onEnter(a) { this.fd = a[0].toInt32(); this.buf = a[1]; this.n = a[2].toInt32(); },
    onLeave(r) {
        var n = r.toInt32();
        if (n <= 0) return;
        var c = getConnFD(this.fd);
        if (!c) return;
        var raw = this.buf.readByteArray(Math.min(n, 2048));
        var arr = new Uint8Array(raw);
        if (!CAPTURE_ALL_UDP && !isInteresting(c.ip, c.port, arr)) return;
        logPacket("RECV", c.ip, c.port, n, raw);
    }
});

// ── connect (track connected UDP sockets to relay) ──
var connect_fn = Module.findExportByName("libc.so", "connect");
if (connect_fn) Interceptor.attach(connect_fn, {
    onEnter(a) {
        this.fd = a[0].toInt32();
        this.addr = a[1];
        this.addrlen = a[2].toInt32();
    },
    onLeave(r) {
        if (r.toInt32() !== 0) return;
        if (!this.addr || this.addr.isNull()) return;
        if (this.addr.readU16() !== 2) return; // AF_INET
        var port = ((this.addr.add(2).readU8()<<8) | this.addr.add(3).readU8());
        var ip = this.addr.add(4).readU8()+"."+this.addr.add(5).readU8()+"."+this.addr.add(6).readU8()+"."+this.addr.add(7).readU8();
        if (port === 3478 || port === 3480 || isRelayIP(ip)) {
            markConnFD(this.fd, ip, port);
            markRelayIP(ip);
            console.log("[connect] fd=" + this.fd + " → " + ip + ":" + port);
        }
    }
});

console.log("[*] Smart relay tracking: logs ALL traffic from relay IPs on any port");
console.log("[*] CAPTURE_ALL_UDP=" + CAPTURE_ALL_UDP);
console.log("[*] Watching sendto/recvfrom/send/recv/sendmsg/recvmsg...");

// ── Java layer: DatagramSocket.receive ──
Java.perform(function(){
    try {
        var DS=Java.use("java.net.DatagramSocket");
        DS.receive.overload('java.net.DatagramPacket').implementation=function(p){
            this.receive(p);
            var port=p.getPort(), addr=p.getAddress().getHostAddress();
            var d=p.getData(), n=p.getLength(), raw=Java.array('byte',d).slice(0,n);
            if (isInteresting(addr, port, raw)) {
                logPacket("JRECV", addr, port, n, raw);
            }
        };
        console.log("[voip] Hooked DatagramSocket.receive");
    } catch(e) { console.log("[voip] Java recv hook: "+e); }
});

console.log("[voip] Ready");
