#!/usr/bin/env python3
"""The game's stream LZSS (RAM routine at $3C8D, traced in Mesen).

Flag byte, MSB first: 1 = literal byte, 0 = match. Match = 1 byte absolute position in a 256-byte ring
(zero-filled, write position starts at 0xEF) + a 4-bit length (copy length + 2). Length nibbles come
from the same byte stream, two per byte, high nibble first.
"""


def unpack(src, pos=0, size=None, stop=None, limit=None):
    """Decode from src[pos:]. Stops after `size` output bytes, when stop(out) is true, or when the input
    reaches `limit` (the streams have no end marker). Returns (bytes, end pos)."""
    if limit is not None:
        src = src[:limit]
    ring = bytearray(256)
    w = 0xEF
    out = bytearray()
    nib = None
    while size is None or len(out) < size:
        if pos >= len(src):
            break
        flags = src[pos]; pos += 1
        for bit in range(8):
            if size is not None and len(out) >= size:
                break
            if pos >= len(src):
                break
            if flags & (0x80 >> bit):
                b = src[pos]; pos += 1
                out.append(b); ring[w] = b; w = (w + 1) & 255
            else:
                r = src[pos]; pos += 1
                if nib is None:
                    if pos >= len(src):
                        break
                    nib = src[pos]; pos += 1
                    n = nib >> 4
                else:
                    n, nib = nib & 15, None
                for _ in range(n + 2):
                    b = ring[r]; r = (r + 1) & 255
                    out.append(b); ring[w] = b; w = (w + 1) & 255
                    if size is not None and len(out) >= size:
                        break
            if stop and stop(out):
                return bytes(out), pos
    return bytes(out), pos


def pack(data):
    """Greedy encoder; unpack(pack(x), size=len(x)) == x."""
    ring = bytearray(256)
    w = 0xEF
    out = bytearray()
    i = 0
    nib_at = None
    while i < len(data):
        flag_at = len(out); out.append(0)
        for bit in range(8):
            if i >= len(data):
                break
            best, best_r = 0, 0
            limit = min(17, len(data) - i)
            if limit >= 2:
                first = data[i]
                for r in [r for r in range(256) if ring[r] == first]:
                    # simulate the copy: the ring is written while it is read
                    n, rr, ww = 0, r, w
                    tmp = None
                    while n < limit:
                        b = ring[rr] if tmp is None or rr not in tmp else tmp[rr]
                        if b != data[i + n]:
                            break
                        if tmp is None:
                            tmp = {}
                        tmp[ww] = b
                        rr = (rr + 1) & 255; ww = (ww + 1) & 255; n += 1
                    if n > best:
                        best, best_r = n, r
                        if n == limit:
                            break
            if best >= 2:
                out.append(best_r)
                if nib_at is None:
                    nib_at = len(out); out.append((best - 2) << 4)
                else:
                    out[nib_at] |= best - 2; nib_at = None
                for k in range(best):
                    ring[w] = data[i + k]; w = (w + 1) & 255
                i += best
            else:
                out[flag_at] |= 0x80 >> bit
                out.append(data[i]); ring[w] = data[i]; w = (w + 1) & 255
                i += 1
    return bytes(out)


if __name__ == '__main__':
    import os
    for n in (0, 1, 5, 300, 5000):
        x = os.urandom(n // 3) + bytes(n // 3) + b'abcabcabcabc' * (n // 36)
        assert unpack(pack(x), size=len(x))[0] == x, n
    print('lz self-check ok')
