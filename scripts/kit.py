"""Drawing kit: SVG document builder, text-as-paths, crayon-style wobbly shapes.

Everything a README image needs has to live inside the SVG itself (GitHub serves
images with a CSP that blocks fonts, scripts and external files), so text is
converted to glyph paths and the "crayon" look is baked into the geometry.
"""
import math
import os
import random

from fontTools.pens.basePen import BasePen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- palettes
BASE = dict(
    clay='#e8894c', clayD='#c2632b', clayL='#f6b98a', pink='#ffa3b3', rose='#ff5f7a',
    sky='#8ed2f7', lav='#c4a8ff', butter='#ffd75e', gold='#f0a92c', blue='#5aa0f0',
    navy='#2c3c6b', red='#e04a4a', green='#7cc576', mint='#a6e3c8', cink='#2f2721',
)
LIGHT = dict(BASE, name='light', bg='#fffaf0', bg2='#f7eedf', dot='#e9dcc8', text='#2f2721',
             text2='#86766a', line='#2f2721', shadow='#2f2721', shadowA=.10, cloud='#ffffff',
             empty='#f1e7d7', emptyLine='#e2d3bd', hatch='#2f2721')
DARK = dict(BASE, name='dark', bg='#1c2030', bg2='#242a3c', dot='#2e3449', text='#f6ecdc',
            text2='#9d97ab', line='#f1e6d4', shadow='#000000', shadowA=.30, cloud='#2f3650',
            empty='#262c3f', emptyLine='#353c55', hatch='#1c1410')
PALETTES = (LIGHT, DARK)


def fmt(v, nd=1):
    s = f'{v:.{nd}f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# ---------------------------------------------------------------- geometry
def rrect_pts(x, y, w, h, r, n=5):
    r = max(0.0, min(r, w / 2, h / 2))
    pts = []
    corners = [(x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def ell_pts(cx, cy, rx, ry, n=28, a0=0.0):
    return [(cx + rx * math.cos(a0 + 2 * math.pi * i / n), cy + ry * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def star_pts(cx, cy, r1, r2, k=5, rot=-90):
    pts = []
    for i in range(2 * k):
        r = r1 if i % 2 == 0 else r2
        a = math.radians(rot + 180 * i / k)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def heart_pts(cx, cy, s, n=40):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * s / 17, cy + y * s / 17))
    return pts


def _resample(pts, step, closed):
    P = list(pts) + ([pts[0]] if closed else [])
    lens = [math.dist(P[i], P[i + 1]) for i in range(len(P) - 1)]
    L = sum(lens) or 1e-6
    n = max(8 if closed else 2, int(round(L / step)))
    targets = [L * i / n for i in range(n)] if closed else [L * i / n for i in range(n + 1)]
    out, seg, acc = [], 0, 0.0
    for t in targets:
        while seg < len(lens) - 1 and acc + lens[seg] < t:
            acc += lens[seg]
            seg += 1
        u = 0 if lens[seg] == 0 else (t - acc) / lens[seg]
        u = min(max(u, 0), 1)
        a, b = P[seg], P[seg + 1]
        out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    return out, L


class _Noise:
    def __init__(self, seed, n):
        r = random.Random(seed)
        self.v = [r.uniform(-1, 1) for _ in range(n)]
        self.n = n

    def __call__(self, x):
        i = math.floor(x)
        f = x - i
        a, b = self.v[i % self.n], self.v[(i + 1) % self.n]
        u = f * f * (3 - 2 * f)
        return a + (b - a) * u


def wobble(pts, amp=1.0, step=6.0, seed=1, closed=True, knots=3.2):
    """Resample a polyline and push it along its normals with smooth noise."""
    R, L = _resample(pts, step, closed)
    K = max(3, int(round(L / 100 * knots)))
    lo, hi = _Noise(seed, K), _Noise(seed * 7 + 3, K * 3)
    n = len(R)
    out = []
    for i, (x, y) in enumerate(R):
        if closed:
            a, b = R[i - 1], R[(i + 1) % n]
            u = i / n
        else:
            a, b = R[max(i - 1, 0)], R[min(i + 1, n - 1)]
            u = i / max(n - 1, 1)
        tx, ty = b[0] - a[0], b[1] - a[1]
        l = math.hypot(tx, ty) or 1
        d = amp * (lo(u * K) + 0.35 * hi(u * K * 3))
        out.append((x - ty / l * d, y + tx / l * d))
    return out


def smooth_d(pts, closed=True, nd=1):
    """Catmull-Rom through pts as compact relative cubic commands (C then s...)."""
    n = len(pts)
    if n < 2:
        return ''
    P = pts
    if closed:
        get = lambda i: P[i % n]
        segs = range(n)
    else:
        get = lambda i: P[min(max(i, 0), n - 1)]
        segs = range(n - 1)
    x0, y0 = P[0]
    out = [f'M{fmt(x0, nd)} {fmt(y0, nd)}']
    cx, cy = x0, y0
    for k, i in enumerate(segs):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        if k == 0:
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            out.append(f'c{fmt(c1[0]-cx, nd)} {fmt(c1[1]-cy, nd)} {fmt(c2[0]-cx, nd)} {fmt(c2[1]-cy, nd)} {fmt(p2[0]-cx, nd)} {fmt(p2[1]-cy, nd)}')
        else:
            out.append(f's{fmt(c2[0]-cx, nd)} {fmt(c2[1]-cy, nd)} {fmt(p2[0]-cx, nd)} {fmt(p2[1]-cy, nd)}')
        cx, cy = p2
    if closed:
        out.append('Z')
    return ''.join(out).replace(' -', '-')


def poly_d(pts, closed=True, nd=1):
    s = 'M' + ' '.join(f'{fmt(x, nd)} {fmt(y, nd)}' for x, y in pts)
    return s + ('Z' if closed else '')


# ---------------------------------------------------------------- fonts
class _FlatPen(BasePen):
    """Flattens glyph outlines to polylines (for wobbly hand-drawn lettering)."""

    def __init__(self, glyphSet, tol=8):
        super().__init__(glyphSet)
        self.contours, self.cur, self.tol = [], [], tol

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        n = max(2, int(math.dist(p0, p3) / self.tol) + 1)
        for i in range(1, n + 1):
            t = i / n
            mt = 1 - t
            self.cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                             mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        n = max(2, int(math.dist(p0, p2) / self.tol) + 1)
        for i in range(1, n + 1):
            t = i / n
            mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                             mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            if math.dist(self.cur[0], self.cur[-1]) < 1e-6:
                self.cur.pop()
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


class Font:
    def __init__(self, key, filename):
        self.key = key
        self.tt = TTFont(os.path.join(ROOT, 'fonts', filename))
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upem = self.tt['head'].unitsPerEm
        self.hmtx = self.tt['hmtx']
        self._d = {}

    def has(self, ch):
        return ord(ch) in self.cmap

    def gname(self, ch):
        return self.cmap.get(ord(ch))

    def adv(self, gname):  # in em
        return self.hmtx[gname][0] / self.upem

    def d(self, gname):
        """Glyph outline in units of 1/100 em, y down, baseline at 0."""
        if gname not in self._d:
            pen = SVGPathPen(self.gs, ntos=lambda v: fmt(v, 0))
            k = 100 / self.upem
            self.gs[gname].draw(TransformPen(pen, (k, 0, 0, -k, 0, 0)))
            self._d[gname] = pen.getCommands()
        return self._d[gname]

    def contours(self, gname, size, x, y, tol_px=1.6):
        k = size / self.upem
        pen = _FlatPen(self.gs, tol=tol_px / k)
        self.gs[gname].draw(pen)
        return [[(x + px * k, y - py * k) for px, py in c] for c in pen.contours]


_FONTS = {}


def font(key):
    files = {'zc': 'ZCOOLKuaiLe-Regular.ttf', 'gs': 'Grandstander-Black.ttf', 'gb': 'Grandstander-Bold.ttf'}
    if key not in _FONTS:
        _FONTS[key] = Font(key, files[key])
    return _FONTS[key]


def is_cjk(ch):
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF) or (0xFF00 <= o <= 0xFFEF) or (0x3000 <= o <= 0x303F)


def runs(s, fkey):
    """Split text into (font, char) pairs; 'mix' = Grandstander for Latin, ZCOOL for CJK."""
    out = []
    for ch in s:
        if fkey == 'mix':
            f = font('zc') if is_cjk(ch) else font('gb')
        elif fkey == 'mixb':
            f = font('zc') if is_cjk(ch) else font('gs')
        else:
            f = font(fkey)
        if ch != ' ' and not f.has(ch):
            for alt in ('zc', 'gb'):
                if font(alt).has(ch):
                    f = font(alt)
                    break
        out.append((f, ch))
    return out


def measure(s, size, fkey='zc', ls=0.0):
    w = 0.0
    for f, ch in runs(s, fkey):
        g = f.gname(ch) or f.gname(' ')
        w += (f.adv(g) if g else 0.5) * size + ls
    return w - (ls if s else 0)


def wrap(s, size, maxw, fkey='zc', max_lines=3):
    """Greedy wrap that keeps Latin words together and breaks CJK anywhere."""
    tokens, cur = [], ''
    for ch in s:
        if is_cjk(ch) or ch == ' ':
            if cur:
                tokens.append(cur)
                cur = ''
            tokens.append(ch)
        else:
            cur += ch
    if cur:
        tokens.append(cur)
    lines, line = [], ''
    no_start = set('，。、；：！？）》」』,.;:!?)')
    for tk in tokens:
        cand = line + tk
        if measure(cand.strip(), size, fkey) <= maxw or not line.strip():
            line = cand
        else:
            if tk in no_start:  # keep closing punctuation on the line
                line += tk
                continue
            lines.append(line.strip())
            line = tk.lstrip()
    if line.strip():
        lines.append(line.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and measure(last + '…', size, fkey) > maxw:
            last = last[:-1]
        lines[-1] = last.rstrip('，、 ') + '…'
    return lines


# ---------------------------------------------------------------- document
class Doc:
    def __init__(self, w, h, pal, title, desc=''):
        self.w, self.h, self.pal, self.title, self.desc = w, h, pal, title, desc
        self.defs, self.css, self.body = [], [], []
        self._glyph_ids = {}
        self._n = 0

    def uid(self, p='i'):
        self._n += 1
        return f'{p}{self._n}'

    def add(self, *parts):
        self.body.extend(parts)

    def style(self, css):
        self.css.append(css)

    def glyph(self, f, g):
        key = (f.key, g)
        if key not in self._glyph_ids:
            gid = f'{f.key}{len(self._glyph_ids)}'
            self._glyph_ids[key] = gid
            d = f.d(g)
            if d:
                self.defs.append(f'<path id="{gid}" d="{d}"/>')
        return self._glyph_ids[key]

    def text(self, s, x, y, size, fkey='zc', fill=None, anchor='start', ls=0.0, attrs=''):
        """Text as <use>d glyph paths. Returns (svg, width, list of glyph right edges in px)."""
        w = measure(s, size, fkey, ls)
        if anchor == 'middle':
            x -= w / 2
        elif anchor == 'end':
            x -= w
        k = size / 100
        uses, edges, cx = [], [], 0.0
        for f, ch in runs(s, fkey):
            g = f.gname(ch) or f.gname(' ')
            adv = (f.adv(g) if g else 0.5) * 100
            if g and ch != ' ' and f.d(g):
                uses.append(f'<use href="#{self.glyph(f, g)}" x="{fmt(cx)}"/>')
            cx += adv + ls / k
            edges.append(x + cx * k)
        fill = fill or self.pal['text']
        svg = f'<g fill="{fill}" transform="translate({fmt(x)} {fmt(y)}) scale({fmt(k, 4)})"{attrs}>{"".join(uses)}</g>'
        return svg, w, edges

    def defpath(self, d):
        pid = self.uid('p')
        self.defs.append(f'<path id="{pid}" d="{d}"/>')
        return pid

    def render(self):
        title = esc(self.title)
        css = '\n'.join(self.css)
        motion = '@media (prefers-reduced-motion: reduce){*{animation:none!important}}'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{title}">'
                f'<title>{title}</title>' + (f'<desc>{esc(self.desc)}</desc>' if self.desc else '') +
                f'<style>{css}\n{motion}</style><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')


# ---------------------------------------------------------------- crayon helpers
def hatch_def(doc, pid='hatch', color=None, gap=5.0, angle=-35, w=1.3):
    color = color or doc.pal['hatch']
    doc.defs.append(f'<pattern id="{pid}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse" '
                    f'patternTransform="rotate({angle})"><path d="M0 0V{gap}" stroke="{color}" stroke-width="{w}"/></pattern>')


def crayon(doc, pts, fill=None, line=None, w=2.4, seed=0, amp=1.0, step=7.0, off=(1.5, -1.1),
           hatch='hatch', hatchA=.16, fill_op=None, closed=True, attrs=''):
    """Crayon doodle shape: misregistered wobbly fill + hatching + wobbly ink line."""
    o = []
    if fill and closed:
        fp = wobble(pts, amp * .8, step, seed + 101, True)
        fp = [(x + off[0], y + off[1]) for x, y in fp]
        d = smooth_d(fp)
        op = f' opacity="{fmt(fill_op, 2)}"' if fill_op is not None else ''
        if hatch:
            pid = doc.defpath(d)
            o.append(f'<use href="#{pid}" fill="{fill}"{op}/><use href="#{pid}" fill="url(#{hatch})" opacity="{fmt(hatchA, 2)}"/>')
        else:
            o.append(f'<path d="{d}" fill="{fill}"{op}/>')
    if line:
        lp = wobble(pts, amp, step, seed, closed)
        o.append(f'<path d="{smooth_d(lp, closed)}" fill="none" stroke="{line}" stroke-width="{fmt(w, 2)}" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    return f'<g{attrs}>{"".join(o)}</g>' if attrs else ''.join(o)


def scribble_line(pts, w, color, seed=0, amp=0.8, step=6, attrs=''):
    lp = wobble(pts, amp, step, seed, False)
    return (f'<path d="{smooth_d(lp, False)}" fill="none" stroke="{color}" stroke-width="{fmt(w, 2)}" '
            f'stroke-linecap="round" stroke-linejoin="round"{attrs}/>')


def card(doc, x, y, w, h, r=22, seed=1, tapes=()):
    """Paper card with dot grid, sticker shadow, crayon frame and washi tapes."""
    p = doc.pal
    gid = doc.uid('dots')
    doc.defs.append(f'<pattern id="{gid}" width="22" height="22" patternUnits="userSpaceOnUse">'
                    f'<circle cx="11" cy="11" r="1.4" fill="{p["dot"]}"/></pattern>')
    clip = doc.uid('clip')
    base = rrect_pts(x, y, w, h, r, 8)
    doc.defs.append(f'<clipPath id="{clip}"><path d="{smooth_d(wobble(base, .9, 10, seed + 5))}"/></clipPath>')
    sh = smooth_d(wobble(rrect_pts(x + 5, y + 7, w, h, r, 8), 1.0, 10, seed + 9))
    out = [f'<path d="{sh}" fill="{p["shadow"]}" opacity="{p["shadowA"]}"/>',
           f'<path d="{smooth_d(wobble(base, .9, 10, seed + 5))}" fill="{p["bg"]}"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})" clip-path="url(#{clip})"/>',
           crayon(doc, base, None, p['line'], 2.6, seed, 1.1, 10)]
    tp = ''.join(tape(tx, ty, tw, th, rot, col, seed + int(tx)) for (tx, ty, tw, th, rot, col) in tapes)
    return ''.join(out), clip, tp


def tape(cx, cy, w, h, rot, color, seed=0):
    r = random.Random(seed)
    pts = []
    zig = 6
    for i in range(zig + 1):  # left zigzag edge
        pts.append((-w / 2 + (2.5 if i % 2 else 0), -h / 2 + h * i / zig))
    pts2 = []
    for i in range(zig + 1):
        pts2.append((w / 2 - (2.5 if i % 2 else 0), h / 2 - h * i / zig))
    outline = [(-w / 2, -h / 2)] + [(w / 2, -h / 2 + r.uniform(-.6, .6))] + pts2 + [(-w / 2, h / 2)] + pts[::-1]
    d = poly_d(outline)
    return (f'<g transform="translate({fmt(cx)} {fmt(cy)}) rotate({fmt(rot)})">'
            f'<path d="{d}" fill="{color}" opacity=".78"/>'
            f'<path d="M{fmt(-w/2+4)} {fmt(-h/2+5)}H{fmt(w/2-4)}" stroke="#fff" stroke-opacity=".35" stroke-width="3"/></g>')


def sparkle(cx, cy, s, color, line=None, w=1.6):
    pts = []
    for i in range(8):
        r = s if i % 2 == 0 else s * .32
        a = math.radians(-90 + 45 * i)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d = poly_d(pts)
    stroke = f' stroke="{line}" stroke-width="{fmt(w, 2)}" stroke-linejoin="round"' if line else ''
    return f'<path d="{d}" fill="{color}"{stroke}/>'


def kf(name, stops, extra=''):
    """CSS keyframes from [(pct, 'css'), ...]."""
    body = ''.join(f'{fmt(p, 3)}%{{{c}}}' for p, c in stops)
    return f'@keyframes {name}{{{body}}}{extra}'
