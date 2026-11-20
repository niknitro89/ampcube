#!/usr/bin/env python3
"""
htfw.py - tool per firmware Sonicake in formato "HTFW" (AMPCUBE, Pocket Master).

Comandi:
  info   <fw.bin>                       mostra header e sezioni, verifica i CRC
  unpack <fw.bin> <dir>                 estrae header, payload decompresso e sezioni
  repack <dir> <out.bin>                ricostruisce il .bin da una directory di unpack
  verify <fw.bin>                       come info, exit code != 0 se un CRC non torna

Formato (ricavato confrontando AMPCUBE 1.2.3, Pocket Master 1.3.3 e CFW 1.0.2):

  0x00  4   magic "HTFW"
  0x04  2   CRC16/MODBUS del file da 0x06 a fine file, salvato big-endian
            (ricavato da checkCrc in 5868USB.dll di Sonicake Manager)
  0x06  2   0x0001 (incluso nel CRC dell'header)
  0x08  4   dimensione totale del file .bin
  0x0C  16  nome modello (ASCII, padding 0)
  0x1C  4   versione: 'V', major, minor, patch   (es. 56 01 02 03 = V1.2.3)
  0x20  1   ?
  0x21  1   flag compressione (1 = payload LZO1X, 0 = raw)
  0x22  2   ? (0x0005 = numero sezioni?)
  0x24  4   dimensione payload decompresso
  0x28  16  zero
  0x38  5 x 16  tabella sezioni:
          +0  2  CRC16/MODBUS della sezione, memorizzato big-endian
          +2  1  0
          +3  1  tipo ('c','g','f','b','e')
          +4  4  indirizzo di caricamento
          +8  4  offset nel payload decompresso
          +12 4  dimensione
  0x88      payload
            - raw se flag=0
            - se flag=1: u32 dimensione decompressa + stream LZO1X-1
              (ricompressione con lzo1x_1 = identica byte per byte all'originale)
"""
import ctypes, ctypes.util, json, os, struct, sys

HDR = 0x88
NSEC = 5
TAB = 0x38


# ---------------------------------------------------------------- CRC16/MODBUS
_T = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _T.append(_c)


def crc16_modbus(data, crc=0xFFFF):
    t = _T
    for b in data:
        crc = (crc >> 8) ^ t[(crc ^ b) & 0xFF]
    return crc


# ---------------------------------------------------------------- LZO (liblzo2)
_lzo = None


def _lib():
    global _lzo
    if _lzo is None:
        name = ctypes.util.find_library("lzo2") or "liblzo2.so.2"
        try:
            _lzo = ctypes.CDLL(name)
        except OSError:
            sys.exit("serve liblzo2 (Debian/Ubuntu: apt install liblzo2-2)")
    return _lzo


def lzo_decompress(src, size):
    L = _lib()
    dst = ctypes.create_string_buffer(size)
    n = ctypes.c_ulong(size)
    r = L.lzo1x_decompress_safe(src, ctypes.c_ulong(len(src)), dst, ctypes.byref(n), None)
    if r != 0 or n.value != size:
        raise ValueError("decompressione LZO fallita (%d, %d byte)" % (r, n.value))
    return dst.raw[:size]


def lzo_compress(src):
    L = _lib()
    wrk = ctypes.create_string_buffer(16384 * ctypes.sizeof(ctypes.c_void_p))
    dst = ctypes.create_string_buffer(len(src) + len(src) // 16 + 64 + 3)
    n = ctypes.c_ulong(0)
    r = L.lzo1x_1_compress(src, ctypes.c_ulong(len(src)), dst, ctypes.byref(n), wrk)
    if r != 0:
        raise ValueError("compressione LZO fallita (%d)" % r)
    return dst.raw[: n.value]


# ---------------------------------------------------------------- parsing
def parse(d):
    if d[:4] != b"HTFW":
        raise ValueError("magic HTFW non trovato")
    h = {
        "hdr_crc": struct.unpack_from(">H", d, 4)[0],
        "file_size": struct.unpack_from("<I", d, 8)[0],
        "model": d[0x0C:0x1C].rstrip(b"\0").decode("latin1"),
        "version": "V%d.%d.%d" % tuple(d[0x1D:0x20]),
        "compressed": d[0x21],
        "payload_size": struct.unpack_from("<I", d, 0x24)[0],
        "sections": [],
    }
    for i in range(NSEC):
        o = TAB + 16 * i
        crc = struct.unpack_from(">H", d, o)[0]
        typ = chr(d[o + 3])
        addr, off, size = struct.unpack_from("<III", d, o + 4)
        h["sections"].append(dict(type=typ, crc=crc, addr=addr, off=off, size=size))
    if h["compressed"]:
        usz = struct.unpack_from("<I", d, HDR)[0]
        payload = lzo_decompress(d[HDR + 4:], usz)
    else:
        payload = d[HDR:]
    return h, payload


def cmd_info(fn, strict=False):
    d = open(fn, "rb").read()
    h, p = parse(d)
    print("modello  : %s  %s" % (h["model"], h["version"]))
    print("file     : %d byte (header dice %d)" % (len(d), h["file_size"]))
    hc = crc16_modbus(d[6:h["file_size"]])
    print("compresso: %s   payload: 0x%x byte"
          % ("LZO1X" if h["compressed"] else "no", h["payload_size"]))
    bad = int(hc != h["hdr_crc"]) + int(len(d) != h["file_size"])
    print("  CRC header %04x %s" % (h["hdr_crc"], "OK" if hc == h["hdr_crc"] else "ERRATO (calc %04x)" % hc))
    for s in h["sections"]:
        c = crc16_modbus(p[s["off"]:s["off"] + s["size"]])
        ok = c == s["crc"]
        bad += not ok
        print("  [%s] addr 0x%08x off 0x%07x size 0x%07x crc %04x %s"
              % (s["type"], s["addr"], s["off"], s["size"], s["crc"], "OK" if ok else "ERRATO (calc %04x)" % c))
    if strict and bad:
        sys.exit(1)


def cmd_unpack(fn, out):
    d = open(fn, "rb").read()
    h, p = parse(d)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "header.bin"), "wb").write(d[:HDR])
    open(os.path.join(out, "payload.bin"), "wb").write(p)
    for s in h["sections"]:
        open(os.path.join(out, "sec_%s.bin" % s["type"]), "wb").write(p[s["off"]:s["off"] + s["size"]])
    json.dump(h, open(os.path.join(out, "info.json"), "w"), indent=2)
    print("estratto in", out)


def cmd_repack(src, out):
    hdr = bytearray(open(os.path.join(src, "header.bin"), "rb").read())
    info = json.load(open(os.path.join(src, "info.json")))
    payload = bytearray()
    for i, s in enumerate(info["sections"]):
        data = open(os.path.join(src, "sec_%s.bin" % s["type"]), "rb").read()
        off = len(payload)
        payload += data
        o = TAB + 16 * i
        struct.pack_into(">H", hdr, o, crc16_modbus(data))
        struct.pack_into("<II", hdr, o + 8, off, len(data))
    payload = bytes(payload)
    struct.pack_into("<I", hdr, 0x24, len(payload))
    if hdr[0x21]:
        body = struct.pack("<I", len(payload)) + lzo_compress(payload)
    else:
        body = payload
    struct.pack_into("<I", hdr, 8, HDR + len(body))
    img = bytearray(bytes(hdr) + body)
    struct.pack_into(">H", img, 4, crc16_modbus(img[6:]))
    open(out, "wb").write(bytes(img))
    print("scritto", out, HDR + len(body), "byte")


def main(a):
    if len(a) >= 2 and a[0] == "info":
        cmd_info(a[1])
    elif len(a) >= 2 and a[0] == "verify":
        cmd_info(a[1], strict=True)
    elif len(a) >= 3 and a[0] == "unpack":
        cmd_unpack(a[1], a[2])
    elif len(a) >= 3 and a[0] == "repack":
        cmd_repack(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
