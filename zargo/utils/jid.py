import binascii

class Jid:

    @staticmethod
    def unpackByte(n, n2):
        if n == 251:
            return Jid.unpackHex(n2)
        if n == 255:
            return Jid.unpackNibble(n2)
        raise ValueError("bad packed type %s" % n)

    @staticmethod
    def unpackHex(n):
        if n in range(0, 10):
            return n + 48
        if n in range(10, 16):
            return 65 + (n - 10)

        raise ValueError("bad hex %s" % n)

    @staticmethod
    def unpackNibble(n):
        if n in range(0, 10):
            return n + 48
        if n in (10, 11):
            return 45 + (n - 10)
        raise ValueError("bad nibble %s" % n)

    @staticmethod
    def readPacked8(n, data):
        size = data.pop(0)
        remove = 0
        if (size & 0x80) != 0 and n == 251:
            remove = 1
        size = size & 0x7F
        text = data[0:size]
        del data[:size]
        hexData = binascii.hexlify(text).upper()
        dataSize = len(hexData)
        out = []
        if remove == 0:
            for i in range(0, dataSize):
                char = chr(hexData[i]) if type(hexData[i]) is int else hexData[i] #python2/3 compat
                val = ord(binascii.unhexlify("0%s" % char))
                if i == (dataSize - 1) and val > 11 and n != 251: continue
                out.append(Jid.unpackByte(n, val))
        else:
            out = list(hexData[0: -remove])

        return out

    @staticmethod
    def readJid(bytes):
        ba = bytearray(bytes)
        ch = ba.pop(0)
        if ch==250: 

            t = ba.pop(0)
            if t in [251,255] :
                user =  "".join(map(chr,Jid.readPacked8(t,ba)))
            else:
                return None
            t = ba.pop(0)
            if t==3:
                ret = user+"@s.whatsapp.net"
            else:
                return None
            
            return ret
        elif ch==247:
            xx = ba.pop(0)
            device_no = ba.pop(0)
            t = ba.pop(0)
            if t in [251,255] :
                user =  "".join(map(chr,Jid.readPacked8(t,ba)))
            else:
                return None 
            if xx==1:
                ret = "{}@lid".format(user)
            else:
                #其余情况，暂时按照普通id处置
                ret = "{}.{}:{}@s.whatsapp.net".format(user,xx,device_no)

            return ret