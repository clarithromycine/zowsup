/**
 * Step 1: Find WhatsApp proto Message class names.
 * Run: frida -U -f com.whatsapp -l hook_peer_data_op.js --no-pause
 * 
 * Paste the output back so we can write Step 2 (the actual hook).
 */

function toHex(bytes, maxLen) {
    if (!bytes || bytes.length === 0) return "(empty)";
    var max = maxLen || Math.min(120, bytes.length);
    var hex = "";
    for (var i = 0; i < max; i++)
        hex += ("0" + (bytes[i] & 0xFF).toString(16)).slice(-2);
    if (bytes.length > max) hex += "...";
    return hex;
}

Java.perform(function () {
    console.log("[*] Step 1: finding proto classes...\n");

    // Collect classes containing PeerDataOperation / protocol_message keywords
    var found = [];
    Java.enumerateLoadedClasses({
        onMatch: function (name) {
            if (name.indexOf("PeerDataOperation") >= 0 ||
                name.indexOf("ProtocolMessage") >= 0 ||
                name.indexOf("CompanionCanonical") >= 0) {
                found.push(name);
                console.log("[FOUND] " + name);
            }
        },
        onComplete: function () {
            console.log("\n[*] ====== Done. Found " + found.length + " relevant classes ======");
            console.log("[*] Now searching for the OUTER Message class...\n");

            // The outer Message class has ALL sub-message fields.
            // It extends GeneratedMessageLite/AbstractMessageLite and has toByteArray().
            // Look for classes that have BOTH "protocol_message" AND "conversation" fields.

            // Try known patterns for WhatsApp obfuscated proto
            var protoCandidates = [];
            Java.enumerateLoadedClasses({
                onMatch: function (name) {
                    // WhatsApp proto classes: look for known field name patterns
                    if (name.indexOf("ProtocolMessage$") >= 0 ||
                        name.indexOf("Message$ProtocolMessage") >= 0) {
                        protoCandidates.push(name);
                        console.log("[PROTO-INNER] " + name);
                    }
                },
                onComplete: function () {
                    console.log("\n[*] ====== Inner ProtoMessage classes: " + protoCandidates.length + " ======");
                    
                    // Try to find the OUTER class that wraps ProtocolMessage
                    Java.enumerateLoadedClasses({
                        onMatch: function (name) {
                            // The outer Message class should have "toByteArray" + fields
                            // matching our proto. Look for anything with "GeneratedMessageLite"
                            // in hierarchy that has a "protocolMessage_" internal field
                            try {
                                var cls = Java.use(name);
                                var methods = cls.class.getDeclaredMethods();
                                for (var m = 0; m < methods.length; m++) {
                                    var mname = methods[m].getName();
                                    if (mname.indexOf("peer_data_operation") >= 0 ||
                                        mname.indexOf("peerDataOperation") >= 0) {
                                        console.log("[OUTER-MSG] " + name + " has method: " + mname);
                                        found.push(name);
                                        break;
                                    }
                                }
                            } catch (e) {}
                        },
                        onComplete: function () {
                            console.log("\n[*] ====== ALL DONE ======");
                            console.log("[*] Classes of interest: " + JSON.stringify(found));
                            console.log("[*] Proto inner classes: " + JSON.stringify(protoCandidates));
                            console.log("\n[*] PASTE THIS OUTPUT to get the Step 2 hook script.");
                        }
                    });
                }
            });
        }
    });
});
