/**
 * Frida hook: capture GetCertificates response + ID8.A08/A06 I/O.
 * Usage: frida -U -f com.whatsapp -l hook_plaintext.js --no-pause
 */

function toHex(bytes, maxLen) {
    if (!bytes || bytes.length === 0) return "(empty)";
    var max = maxLen || Math.min(100, bytes.length);
    var hex = "";
    for (var i = 0; i < max; i++) {
        hex += ("0" + (bytes[i] & 0xFF).toString(16)).slice(-2);
    }
    if (bytes.length > max) hex += "...";
    return hex;
}

function toHexFull(bytes) {
    return toHex(bytes, bytes.length);
}

// ── Helper: try to find and dump GetCertificates response via org.json ──
function hookJSONObject() {
    try {
        var JSONObject = Java.use("org.json.JSONObject");
        var origToString = JSONObject.toString;
        JSONObject.toString.implementation = function () {
            var s = origToString.call(this);
            if (s.indexOf("xwa2_ent_get_certificates") >= 0 ||
                s.indexOf("xwa2_ent_request_recovery_nonce") >= 0 ||
                s.indexOf("xwa2_ent_exchange_nonce_and_password") >= 0) {
                console.log("\n===== GRAPHQL RESPONSE (JSON) =====");
                console.log(s.substring(0, 3000));
                if (s.length > 3000) console.log("... (truncated, total " + s.length + " chars)");
                console.log("=========================================\n");
            }
            return s;
        };
        console.log("[+] Hooked JSONObject.toString for GetCertificates");
    } catch (e) {
        console.log("[-] JSONObject hook failed: " + e);
    }
}

Java.perform(function () {
    hookJSONObject();

    var ID8 = Java.use("X.ID8");
    console.log("[+] ID8 class found");

    // ── Hook ID8.A02(Integer, String, String, PublicKey) → String (raw blob) ──
    try {
        var A02overload = ID8.A02.overload(
            'java.lang.Integer',
            'java.lang.String',
            'java.lang.String',
            'java.security.PublicKey'
        );
        A02overload.implementation = function (keyId, password, aad, publicKey) {
            var result = this.A02(keyId, password, aad, publicKey);
            console.log("\n===== ID8.A02 CALLED =====");
            console.log("[keyId]        " + keyId);
            console.log("[password len] " + password.length + " chars");
            console.log("[password]     " + password);
            console.log("[aad]          " + (aad ? ("len=" + aad.length + " '" + aad + "'") : "(null)"));
            console.log("[pubKey algo]  " + publicKey.getAlgorithm());
            console.log("[pubKey fmt]   " + publicKey.getFormat());
            var pubEnc = publicKey.getEncoded();
            console.log("[pubKey enc len] " + pubEnc.length + "B");
            console.log("[pubKey enc hex] " + toHexFull(pubEnc));
            console.log("[result len]   " + result.length + " chars");
            console.log("[result]       " + result);
            console.log("==========================\n");
            return result;
        };
        console.log("[+] Hooked ID8.A02(Integer,String,String,PublicKey)");
    } catch (e) {
        console.log("[-] ID8.A02 hook failed: " + e);
    }

    // ── Hook ID8.A08(String, PublicKey, int, long) → String (PWD_WA hash) ──
    try {
        var A08overload = ID8.A08.overload(
            'java.lang.String',
            'java.security.PublicKey',
            'int',
            'long'
        );
        A08overload.implementation = function (password, publicKey, keyId, timestamp) {
            var result = this.A08(password, publicKey, keyId, timestamp);
            console.log("\n===== ID8.A08 CALLED (PWD_WA) =====");
            console.log("[password len] " + password.length + " chars");
            console.log("[password]     " + password);
            console.log("[keyId]        " + keyId);
            console.log("[timestamp]    " + timestamp);
            console.log("[result len]   " + result.length + " chars");
            console.log("[result first 80] " + result.substring(0, 80));
            console.log("==================================\n");
            return result;
        };
        console.log("[+] Hooked ID8.A08(String,PublicKey,int,long)");
    } catch (e) {
        console.log("[-] ID8.A08 hook failed: " + e);
    }

    // ── Hook ID8.A06(String, X509Certificate) → C39536HdS ──
    ID8.A06.overloads.forEach(function (overload) {
        overload.implementation = function () {
            var result = this.A06.apply(this, arguments);
            var pt = arguments[0] ? arguments[0].toString() : "(null)";
            var ptBytes = arguments[0] ? Java.array('byte',
                Java.use("java.lang.String").$new(pt).getBytes("UTF-8")) : [];

            console.log("\n===== ID8.A06 CALLED =====");
            console.log("[plaintext len]  " + pt.length + " chars / " + ptBytes.length + " UTF8 bytes");
            console.log("[plaintext FULL hex] " + toHexFull(ptBytes));
            console.log("[plaintext first 300] " + pt.substring(0, 300));
            console.log("[plaintext last  300] " + pt.substring(Math.max(0, pt.length - 300)));

            // Dump C39536HdS result: A01=key, A00=data, A03=tag, A02=nonce
            console.log("[RESULT]");
            if (result) {
                var encKey = result.A01.value ? result.A01.value : result.A01;
                var data   = result.A00.value ? result.A00.value : result.A00;
                var tag    = result.A03.value ? result.A03.value : result.A03;
                var nonce  = result.A02.value ? result.A02.value : result.A02;
                console.log("  enc_key: " + encKey.length + "B  " + toHexFull(encKey));
                console.log("  data:    " + data.length + "B   " + toHexFull(data));
                console.log("  tag:     " + tag.length + "B    " + toHexFull(tag));
                console.log("  nonce:   " + nonce.length + "B    " + toHexFull(nonce));
            }
            console.log("==========================\n");
            return result;
        };
        console.log("[+] Hooked ID8.A06 overload");
    });

    // ── Hook OkHttp (WhatsApp uses OkHttp for HTTP) ──
    try {
        var RealCall = Java.use("okhttp3.RealCall");
        RealCall.execute.implementation = function () {
            var request = this.request();
            var url = request.url().toString();
            var method = request.method();
            var body = request.body();
            var bodyStr = "(no body)";
            if (body) {
                try {
                    var Buffer = Java.use("okio.Buffer");
                    var buf = Buffer.$new();
                    body.writeTo(buf);
                    bodyStr = buf.readUtf8();
                } catch (e) { bodyStr = "(read failed)"; }
            }
            console.log("\n===== OKHTTP REQ =====");
            console.log("[method] " + method + " " + url);
            console.log("[body]   " + bodyStr.substring(0, 500));
            var result = this.execute();
            console.log("[status] " + result.code());
            try {
                var src = result.body().source();
                console.log("[resp]   " + src.readUtf8().substring(0, 500));
            } catch (e) { console.log("[resp]   (read failed)"); }
            console.log("======================\n");
            return result;
        };
        console.log("[+] Hooked OkHttp RealCall.execute");
    } catch (e) {
        console.log("[-] OkHttp hook failed: " + e);
    }

    // ── Fallback: hook java.net.URL openConnection ──
    try {
        var URL = Java.use("java.net.URL");
        URL.openConnection.overload().implementation = function () {
            var conn = this.openConnection();
            console.log("\n===== URL CONNECT: " + this.toString() + " =====");
            return conn;
        };
        console.log("[+] Hooked java.net.URL.openConnection");
    } catch (e) {}
});
