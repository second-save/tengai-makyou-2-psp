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


def pack_best(data):
    """Optimal parse (literal = 9 bits, match of 2-17 = 13 bits), a few percent smaller than pack().
    shortcut: several times slower than pack(), so only the battle stream uses it; use it for a block that runs out of room."""
    n, ext = len(data), bytes(256) + bytes(data)   # ext[256 + i] = data[i]; before it, the zero-filled ring
    cost, pick = [0] * (n + 1), [None] * n
    for i in range(n - 1, -1, -1):
        cost[i], best = 9 + cost[i + 1], 0
        lim = min(17, n - i)
        for j in range(i, i + 256):   # source index in ext; the copy may run into the bytes it writes
            k = 0
            while k < lim and ext[j + k] == ext[256 + i + k]:
                k += 1
            if k > best:
                best, src = k, j - 256
                if k == lim:
                    break
        for l in range(2, best + 1):
            if 13 + cost[i + l] < cost[i]:
                cost[i], pick[i] = 13 + cost[i + l], (l, (0xEF + src) & 255)
    out, i, nib_at, bit = bytearray(), 0, None, 8
    while i < n:
        if bit == 8:
            flag_at, bit = len(out), 0
            out.append(0)
        if pick[i]:
            l, r = pick[i]
            out.append(r)
            if nib_at is None:
                nib_at = len(out); out.append((l - 2) << 4)
            else:
                out[nib_at] |= l - 2; nib_at = None
            i += l
        else:
            out[flag_at] |= 0x80 >> bit
            out.append(data[i])
            i += 1
        bit += 1
    return bytes(out)


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


def unpack_rings(src, pos, rings):
    """Graphics variant (69:$4700 -> VRAM): two decoders, ring A ($3C8D) and ring B ($3D62), share one flag / nibble /
    byte stream; rings[k] (0 = A, 1 = B) says which one the k-th fetch uses. Returns (bytes, end pos)."""
    ring = [bytearray(256), bytearray(256)]
    w, r, left = [0xEF, 0xEF], [0, 0], [0, 0]
    flags, bit, nib, out = 0, 8, None, bytearray()
    for k in rings:
        if not left[k]:
            if bit == 8:
                flags, bit, pos = src[pos], 0, pos + 1
            lit = flags & (0x80 >> bit)
            bit += 1
            if lit:
                b, pos = src[pos], pos + 1
                out.append(b); ring[k][w[k]] = b; w[k] = (w[k] + 1) & 255
                continue
            r[k], pos = src[pos], pos + 1
            if nib is None:
                nib, pos = src[pos], pos + 1
                n = nib >> 4
            else:
                n, nib = nib & 15, None
            left[k] = n + 2
        b = ring[k][r[k]]; r[k] = (r[k] + 1) & 255; left[k] -= 1
        out.append(b); ring[k][w[k]] = b; w[k] = (w[k] + 1) & 255
    return bytes(out), pos


def pack_rings(data, rings):
    """Greedy encoder for unpack_rings: data[k] is fetched from ring rings[k]."""
    ring = [bytearray(256), bytearray(256)]
    w, left = [0xEF, 0xEF], [0, 0]
    out, bit, flag_at, nib_at = bytearray(), 8, 0, None
    later = [[i for i in range(len(rings)) if rings[i] == k] for k in (0, 1)]   # fetch indices per ring
    at = [0, 0]
    for i, k in enumerate(rings):
        at[k] += 1
        if left[k]:
            left[k] -= 1
            ring[k][w[k]] = data[i]; w[k] = (w[k] + 1) & 255
            continue
        mine = [data[j] for j in later[k][at[k] - 1:at[k] + 16]]   # this ring's next bytes, up to 17
        best, best_r = 0, 0
        for s in range(256):
            n, rr, ww, tmp = 0, s, w[k], {}
            while n < len(mine):
                b = tmp.get(rr, ring[k][rr])
                if b != mine[n]:
                    break
                tmp[ww] = b; rr = (rr + 1) & 255; ww = (ww + 1) & 255; n += 1
            if n > best:
                best, best_r = n, s
        if bit == 8:
            flag_at, bit = len(out), 0
            out.append(0)
        if best >= 2:
            out.append(best_r)
            if nib_at is None:
                nib_at = len(out); out.append((best - 2) << 4)
            else:
                out[nib_at] |= best - 2; nib_at = None
            left[k] = best - 1
        else:
            out[flag_at] |= 0x80 >> bit
            out.append(data[i])
        bit += 1
        ring[k][w[k]] = data[i]; w[k] = (w[k] + 1) & 255
    return bytes(out)


def gfx_rings(header):
    """Fetch order of a 69:$4681 graphics block from its 2-byte header (word count, bit 15 = high bytes from ring B)."""
    n = header[0] | (header[1] & 0x7F) << 8
    return [0, 1 if header[1] & 0x80 else 0] * n


if __name__ == '__main__':
    import os
    for n in (0, 7, 600):
        x = os.urandom(n // 3) + bytes(n // 3) + b'abcabcabcabc' * (n // 36)
        x = x[:len(x) & ~1]
        for hb in (0, 0x80):
            rings = gfx_rings(bytes([len(x) // 2 & 255, len(x) // 512 | hb]))
            assert unpack_rings(pack_rings(x, rings), 0, rings)[0] == x, (n, hb)
    for n in (0, 1, 5, 300, 5000):
        x = os.urandom(n // 3) + bytes(n // 3) + b'abcabcabcabc' * (n // 36)
        assert unpack(pack(x), size=len(x))[0] == x, n
        assert unpack(pack_best(x), size=len(x))[0] == x and len(pack_best(x)) <= len(pack(x)), n
    print('lz self-check ok')
