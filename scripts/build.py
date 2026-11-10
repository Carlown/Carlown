#!/usr/bin/env python3
"""Build every image in assets/ (light + dark) from profile.json and live GitHub data.

    python scripts/build.py            # fetch data (GITHUB_TOKEN optional) and rebuild
    python scripts/build.py --offline  # rebuild from data/github.json
"""
import datetime as dt
import json
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data as ghdata  # noqa: E402
from clawd import BODY_TOP, clawd, zzz_glyph  # noqa: E402
from kit import (PALETTES, ROOT, Doc, card, crayon, ell_pts, fmt, font, hatch_def, heart_pts, kf,  # noqa: E402
                 measure, poly_d, rrect_pts, scribble_line, smooth_d, sparkle, star_pts, wobble, wrap)

ASSETS = os.path.join(ROOT, 'assets')


def pct(t, T):
    return max(0.0, min(100.0, t / T * 100))


def timeline(name, T, keys, extra=''):
    """keys: [(seconds, css)] -> @keyframes using percentages of period T."""
    keys = sorted(keys, key=lambda k: k[0])
    return kf(name, [(pct(t, T), c) for t, c in keys], extra)


def toggles(name, T, windows, on='opacity:1', off='opacity:0', eps=.02):
    """Hard on/off switching: visible inside each (t0, t1) window."""
    keys = [(0, on if any(a <= 0 for a, _ in windows) else off)]
    for t0, t1 in windows:
        if t0 > 0:
            keys += [(t0 - eps, off), (t0, on)]
        if t1 < T:
            keys += [(t1, on), (t1 + eps, off)]
    keys.append((T, on if any(b >= T for _, b in windows) else off))
    return timeline(name, T, keys)


# ====================================================================== small doodles
def cloud_pts(sc=1.0):
    circles = [(-36, 6, 17), (-16, -9, 23), (10, -14, 22), (32, -1, 18), (0, 7, 20), (-24, 9, 15), (22, 9, 16)]
    pts = []
    for i, (cx, cy, r) in enumerate(circles):
        for k in range(40):
            a = 2 * math.pi * k / 40
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if any((x - ox) ** 2 + (y - oy) ** 2 < (orr - .3) ** 2 for j, (ox, oy, orr) in enumerate(circles) if j != i):
                continue
            pts.append((x, min(y, 17)))
    pts.sort(key=lambda p: math.atan2(p[1] - 2, p[0]))
    return [(x * sc, y * sc) for x, y in pts]


def crescent_pts(R, dx, dy, r, n=40):
    d = math.hypot(dx, dy)
    a = (R * R - r * r + d * d) / (2 * d)
    h = math.sqrt(max(R * R - a * a, 0))
    ux, uy = dx / d, dy / d
    p1 = (a * ux - h * uy, a * uy + h * ux)
    p2 = (a * ux + h * uy, a * uy - h * ux)
    a1, a2 = math.atan2(p1[1], p1[0]), math.atan2(p2[1], p2[0])
    # outer arc: the long way round (away from the inner circle)
    if a2 < a1:
        a2 += 2 * math.pi
    outer = [(R * math.cos(a1 + (a2 - a1) * i / n), R * math.sin(a1 + (a2 - a1) * i / n)) for i in range(n + 1)]
    if any(math.hypot(x - dx, y - dy) < r - .5 for x, y in outer[1:-1]):
        a2 -= 2 * math.pi
        outer = [(R * math.cos(a1 + (a2 - a1) * i / n), R * math.sin(a1 + (a2 - a1) * i / n)) for i in range(n + 1)]
    b1, b2 = math.atan2(p2[1] - dy, p2[0] - dx), math.atan2(p1[1] - dy, p1[0] - dx)
    inner = []
    for sgn in (1, -1):
        e = b2
        while sgn * (e - b1) < 0:
            e += sgn * 2 * math.pi
        cand = [(dx + r * math.cos(b1 + (e - b1) * i / n), dy + r * math.sin(b1 + (e - b1) * i / n)) for i in range(1, n)]
        if all(math.hypot(x, y) <= R + .5 for x, y in cand):
            inner = cand
            break
    return outer + inner


def flower(cx, cy, h, color, line, seed, cls):
    r = random.Random(seed)
    stem = scribble_line([(0, 0), (r.uniform(-2, 2), -h * .5), (0, -h)], 2.2, '#5f9e4f', seed, .5, 4)
    petals = ''.join(f'<circle cx="{fmt(6 * math.cos(a))}" cy="{fmt(-h + 6 * math.sin(a))}" r="5" fill="{color}" stroke="{line}" stroke-width="1.4"/>'
                     for a in [2 * math.pi * k / 5 - math.pi / 2 for k in range(5)])
    center = f'<circle cx="0" cy="{fmt(-h)}" r="3.6" fill="#ffd75e" stroke="{line}" stroke-width="1.3"/>'
    return f'<g transform="translate({fmt(cx)} {fmt(cy)})"><g class="{cls}">{stem}{petals}{center}</g></g>'


def grass(cx, cy, color, seed):
    r = random.Random(seed)
    out = []
    for k in (-1, 0, 1):
        ang = k * .45 + r.uniform(-.1, .1)
        L = r.uniform(8, 13) * (1.2 if k == 0 else 1)
        out.append(scribble_line([(cx + k * 2, cy), (cx + k * 2 + math.sin(ang) * L * .5, cy - L * .55), (cx + k * 2 + math.sin(ang) * L, cy - L)],
                                 2, color, seed + k, .3, 3))
    return ''.join(out)


def heart(cx, cy, s, fill, line, w=1.4, seed=0):
    return f'<path d="{smooth_d(wobble(heart_pts(cx, cy, s, 36), s * .03, s * .25, seed))}" fill="{fill}" stroke="{line}" stroke-width="{fmt(w, 2)}" stroke-linejoin="round"/>'


def star_icon(d, cx, cy, s, fill, line, seed=0):
    return crayon(d, star_pts(cx, cy, s, s * .45), fill, line, max(1.2, s * .12), seed, s * .02, s * .25, (0, 0), hatch=None)


def chevron(x, y, s, color, w=3.4):
    return scribble_line([(x, y - s), (x + s * .9, y), (x, y + s)], w, color, 5, .3, 3)


def arrow_ne(x, y, s, color, w=1.8):
    return (scribble_line([(x, y), (x + s, y - s)], w, color, 1, .2, 3) +
            scribble_line([(x + s * .3, y - s), (x + s, y - s), (x + s, y - s * .3)], w, color, 2, .2, 3))


# ====================================================================== hero
def hero(pal, cfg):
    W, H = 1000, 360
    name = cfg['name']
    d = Doc(W, H, pal, f"Hi, I'm {name}", 'Clawd the crayon crab waves hello; a typing self-intro runs on the left')
    hatch_def(d)
    p = pal
    dark = p['name'] == 'dark'
    frame, clip, tapes = card(d, 10, 10, W - 26, H - 28, 26, seed=3,
                              tapes=[(86, 21, 100, 24, -7, p['pink']), (916, 21, 92, 24, 8, p['sky'])])
    d.add(frame, f'<g clip-path="url(#{clip})">')
    css = []

    # --- sky: sun or moon + stars, drifting clouds
    sx, sy = 912, 92
    if dark:
        moon = crescent_pts(25, 11, -9, 21)
        d.add(f'<g transform="translate({sx} {sy}) rotate(-20)">'
              + crayon(d, moon, p['butter'], p['line'], 2.2, 7, .6, 4, (0, 0), hatch=None) + '</g>')
        r = random.Random(4)
        for i in range(16):
            x, y = r.uniform(560, 970), r.uniform(34, 170)
            if math.hypot(x - sx, y - sy) < 44 or (600 < x < 790 and 70 < y < 150):
                continue
            s = r.uniform(3, 6.5)
            d.add(f'<g transform="translate({fmt(x)} {fmt(y)})"><g class="tw" style="animation-delay:-{fmt(r.uniform(0, 3), 2)}s">'
                  + sparkle(0, 0, s, p['butter']) + '</g></g>')
        css.append('.tw{animation:tw 3s ease-in-out infinite}'
                   + kf('tw', [(0, 'opacity:.25;transform:scale(.6)'), (50, 'opacity:1;transform:scale(1)'), (100, 'opacity:.25;transform:scale(.6)')]))
    else:
        rays = ''.join(scribble_line([(math.cos(a) * 33, math.sin(a) * 33), (math.cos(a) * 44, math.sin(a) * 44)], 3, p['gold'], k, .4, 3)
                       for k, a in enumerate(2 * math.pi * i / 10 for i in range(10)))
        d.add(f'<g transform="translate({sx} {sy})"><g class="rays">{rays}</g>'
              + crayon(d, ell_pts(0, 0, 25, 25, 26), p['butter'], p['line'], 2.4, 9, .7, 5, (1, -.8), hatchA=.12) + '</g>')
        css.append('.rays{animation:spin 40s linear infinite}' + kf('spin', [(0, 'transform:rotate(0)'), (100, 'transform:rotate(360deg)')]))
    cl_line = p['line'] if not dark else '#7d86a6'
    for i, (cx, cy, sc, dur) in enumerate([(528, 54, 1.0, 34), (968, 168, .72, 27), (706, 44, .62, 40)]):
        pts = [(x + cx, y + cy) for x, y in cloud_pts(sc)]
        d.add(f'<g class="cloud c{i}">' + crayon(d, pts, p['cloud'], cl_line, 2.2, 20 + i, .6, 6, (1.2, -.8), hatch=None) + '</g>')
        css.append(f'.c{i}{{animation:drift{i} {dur}s ease-in-out infinite alternate}}'
                   + kf(f'drift{i}', [(0, f'transform:translateX({-26 - i * 6}px)'), (100, f'transform:translateX({26 + i * 6}px)')]))

    # --- ground, grass and flowers under Clawd
    gy = 318
    d.add(scribble_line([(606, gy + 1), (700, gy - 1), (800, gy + 1.5), (900, gy - .5), (990, gy + 1)], 2.6, p['line'], 31, .8, 8))
    gcol = '#6fae5b' if not dark else '#7fc58f'
    for i, x in enumerate([628, 676, 742, 862, 930, 962]):
        d.add(grass(x, gy, gcol, 40 + i))
    d.add(flower(652, gy, 30, p['pink'], p['cink'], 51, 'sway s1'), flower(948, gy, 24, p['lav'], p['cink'], 52, 'sway s2'))
    css.append('.sway{animation:sway 3.2s ease-in-out infinite alternate}.s2{animation-delay:-1.6s}'
               + kf('sway', [(0, 'transform:rotate(-7deg)'), (100, 'transform:rotate(7deg)')]))

    # --- left text block
    x0 = 66
    t, _, _ = d.text(cfg['greeting'], x0 + 2, 108, 30, 'gb', p['text2'])
    d.add(t)
    # crayon lettering of the name, letters bounce in a wave
    f = font('gs')
    size = 106
    base_y = 214
    name_w = measure(name, size, 'gs')
    swash = wobble([(x0 - 6, base_y - 18), (x0 + name_w * .5, base_y - 21), (x0 + name_w + 10, base_y - 24)], 1.2, 12, 77, False)
    d.add(f'<path class="hl" d="{smooth_d(swash, False)}" pathLength="1" fill="none" stroke="{p["lav"] if dark else p["butter"]}" '
          f'stroke-width="24" stroke-linecap="round" opacity="{.55 if not dark else .3}"/>')
    css.append('.hl{stroke-dasharray:1 1;animation:hl 1.1s .5s cubic-bezier(.3,.6,.3,1) backwards}'
               + kf('hl', [(0, 'stroke-dashoffset:1'), (100, 'stroke-dashoffset:0')]))
    cx = x0
    for i, ch in enumerate(name):
        g = f.gname(ch)
        adv = f.adv(g) * size
        if ch != ' ':
            cons = f.contours(g, size, cx, base_y, 1.8)
            fill_d = ''.join(smooth_d([(x + 2.4, y - 1.8) for x, y in wobble(c, .8, 5, 300 + i * 13 + k)]) for k, c in enumerate(cons))
            line_d = ''.join(smooth_d(wobble(c, 1.0, 5, 500 + i * 17 + k)) for k, c in enumerate(cons))
            pid = d.defpath(fill_d)
            d.add(f'<g class="nb" style="animation-delay:{fmt(1.6 + i * .09, 2)}s">'
                  f'<use href="#{pid}" x="5" y="6" fill="{p["shadow"]}" opacity="{p["shadowA"] * 1.6:.2f}"/>'
                  f'<use href="#{pid}" fill="{p["clay"]}"/><use href="#{pid}" fill="url(#hatch)" opacity=".2"/>'
                  f'<path d="{line_d}" fill="none" stroke="{p["line"] if dark else p["cink"]}" stroke-width="3.2" stroke-linejoin="round"/></g>')
        cx += adv
    css.append('.nb{animation:nb 7s ease-in-out infinite}'
               + kf('nb', [(0, 'transform:translateY(0)'), (3, 'transform:translateY(-14px)'), (6, 'transform:translateY(0)'),
                           (7.5, 'transform:translateY(-3px)'), (9, 'transform:translateY(0)'), (100, 'transform:translateY(0)')]))
    # sparkles around the name
    for i, (sx_, sy_, s_) in enumerate([(x0 + name_w + 26, 128, 11), (x0 + name_w + 46, 168, 7), (x0 - 18, 140, 8)]):
        d.add(f'<g transform="translate({fmt(sx_)} {fmt(sy_)})"><g class="spk" style="animation-delay:{fmt(i * .9, 2)}s">'
              + sparkle(0, 0, s_, p['butter'], p['cink'], 1.4) + '</g></g>')
    css.append('.spk{animation:spk 2.7s ease-in-out infinite}'
               + kf('spk', [(0, 'transform:scale(0) rotate(0)'), (30, 'transform:scale(1) rotate(45deg)'),
                            (60, 'transform:scale(0) rotate(90deg)'), (100, 'transform:scale(0) rotate(90deg)')]))
    # @handle pill + tagline
    hw = measure('@' + cfg['user'], 20, 'gb')
    pill = rrect_pts(x0, 236, hw + 28, 34, 17, 6)
    d.add(crayon(d, pill, p['clay'], p['clay'], 2.2, 61, .6, 6, (1, -.6), hatch=None, fill_op=.16))
    t, _, _ = d.text('@' + cfg['user'], x0 + 14, 260, 20, 'gb', p['clayD'] if not dark else p['clayL'])
    d.add(t)
    t, _, _ = d.text(cfg['tagline'], x0 + hw + 46, 260, 19, 'gb', p['text2'])
    d.add(t)

    # --- typing line
    ty = 312
    d.add(chevron(x0 + 4, ty - 9, 8, p['clay']))
    tx = x0 + 30
    maxw = 560
    lines = []
    for s in cfg['typing']:
        sz = 28
        w = measure(s, sz, 'mix')
        if w > maxw:
            sz = 28 * maxw / w
        lines.append((s, sz))
    T = 0.0
    plan = []
    for s, sz in lines:
        svg, w, edges = d.text(s, tx, ty, sz, 'mix', p['text'])
        ev = []
        t0 = T + .25
        tcur = t0
        for k, ch in enumerate(s):
            tcur += .13 if ord(ch) > 0x2e80 else .07
            ev.append((tcur, edges[k] - tx))
        hold = tcur + 2.0
        tcur = hold
        for k in range(len(s) - 1, -1, -1):
            tcur += .03
            ev.append((tcur, (edges[k - 1] - tx) if k > 0 else 0))
        plan.append((svg, ev))
        T = tcur + .3
    cur_vals = [(0.0, 0.0)]
    for i, (svg, ev) in enumerate(plan):
        cid = d.uid('tc')
        vals = [(0.0, 0.0)] + ev + [(T, 0.0)]
        kt, vv = _dedupe(vals, T)
        d.defs.append(f'<clipPath id="{cid}"><rect x="{fmt(tx - 2)}" y="{ty - 34}" height="48" width="0">'
                      f'<animate attributeName="width" dur="{fmt(T, 2)}s" repeatCount="indefinite" calcMode="discrete" '
                      f'keyTimes="{kt}" values="{";".join(fmt(v + (2 if v > 0 else 0)) for v in vv)}"/></rect></clipPath>')
        d.add(f'<g clip-path="url(#{cid})">{svg}</g>')
        cur_vals += ev
    cur_vals.append((T, 0.0))
    kt, vv = _dedupe(cur_vals, T)
    d.add(f'<g class="blink"><rect x="{fmt(tx + 3)}" y="{ty - 25}" width="3.6" height="31" rx="1.6" fill="{p["clay"]}">'
          f'<animateTransform attributeName="transform" type="translate" dur="{fmt(T, 2)}s" repeatCount="indefinite" '
          f'calcMode="discrete" keyTimes="{kt}" values="{";".join(fmt(v) + " 0" for v in vv)}"/></rect></g>')
    css.append('.blink{animation:blink 1s steps(1) infinite}' + kf('blink', [(0, 'opacity:1'), (50, 'opacity:0'), (100, 'opacity:0')]))

    # --- Clawd: wave + talk, look at the text, happy jump with hearts
    P = 8.0
    cxp, s = 806, 150
    d.add(clawd(d, cxp, gy, s, 'h', seed=11, faces=('open', 'happy'), mouths=('smile', 'grin', 'o')))
    bob = []
    for k in range(17):
        tt = k * .5
        if 4.6 < tt < 6.3:
            continue
        bob.append((tt, 'transform:scale(1,1)' if k % 2 == 0 else 'transform:scale(1.015,.975)'))
    bob += [(4.8, 'transform:scale(1,1)'), (5.0, 'transform:scale(1.1,.86)'), (5.12, 'transform:scale(.94,1.08)'),
            (5.62, 'transform:scale(1,1)'), (5.74, 'transform:scale(1.12,.85)'), (5.92, 'transform:scale(.98,1.03)'),
            (6.1, 'transform:scale(1,1)')]
    up = 'animation-timing-function:cubic-bezier(.2,.7,.4,1)'
    down = 'animation-timing-function:cubic-bezier(.6,0,.85,.4)'
    wave = [(0, 'transform:rotate(0)'), (.3, 'transform:rotate(0)'), (.55, 'transform:rotate(-58deg)')]
    for k in range(6):
        wave.append((.8 + k * .25, f'transform:rotate({-74 if k % 2 == 0 else -36}deg)'))
    wave += [(2.45, 'transform:rotate(0)'), (4.95, 'transform:rotate(0)'), (5.15, 'transform:rotate(-62deg)'),
             (5.65, 'transform:rotate(-62deg)'), (5.95, 'transform:rotate(0)'), (P, 'transform:rotate(0)')]
    css += [
        '.h-jump,.h-bob,.h-armR,.h-armL,.h-blink,.h-face,.h-shadow,.h-eyesO,.h-eyesH,.h-m1,.h-m2,.h-m3,.bub,.hrt'
        f'{{animation-duration:{P}s;animation-iteration-count:infinite}}',
        '.h-jump{animation-name:hjump}.h-bob{animation-name:hbob}.h-armR{animation-name:harmR}.h-armL{animation-name:harmL}'
        '.h-blink{animation-name:hblink}.h-face{animation-name:hface}.h-shadow{animation-name:hshadow}'
        '.h-eyesO{animation-name:heo}.h-eyesH{animation-name:heh}.h-m1{animation-name:hm1}.h-m2{animation-name:hm2}'
        '.h-m3{animation-name:hm3}.bub{animation-name:bub}.hrt{animation-name:hrt}',
        timeline('hjump', P, [(0, 'transform:translateY(0)'), (5.02, f'transform:translateY(0);{up}'),
                              (5.36, f'transform:translateY(-38px);{down}'), (5.68, 'transform:translateY(0)'), (P, 'transform:translateY(0)')]),
        timeline('hbob', P, bob),
        timeline('harmR', P, wave),
        timeline('harmL', P, [(0, 'transform:rotate(0)'), (2.9, 'transform:rotate(0)'), (3.15, 'transform:rotate(24deg)'),
                              (4.2, 'transform:rotate(24deg)'), (4.45, 'transform:rotate(0)'), (4.95, 'transform:rotate(0)'),
                              (5.15, 'transform:rotate(62deg)'), (5.65, 'transform:rotate(62deg)'), (5.95, 'transform:rotate(0)'),
                              (P, 'transform:rotate(0)')]),
        timeline('hblink', P, [(0, 'transform:scaleY(1)'), (3.5, 'transform:scaleY(1)'), (3.57, 'transform:scaleY(.1)'),
                               (3.65, 'transform:scaleY(1)'), (7.2, 'transform:scaleY(1)'), (7.27, 'transform:scaleY(.1)'),
                               (7.35, 'transform:scaleY(1)'), (P, 'transform:scaleY(1)')]),
        timeline('hface', P, [(0, 'transform:translateX(0)'), (2.8, 'transform:translateX(0)'), (3.05, 'transform:translate(-8px,1px)'),
                              (4.3, 'transform:translate(-8px,1px)'), (4.55, 'transform:translateX(0)'), (P, 'transform:translateX(0)')]),
        timeline('hshadow', P, [(0, 'transform:scale(1)'), (5.02, 'transform:scale(1)'), (5.36, 'transform:scale(.6)'),
                                (5.68, 'transform:scale(1)'), (P, 'transform:scale(1)')]),
        toggles('heo', P, [(0, 4.9), (6.4, P)]), toggles('heh', P, [(4.9, 6.4)]),
        toggles('hm1', P, [(0, .5), (.7, .9), (1.1, 1.3), (1.5, 4.9), (6.4, P)]), toggles('hm2', P, [(4.9, 6.4)]),
        toggles('hm3', P, [(.5, .7), (.9, 1.1), (1.3, 1.5)]),
        timeline('bub', P, [(0, 'transform:scale(0)'), (.3, 'transform:scale(0)'), (.48, 'transform:scale(1.1)'), (.6, 'transform:scale(1)'),
                            (2.5, 'transform:scale(1)'), (2.7, 'transform:scale(0)'), (P, 'transform:scale(0)')]),
        timeline('hrt', P, [(0, 'transform:translateY(0) scale(0);opacity:0'), (5.15, 'transform:translateY(0) scale(0);opacity:0'),
                            (5.35, 'transform:translateY(-6px) scale(1);opacity:1'), (6.3, 'transform:translateY(-44px) scale(.9);opacity:1'),
                            (6.7, 'transform:translateY(-54px) scale(.8);opacity:0'), (P, 'transform:translateY(-54px) scale(.8);opacity:0')]),
    ]
    # speech bubble (pivot at the tail tip)
    tipx, tipy = 742, 178
    bw = max(150, measure(cfg['bubble'], 26, 'gb') + 44)
    bx0, by0, bh = -bw + 22, -96, 56
    body = rrect_pts(bx0, by0, bw, bh, 18, 6)
    k = next(i for i, (x, y) in enumerate(body) if y >= by0 + bh - .01 and x < bx0 + bw - 18)
    bub_pts = body[:k] + [(-6, by0 + bh), (0, 0), (-24, by0 + bh)] + body[k:]
    t, _, _ = d.text(cfg['bubble'], bx0 + bw / 2, by0 + 37, 26, 'gb', p['cink'], anchor='middle')
    d.add(f'<g transform="translate({tipx} {tipy})"><g class="bub">'
          + crayon(d, bub_pts, '#fffdf7', p['cink'], 2.4, 81, .7, 6, (1.2, -1), hatch=None) + t + '</g></g>')
    for i, (hx, hy, hs, col) in enumerate([(-34, -2, 11, p['rose']), (2, -16, 14, p['pink']), (36, -4, 10, p['rose'])]):
        d.add(f'<g transform="translate({cxp + hx} {gy - s * .98 + hy})"><g class="hrt" style="animation-delay:{fmt(i * .14, 2)}s">'
              + heart(0, 0, hs, col, p['cink'], 1.6, 90 + i) + '</g></g>')
    d.add('</g>', tapes)
    d.style('\n'.join(css))
    return d


def _dedupe(vals, T):
    """(t, v) list -> strictly increasing keyTimes / values strings for SMIL."""
    out = []
    for t, v in sorted(vals, key=lambda tv: tv[0]):
        t = min(max(t / T, 0), 1)
        if out and t <= out[-1][0] + 1e-5:
            if t >= 1:
                continue
            t = out[-1][0] + 1e-4
        out.append((t, v))
    if out[-1][0] < 1:
        out.append((1.0, out[0][1]))
    return ';'.join(f'{t:.4f}'.rstrip('0').rstrip('.') if t else '0' for t, _ in out), [v for _, v in out]


# ====================================================================== contribution patrol
LEVELS = {
    'light': ['#f1e7d7', '#ffd8b4', '#f8b07a', '#e8894c', '#c2632b'],
    'dark': ['#262c3f', '#5b3a2e', '#94512f', '#d97a3f', '#ffab61'],
}


def contrib(pal, cfg, data):
    p = pal
    dark = p['name'] == 'dark'
    days = data['calendar']['days']
    total = data['calendar']['total']
    W, H = 1000, 300
    d = Doc(W, H, pal, 'Clawd patrols my graph', f'{total} contributions in the last year; Clawd nibbles each active cell off the graph')
    hatch_def(d)
    frame, clip, tapes = card(d, 10, 10, W - 26, H - 26, 24, seed=13, tapes=[(904, 20, 86, 24, 6, p['butter'])])
    d.add(frame, f'<g clip-path="url(#{clip})">')
    css = []

    d0 = dt.date.fromisoformat(days[0]['date'])
    sunday0 = d0 - dt.timedelta(days=(d0.weekday() + 1) % 7)
    cells = []
    for day in days:
        dd = dt.date.fromisoformat(day['date'])
        cells.append(((dd - sunday0).days // 7, (dd.weekday() + 1) % 7, day['level'], day['count'], dd))
    ncol = max(c[0] for c in cells) + 1
    gx0, gy0 = 62, 104
    pitch = min(17.0, 878 / ncol)
    cs = pitch * .8
    pos = lambda col, row: (gx0 + col * pitch + cs / 2, gy0 + row * pitch + cs / 2)

    # header
    t, _, _ = d.text('Clawd patrols my graph', 44, 60, 28, 'gs', p['text'])
    d.add(t)
    t, _, _ = d.text(f'{total:,} contributions this year', 956, 60, 20, 'mix', p['text2'], anchor='end')
    d.add(t)
    # month + weekday labels
    seen = set()
    for col, row, lvl, cnt, dd in cells:
        if dd.day <= 7 and row == 0 or (col == 0 and row == 0):
            key = (dd.year, dd.month)
            if key in seen or col > ncol - 3:
                continue
            seen.add(key)
            t, _, _ = d.text(dd.strftime('%b'), gx0 + col * pitch, gy0 - 9, 14, 'mix', p['text2'])
            d.add(t)
    for row, lab in ((1, 'Mon'), (3, 'Wed'), (5, 'Fri')):
        t, _, _ = d.text(lab, gx0 - 10, gy0 + row * pitch + cs * .82, 13, 'gb', p['text2'], anchor='end')
        d.add(t)

    # cell shapes (a few wobbly variants per level, reused with <use>)
    variants = {}
    for lvl in range(5):
        for v in range(3):
            sh = rrect_pts(-cs / 2, -cs / 2, cs, cs, cs * .26, 3)
            dd_ = smooth_d(wobble(sh, .45, 2.6, 900 + lvl * 7 + v), True)
            cid = f'k{lvl}{v}'
            if lvl == 0:
                d.defs.append(f'<path id="{cid}" d="{dd_}" fill="{LEVELS[p["name"]][0]}" stroke="{p["emptyLine"]}" stroke-width=".9"/>')
            else:
                stroke = f' stroke="{p["cink"]}" stroke-width="1.1"' if not dark else ''
                d.defs.append(f'<path id="{cid}" d="{dd_}" fill="{LEVELS[p["name"]][lvl]}"{stroke}/>')
            variants[(lvl, v)] = cid

    targets = [c for c in cells if c[3] > 0 or c[2] > 0]
    # patrol order: sweep the weeks left to right, snake through each column
    order, cur_row = [], 3
    bycol = {}
    for c in targets:
        bycol.setdefault(c[0], []).append(c)
    for col in sorted(bycol):
        lst = sorted(bycol[col], key=lambda c: c[1])
        if abs(lst[-1][1] - cur_row) < abs(lst[0][1] - cur_row):
            lst.reverse()
        order += lst
        cur_row = lst[-1][1]
    foot = cs / 2 + 1.5
    start = (gx0 - 92, pos(0, 3)[1] + foot)
    exit_ = (gx0 + ncol * pitch + 80, pos(0, 3)[1] + foot)
    pts = [start] + [(pos(c[0], c[1])[0], pos(c[0], c[1])[1] + foot) for c in order] + [exit_]
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    v, pause = 190.0, .3
    budget = 30.0
    if L / v + len(order) * pause > budget:
        k = (L / v + len(order) * pause) / budget
        v *= k
        pause = max(.12, pause / k)
    keys, eat_t = [], []
    tcur = 0.0
    keys.append((0.0, start))
    for i in range(1, len(pts)):
        tcur += math.dist(pts[i - 1], pts[i]) / v
        keys.append((tcur, pts[i]))
        if i < len(pts) - 1:
            eat_t.append(tcur)
            tcur += pause
            if i == len(pts) - 2:  # victory hop after the last bite
                tcur += 1.0
                jump_t = tcur - 1.0
            keys.append((tcur, pts[i]))
    if not order:
        jump_t = tcur
    t_exit = tcur
    T = t_exit + 2.2
    regrow0 = t_exit + .1

    # draw cells
    r = random.Random(5)
    eaten = {(c[0], c[1]): i for i, c in enumerate(order)}
    for col, row, lvl, cnt, dd in cells:
        x, y = pos(col, row)
        use = f'<use href="#{variants[(lvl, r.randrange(3))]}"/>'
        i = eaten.get((col, row))
        if i is None:
            d.add(f'<use href="#{variants[(lvl, r.randrange(3))]}" x="{fmt(x)}" y="{fmt(y)}"/>')
            continue
        te = eat_t[i]
        tr = regrow0 + col / max(ncol, 1) * 1.0
        d.add(f'<g transform="translate({fmt(x)} {fmt(y)})"><use href="#{variants[(0, 0)]}"/><g class="e{i}">{use}</g></g>')
        css.append(f'.e{i}{{animation:e{i} {fmt(T, 2)}s infinite}}' + timeline(f'e{i}', T, [
            (0, 'transform:scale(1)'), (te - .02, 'transform:scale(1)'), (te + .08, 'transform:scale(1.35) rotate(8deg)'),
            (te + .22, 'transform:scale(0) rotate(-20deg)'), (tr, 'transform:scale(0)'), (tr + .25, 'transform:scale(1.2)'),
            (tr + .42, 'transform:scale(1)'), (T, 'transform:scale(1)')]))
        # pop particle: hearts for small days, stars for big ones
        pop = (heart(0, 0, 7, p['rose'], p['cink'], 1.1, i) if lvl <= 2 else
               star_icon(d, 0, 0, 7.5, p['butter'], p['cink'], i))
        d.add(f'<g transform="translate({fmt(x)} {fmt(y - 22)})"><g class="q{i}" opacity="0">{pop}</g></g>')
        css.append(f'.q{i}{{animation:q{i} {fmt(T, 2)}s infinite}}' + timeline(f'q{i}', T, [
            (0, 'opacity:0;transform:translateY(0) scale(.3)'), (te, 'opacity:0;transform:translateY(0) scale(.3)'),
            (te + .12, 'opacity:1;transform:translateY(-4px) scale(1)'), (te + .75, 'opacity:0;transform:translateY(-24px) scale(.8)'),
            (T, 'opacity:0;transform:translateY(-24px) scale(.8)')]))

    # Clawd
    cs_ = 34
    d.add(f'<g class="cw-move">' + clawd(d, 0, 0, cs_, 'cw', seed=11, faces=('open', 'happy'), mouths=('smile', 'o'), shadow=True) + '</g>')
    mv = [(t_, f'transform:translate({fmt(x)}px,{fmt(y)}px)') for t_, (x, y) in keys] + [(T, f'transform:translate({fmt(start[0])}px,{fmt(start[1])}px)')]
    # stay off-screen until the loop restarts
    mv.insert(-1, (t_exit + .01, f'transform:translate({fmt(start[0])}px,{fmt(start[1])}px)'))
    css += [f'.cw-move{{animation:cwmove {fmt(T, 2)}s linear infinite}}' + timeline('cwmove', T, mv),
            '.cw-legA,.cw-legB{animation:cwleg .34s linear infinite}.cw-legB{animation-delay:-.17s}'
            + kf('cwleg', [(0, 'transform:translateY(0)'), (25, 'transform:translateY(-2.6px)'), (50, 'transform:translateY(0)'), (100, 'transform:translateY(0)')]),
            '.cw-bob{animation:cwbob .17s ease-in-out infinite alternate}' + kf('cwbob', [(0, 'transform:translateY(0)'), (100, 'transform:translateY(-1.2px)')]),
            f'.cw-m1{{animation:cwm1 {fmt(T, 2)}s infinite}}.cw-m2{{animation:cwm2 {fmt(T, 2)}s infinite}}'
            f'.cw-eyesO{{animation:cweo {fmt(T, 2)}s infinite}}.cw-eyesH{{animation:cweh {fmt(T, 2)}s infinite}}'
            f'.cw-jump{{animation:cwjump {fmt(T, 2)}s infinite}}',
            toggles('cwm2', T, [(te - .04, te + pause * .8) for te in eat_t]),
            toggles('cwm1', T, _invert([(te - .04, te + pause * .8) for te in eat_t], T)),
            toggles('cweh', T, [(jump_t, jump_t + 1.2)]), toggles('cweo', T, _invert([(jump_t, jump_t + 1.2)], T)),
            timeline('cwjump', T, [(0, 'transform:translateY(0)'), (jump_t + pause, 'transform:translateY(0)'),
                                   (jump_t + pause + .2, 'transform:translateY(-16px)'), (jump_t + pause + .4, 'transform:translateY(0)'),
                                   (jump_t + pause + .55, 'transform:translateY(-7px)'), (jump_t + pause + .7, 'transform:translateY(0)'),
                                   (T, 'transform:translateY(0)')])]

    # footer: caption + legend
    t, _, _ = d.text('Fed daily by GitHub Actions · eaten cells grow back tomorrow', 44, 262, 15, 'mix', p['text2'])
    d.add(t)
    lx = 956 - 5 * (cs + 4) - 26
    t, _, _ = d.text('Less', lx - 8, 262, 14, 'gb', p['text2'], anchor='end')
    d.add(t)
    for lvl in range(5):
        d.add(f'<use href="#{variants[(lvl, lvl % 3)]}" x="{fmt(lx + lvl * (cs + 4) + cs / 2)}" y="{fmt(257 - cs / 2 + 2)}"/>')
    t, _, _ = d.text('More', lx + 5 * (cs + 4) + 4, 262, 14, 'gb', p['text2'])
    d.add(t)
    d.add('</g>', tapes)
    d.style('\n'.join(css))
    return d


def _invert(windows, T):
    out, t = [], 0.0
    for a, b in sorted(windows):
        if a > t:
            out.append((t, a))
        t = max(t, b)
    if t < T:
        out.append((t, T))
    return out


# ====================================================================== stats
LANG_COLORS = {'Java': '#d98a3a', 'Python': '#5aa0f0', 'JavaScript': '#ffd75e', 'TypeScript': '#3d6fc0',
               'HTML': '#e8604c', 'CSS': '#b48cf0', 'SCSS': '#ff8fb1', 'C#': '#7cc576', 'Shell': '#9ad46a',
               'PowerShell': '#6aa7d8', 'Dockerfile': '#74c7d9', 'Go': '#62c6e0', 'Rust': '#d9a37a', 'C++': '#f07ca0',
               'C': '#8f9bb3', 'Lua': '#6c7fe0', 'Vue': '#7cc8a0'}
RANKS = [(1, 'Village Rookie'), (3, 'Apprentice Modder'), (5, 'Professional Slacker'), (7, 'Pet Tamer'),
         (10, 'Bug Hunter'), (13, 'Code Alchemist'), (17, 'Cyber Creator'), (21, 'Legendary Crab King')]


def level_of(stats):
    xp = stats['total'] + 15 * stats['stars'] + 20 * stats['forks'] + 10 * stats['own'] + 3 * stats['active_days']
    lv = max(1, int(math.sqrt(xp / 12)))
    base, nxt = 12 * lv * lv, 12 * (lv + 1) ** 2
    rank = [r for l, r in RANKS if lv >= l][-1]
    return xp, lv, rank, (xp - base) / (nxt - base), nxt - xp


def icon(kind, d, cx, cy, s, p):
    ln = p['cink']
    ln2 = p['line'] if p['name'] == 'dark' else ln  # strokes drawn straight on the card
    if kind == 'star':
        return star_icon(d, cx, cy, s * .55, p['butter'], ln, 3)
    if kind == 'fork':
        return (scribble_line([(cx - s * .28, cy - s * .3), (cx - s * .28, cy - s * .05), (cx, cy + s * .12), (cx, cy + s * .32)], 2.2, ln2, 1, .2, 3)
                + scribble_line([(cx + s * .28, cy - s * .3), (cx + s * .28, cy - s * .05), (cx, cy + s * .12)], 2.2, ln2, 2, .2, 3)
                + ''.join(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(s * .13)}" fill="{p["sky"]}" stroke="{ln}" stroke-width="1.6"/>'
                          for x, y in ((cx - s * .28, cy - s * .32), (cx + s * .28, cy - s * .32), (cx, cy + s * .34))))
    if kind == 'box':
        return (crayon(d, rrect_pts(cx - s * .38, cy - s * .42, s * .76, s * .84, s * .08, 2), p['lav'], ln, 1.7, 4, .3, 3, (.6, -.4), hatch=None)
                + scribble_line([(cx - s * .2, cy - s * .42), (cx - s * .2, cy + s * .42)], 1.6, ln, 5, .2, 3))
    if kind == 'flame':
        pts = [(cx, cy - s * .5), (cx + s * .3, cy - s * .08), (cx + s * .34, cy + s * .2), (cx + s * .14, cy + s * .44), (cx - s * .14, cy + s * .44),
               (cx - s * .34, cy + s * .2), (cx - s * .26, cy - s * .12), (cx - s * .1, cy + s * .02)]
        return crayon(d, pts, p['rose'], ln, 1.7, 6, .3, 3, (.6, -.4), hatch=None) + \
            f'<path d="{smooth_d(wobble([(cx, cy + s * .02), (cx + s * .14, cy + s * .22), (cx, cy + s * .4), (cx - s * .14, cy + s * .22)], .2, 2, 9))}" fill="{p["butter"]}"/>'
    if kind == 'cal':
        return (crayon(d, rrect_pts(cx - s * .42, cy - s * .34, s * .84, s * .74, s * .1, 2), '#fffaf0', ln, 1.7, 7, .3, 3, (0, 0), hatch=None)
                + f'<path d="{poly_d(rrect_pts(cx - s * .42, cy - s * .34, s * .84, s * .2, s * .06, 2))}" fill="{p["clay"]}"/>'
                + ''.join(f'<circle cx="{fmt(cx + dx * s)}" cy="{fmt(cy + dy * s)}" r="{fmt(s * .05)}" fill="{ln}"/>'
                          for dx, dy in ((-.18, .05), (0, .05), (.18, .05), (-.18, .22), (0, .22))))
    if kind == 'bolt':
        pts = [(cx + s * .1, cy - s * .5), (cx - s * .3, cy + s * .06), (cx - s * .02, cy + s * .06), (cx - s * .12, cy + s * .5),
               (cx + s * .32, cy - s * .1), (cx + s * .04, cy - s * .1)]
        return crayon(d, pts, p['butter'], ln, 1.7, 8, .3, 3, (.6, -.4), hatch=None)
    return ''


def stats_card(pal, cfg, data):
    p = pal
    dark = p['name'] == 'dark'
    W, H = 1000, 340
    repos = data['repos']
    own = [r for r in repos.values() if not r['fork']]
    cst = ghdata.calendar_stats(data['calendar']['days'])
    st = {'total': data['calendar']['total'], 'stars': sum(r['stars'] for r in own), 'forks': sum(r['forks'] for r in own),
          'own': len(own), 'public': data['user']['public_repos'], **cst}
    xp, lv, rank, prog, need = level_of(st)
    d = Doc(W, H, pal, 'Adventurer Card', f'LV.{lv} {rank}; {st["stars"]} stars, {st["forks"]} forks, {st["public"]} public repos, {st["total"]} contributions this year')
    hatch_def(d)
    frame, clip, tapes = card(d, 10, 10, W - 26, H - 26, 24, seed=23, tapes=[(82, 20, 92, 24, -6, p['mint']), (930, 20, 80, 22, 7, p['pink'])])
    d.add(frame, f'<g clip-path="url(#{clip})">')
    css = []
    # --- left: adventurer card
    t, w, _ = d.text('Adventurer Card', 44, 64, 30, 'gs', p['text'])
    d.add(t)
    t, _, _ = d.text('profile stats', 44 + w + 14, 63, 16, 'gb', p['text2'])
    d.add(t)
    bx, by = 92, 146
    d.add(f'<g transform="translate({bx} {by})"><g class="badge">'
          + crayon(d, star_pts(0, 0, 50, 41, 12, -90), p['butter'], p['cink'], 2.4, 31, .7, 5, (1.2, -.8), hatchA=.14)
          + crayon(d, ell_pts(0, 0, 33, 33, 24), p['clay'], p['cink'], 2.2, 32, .6, 5, (1, -.7), hatchA=.16))
    t, _, _ = d.text('LV', 0, -9, 15, 'gs', '#fffaf0', anchor='middle')
    d.add(t)
    t, _, _ = d.text(str(lv), 0, 21, 32 if lv < 10 else 27, 'gs', '#fffaf0', anchor='middle')
    d.add(t, '</g></g>')
    css.append('.badge{animation:badge 6s ease-in-out infinite}'
               + kf('badge', [(0, 'transform:rotate(0)'), (8, 'transform:rotate(-10deg) scale(1.06)'), (16, 'transform:rotate(6deg)'),
                              (22, 'transform:rotate(0)'), (100, 'transform:rotate(0)')]))
    rsz = 26
    while measure(rank, rsz, 'gs') > 338 and rsz > 16:
        rsz -= 1
    t, _, _ = d.text(rank, 166, 134, rsz, 'gs', p['text'])
    d.add(t)
    bar_x, bar_y, bar_w, bar_h = 166, 148, 316, 22
    fillw = max(bar_h, bar_w * max(prog, .04))
    d.add(crayon(d, rrect_pts(bar_x, bar_y, bar_w, bar_h, 11, 5), p['bg2'], None, seed=33, hatch=None))
    d.add(f'<g transform="translate({bar_x} {bar_y})"><g class="xp">'
          + crayon(d, rrect_pts(0, 0, fillw, bar_h, 11, 5), p['clay'], None, seed=34, amp=.5, step=5, hatchA=.2) + '</g></g>')
    d.add(crayon(d, rrect_pts(bar_x, bar_y, bar_w, bar_h, 11, 5), None, p['line'] if dark else p['cink'], 2.2, 35, .6, 6))
    css.append('.xp{animation:xp 1.4s .4s cubic-bezier(.2,.8,.3,1) backwards}' + kf('xp', [(0, 'transform:scaleX(0)'), (100, 'transform:scaleX(1)')]))
    t, _, _ = d.text(f'XP {xp:,} · {need:,} to LV.{lv + 1}', 166, 194, 15, 'mix', p['text2'])
    d.add(t)
    items = [('star', 'Stars', st['stars']), ('fork', 'Forks', st['forks']), ('box', 'Repos', st['public']),
             ('flame', 'Contribs', st['total']), ('cal', 'Active days', st['active_days']), ('bolt', 'Streak', f"{st['longest_streak']} days")]
    for i, (kind, label, val) in enumerate(items):
        col, row = i % 2, i // 2
        x, y = 44 + col * 236, 236 + row * 36
        d.add(icon(kind, d, x + 11, y - 7, 22, p))
        t, _, _ = d.text(label, x + 30, y, 17, 'mix', p['text2'])
        d.add(t)
        t, _, _ = d.text(f'{val:,}' if isinstance(val, int) else val, x + 214, y + 1, 22, 'mixb', p['text'], anchor='end')
        d.add(t)
    d.add(scribble_line([(516, 54), (518, 180), (515, 300)], 2, p['dot'], 41, 1.2, 10))

    # --- right: language donut with Clawd sitting in the hole
    t, w, _ = d.text('Top Languages', 548, 64, 30, 'gs', p['text'])
    d.add(t)
    t, _, _ = d.text('by bytes', 548 + w + 14, 63, 16, 'gb', p['text2'])
    d.add(t)
    langs = sorted(data['languages'].items(), key=lambda kv: -kv[1])
    tot = sum(v for _, v in langs) or 1
    top = [(k, v / tot) for k, v in langs[:6]]
    rest = 1 - sum(v for _, v in top)
    if len(langs) > 6 and rest > .002:
        top = [(k, v / tot) for k, v in langs[:5]]
        top.append(('Other', 1 - sum(v for _, v in top)))
    cx, cy, R, wd = 660, 196, 76, 30
    cum = 0.0
    for i, (k, f_) in enumerate(top):
        col = LANG_COLORS.get(k, '#bdb3a6')
        d.add(f'<circle class="seg" style="animation-delay:{fmt(.3 + i * .15, 2)}s" cx="{cx}" cy="{cy}" r="{R}" fill="none" '
              f'stroke="{col}" stroke-width="{wd}" pathLength="100" stroke-dasharray="{fmt(f_ * 100, 2)} 100" '
              f'stroke-dashoffset="{fmt(-cum * 100, 2)}" transform="rotate(-90 {cx} {cy})"/>')
        cum += f_
    ring = smooth_d(ell_pts(cx, cy, R + wd / 2, R + wd / 2, 40)) + smooth_d(ell_pts(cx, cy, R - wd / 2, R - wd / 2, 32)[::-1])
    d.add(f'<path d="{ring}" fill="url(#hatch)" opacity=".14" fill-rule="evenodd"/>')
    seps = []
    cum = 0.0
    for k, f_ in top:
        a = -math.pi / 2 + cum * 2 * math.pi
        seps.append(scribble_line([(cx + math.cos(a) * (R - wd / 2), cy + math.sin(a) * (R - wd / 2)),
                                   (cx + math.cos(a) * (R + wd / 2), cy + math.sin(a) * (R + wd / 2))], 2, p['cink'], int(cum * 99), .3, 4))
        cum += f_
    ink = p['cink'] if not dark else p['line']
    d.add(f'<g class="sep">' + ''.join(seps) + crayon(d, ell_pts(cx, cy, R + wd / 2, R + wd / 2, 40), None, ink, 2.4, 42, .8, 7)
          + crayon(d, ell_pts(cx, cy, R - wd / 2, R - wd / 2, 32), None, ink, 2.2, 43, .6, 6) + '</g>')
    css.append('.seg{animation:seg 1s cubic-bezier(.3,.7,.3,1) backwards}' + kf('seg', [(0, 'stroke-dasharray:0 100'), (100, '')])
               + '.sep{animation:fade .5s 1.3s backwards}' + kf('fade', [(0, 'opacity:0'), (100, 'opacity:1')]))
    d.add(clawd(d, cx, cy + 25, 52, 'sc', seed=12, faces=('open', 'happy'), mouths=('smile', 'grin')))
    P = 7.0
    css += ['.sc-blink,.sc-armR,.sc-eyesO,.sc-eyesH,.sc-m1,.sc-m2,.sc-jump{animation-duration:7s;animation-iteration-count:infinite}'
            '.sc-blink{animation-name:scb}.sc-armR{animation-name:sca}.sc-eyesO{animation-name:sceo}.sc-eyesH{animation-name:sceh}'
            '.sc-m1{animation-name:scm1}.sc-m2{animation-name:scm2}.sc-jump{animation-name:scj}',
            timeline('scb', P, [(0, 'transform:scaleY(1)'), (2.3, 'transform:scaleY(1)'), (2.37, 'transform:scaleY(.1)'), (2.45, 'transform:scaleY(1)'), (P, 'transform:scaleY(1)')]),
            timeline('sca', P, [(0, 'transform:rotate(0)'), (4.0, 'transform:rotate(0)'), (4.2, 'transform:rotate(-70deg)'), (4.45, 'transform:rotate(-36deg)'),
                                (4.7, 'transform:rotate(-70deg)'), (4.95, 'transform:rotate(-36deg)'), (5.2, 'transform:rotate(0)'), (P, 'transform:rotate(0)')]),
            toggles('sceh', P, [(4.0, 5.4)]), toggles('sceo', P, [(0, 4.0), (5.4, P)]),
            toggles('scm2', P, [(4.0, 5.4)]), toggles('scm1', P, [(0, 4.0), (5.4, P)]),
            timeline('scj', P, [(0, 'transform:translateY(0)'), (4.0, 'transform:translateY(0)'), (4.15, 'transform:translateY(-6px)'),
                                (4.3, 'transform:translateY(0)'), (P, 'transform:translateY(0)')])]
    # legend
    ly = 116
    step_ = min(32, 190 / max(len(top), 1))
    for i, (k, f_) in enumerate(top):
        y = ly + i * step_
        col = LANG_COLORS.get(k, '#bdb3a6')
        d.add(crayon(d, ell_pts(790, y - 6, 8, 8, 14), col, p['cink'], 1.6, 50 + i, .4, 3, (.6, -.4), hatch=None))
        t, _, _ = d.text(k, 806, y, 18, 'mix', p['text'])
        d.add(t)
        t, _, _ = d.text(f'{f_ * 100:.1f}%', 952, y, 17, 'gb', p['text2'], anchor='end')
        d.add(t)
    d.add('</g>', tapes)
    d.style('\n'.join(css))
    return d


# ====================================================================== project cards
def project_icon(kind, d, cx, cy, p, accent):
    ln = p['cink']
    css = []
    if kind == 'clawd':
        svg = clawd(d, cx, cy + 27, 50, 'ic', seed=14, faces=('open', 'happy'), mouths=('smile', 'o'), hatch=None)
        P = 6.0
        css += ['.ic-blink,.ic-armR,.ic-armL,.ic-eyesO,.ic-eyesH,.ic-m1,.ic-m2,.ic-jump,.ic-legA,.ic-legB{animation-duration:6s;animation-iteration-count:infinite}'
                '.ic-blink{animation-name:icb}.ic-armR{animation-name:icr}.ic-eyesO{animation-name:iceo}.ic-eyesH{animation-name:iceh}'
                '.ic-m1{animation-name:icm1}.ic-m2{animation-name:icm2}.ic-legA{animation-name:icla}.ic-legB{animation-name:iclb}',
                timeline('icb', P, [(0, 'transform:scaleY(1)'), (1.6, 'transform:scaleY(1)'), (1.67, 'transform:scaleY(.1)'), (1.75, 'transform:scaleY(1)'), (P, 'transform:scaleY(1)')]),
                timeline('icr', P, [(0, 'transform:rotate(0)'), (3, 'transform:rotate(0)'), (3.2, 'transform:rotate(-70deg)'), (3.45, 'transform:rotate(-36deg)'),
                                    (3.7, 'transform:rotate(-70deg)'), (3.95, 'transform:rotate(-36deg)'), (4.2, 'transform:rotate(0)'), (P, 'transform:rotate(0)')]),
                toggles('iceh', P, [(3.0, 4.4)]), toggles('iceo', P, [(0, 3.0), (4.4, P)]),
                toggles('icm2', P, [(3.1, 3.4), (3.6, 3.9)]), toggles('icm1', P, _invert([(3.1, 3.4), (3.6, 3.9)], P)),
                timeline('icla', P, [(0, 'transform:translateY(0)')] + [(.3 + k * .3, f'transform:translateY({-2 if k % 2 == 0 else 0}px)') for k in range(8)] + [(P, 'transform:translateY(0)')]),
                timeline('iclb', P, [(0, 'transform:translateY(0)')] + [(.3 + k * .3, f'transform:translateY({0 if k % 2 == 0 else -2}px)') for k in range(8)] + [(P, 'transform:translateY(0)')])]
        return svg, css
    if kind == 'tv':
        ant = (scribble_line([(-3, -20), (-14, -40)], 2.4, ln, 1, .3, 3) + scribble_line([(3, -20), (15, -42)], 2.4, ln, 2, .3, 3)
               + f'<circle cx="-14" cy="-41" r="3.2" fill="{p["rose"]}" stroke="{ln}" stroke-width="1.5"/>'
               + f'<circle cx="15" cy="-43" r="3.2" fill="{p["butter"]}" stroke="{ln}" stroke-width="1.5"/>')
        body = crayon(d, rrect_pts(-33, -21, 66, 46, 10, 4), accent, ln, 2.3, 61, .6, 5, (1, -.7), hatchA=.18)
        screen = crayon(d, rrect_pts(-26, -14, 42, 32, 7, 4), p['bg'], ln, 2, 62, .5, 4, (0, 0), hatch=None)
        eye = (f'<ellipse cx="-5" cy="2" rx="12" ry="9" fill="#fff" stroke="{ln}" stroke-width="1.6"/>'
               f'<g class="pup"><circle cx="-5" cy="2" r="4.6" fill="{p["navy"]}"/><circle cx="-6.5" cy=".5" r="1.4" fill="#fff"/></g>')
        rec = f'<circle class="rec" cx="-20" cy="-8" r="2.6" fill="{p["red"]}"/>'
        knobs = ''.join(f'<circle cx="24" cy="{y}" r="3.2" fill="{p["bg"]}" stroke="{ln}" stroke-width="1.5"/>' for y in (-6, 6))
        legs = scribble_line([(-18, 25), (-22, 32)], 2.4, ln, 3, .2, 3) + scribble_line([(18, 25), (22, 32)], 2.4, ln, 4, .2, 3)
        svg = (f'<g transform="translate({cx} {cy + 4})"><g transform="translate(0 -20)"><g class="ant">'
               f'<g transform="translate(0 20)">{ant}</g></g></g>{legs}{body}{screen}{eye}{rec}{knobs}</g>')
        css += ['.ant{animation:ant 1.8s ease-in-out infinite alternate}' + kf('ant', [(0, 'transform:rotate(-9deg)'), (100, 'transform:rotate(9deg)')]),
                '.pup{animation:pup 4s ease-in-out infinite}' + kf('pup', [(0, 'transform:translateX(-4px)'), (40, 'transform:translateX(-4px)'),
                                                                          (50, 'transform:translateX(4px)'), (90, 'transform:translateX(4px)'), (100, 'transform:translateX(-4px)')]),
                '.rec{animation:rec 1.2s steps(1) infinite}' + kf('rec', [(0, 'opacity:1'), (50, 'opacity:.15'), (100, 'opacity:.15')])]
        return svg, css
    if kind == 'mob':
        r = random.Random(3)
        head = crayon(d, rrect_pts(-25, -27, 50, 50, 4, 2), accent, ln, 2.3, 71, .5, 5, (1, -.7), hatch=None)
        pix = ''.join(f'<rect x="{-25 + 6.25 * i}" y="{-27 + 6.25 * j}" width="6.25" height="6.25" fill="#3d7d3a" opacity="{r.uniform(.12, .3):.2f}"/>'
                      for i in range(8) for j in range(8) if r.random() < .28)
        eyes = ''.join(f'<rect x="{x}" y="-12" width="10" height="9" fill="#fff" stroke="{ln}" stroke-width="1.2"/>' for x in (-15, 5))
        pup = f'<g class="mp"><rect x="-11" y="-10" width="5" height="6" fill="{ln}"/><rect x="9" y="-10" width="5" height="6" fill="{ln}"/></g>'
        mouth = scribble_line([(-8, 9), (0, 12), (8, 9)], 2.2, ln, 5, .2, 3)
        bub = (crayon(d, rrect_pts(14, -52, 32, 20, 9, 4) + [], '#fffdf7', ln, 1.8, 72, .4, 4, (0, 0), hatch=None)
               + ''.join(f'<circle class="dot d{k}" cx="{22 + k * 8}" cy="-42" r="2.4" fill="{ln}"/>' for k in range(3)))
        svg = (f'<g transform="translate({cx} {cy + 6})"><g class="mh">{head}{pix}{eyes}{pup}{mouth}</g>'
               f'<g transform="translate(0 2)">{bub}</g>' + sparkle(-30, -36, 7, p['butter'], ln, 1.2) + '</g>')
        css += ['.mh{animation:mh 3s ease-in-out infinite}' + kf('mh', [(0, 'transform:rotate(-3deg)'), (50, 'transform:rotate(3deg)'), (100, 'transform:rotate(-3deg)')]),
                '.mp{animation:mp 4s steps(1) infinite}' + kf('mp', [(0, 'transform:translateX(0)'), (35, 'transform:translateX(-3px)'), (70, 'transform:translateX(3px)'), (100, 'transform:translateX(0)')]),
                '.dot{animation:dot 1.2s ease-in-out infinite}.d1{animation-delay:.2s}.d2{animation-delay:.4s}'
                + kf('dot', [(0, 'transform:translateY(0)'), (30, 'transform:translateY(-3px)'), (60, 'transform:translateY(0)'), (100, 'transform:translateY(0)')])]
        return svg, css
    if kind == 'shield':
        r = random.Random(9)
        pts = [(0, -32), (14, -26), (27, -24), (26, 0), (18, 18), (0, 32), (-18, 18), (-26, 0), (-27, -24), (-14, -26)]
        sh = crayon(d, pts, accent, ln, 2.4, 81, .6, 5, (1.1, -.8), hatchA=.18)
        check = scribble_line([(-11, 0), (-3, 9), (13, -10)], 4, ln, 82, .3, 3)
        dots = []
        for k in range(22):
            a, rr = r.uniform(0, 2 * math.pi), r.uniform(36, 48)
            dots.append(f'<circle class="nz" style="animation-delay:-{r.uniform(0, 1.6):.2f}s" cx="{fmt(math.cos(a) * rr)}" '
                        f'cy="{fmt(math.sin(a) * rr * .9)}" r="{fmt(r.uniform(1.2, 2.4))}" fill="{p["text2"]}"/>')
        svg = f'<g transform="translate({cx} {cy})">{"".join(dots)}<g class="sh">{sh}{check}</g></g>'
        css += ['.nz{animation:nz 1.6s steps(1) infinite}' + kf('nz', [(0, 'opacity:.9'), (25, 'opacity:.1'), (50, 'opacity:.6'), (75, 'opacity:0'), (100, 'opacity:.9')]),
                '.sh{animation:shp 3s ease-in-out infinite}' + kf('shp', [(0, 'transform:scale(1)'), (50, 'transform:scale(1.06)'), (100, 'transform:scale(1)')])]
        return svg, css
    if kind == 'pumpkin':
        org = '#f39a3d'
        lobes = (crayon(d, ell_pts(-13, 3, 17, 22, 22), org, ln, 2.2, 91, .5, 4, (.8, -.6), hatchA=.16)
                 + crayon(d, ell_pts(13, 3, 17, 22, 22), org, ln, 2.2, 92, .5, 4, (.8, -.6), hatchA=.16)
                 + crayon(d, ell_pts(0, 3, 13, 24, 22), '#f7a94e', ln, 2.2, 93, .5, 4, (.8, -.6), hatchA=.16))
        stem = crayon(d, [(-3, -20), (3, -20), (5, -30), (-1, -31)], '#6a9c4a', ln, 2, 94, .3, 3, (0, 0), hatch=None)
        leaf = crayon(d, [(4, -27), (14, -34), (22, -30), (12, -24)], p['green'], ln, 1.8, 95, .3, 3, (0, 0), hatch=None)
        face = (f'<circle cx="-7" cy="0" r="2.6" fill="{ln}"/><circle cx="7" cy="0" r="2.6" fill="{ln}"/>'
                + scribble_line([(-6, 12), (0, 9), (6, 12)], 2, ln, 96, .2, 3)
                + f'<g class="tear"><path d="M9.5 4 q2.6 4 0 6 q-2.6-2 0-6Z" fill="{p["sky"]}" stroke="{ln}" stroke-width="1"/></g>')
        svg = f'<g transform="translate({cx} {cy + 26})"><g class="pk"><g transform="translate(0 -26)">{stem}{leaf}{lobes}{face}</g></g></g>'
        css += ['.pk{animation:pk 2.4s ease-in-out infinite}' + kf('pk', [(0, 'transform:scale(1,1)'), (12, 'transform:scale(1.08,.9)'), (28, 'transform:scale(.95,1.06) translateY(-8px)'),
                                                                           (44, 'transform:scale(1,1)'), (100, 'transform:scale(1,1)')]),
                '.tear{animation:tear 2.4s ease-in infinite}' + kf('tear', [(0, 'transform:translateY(0);opacity:0'), (40, 'transform:translateY(0);opacity:1'), (90, 'transform:translateY(12px);opacity:0'), (100, 'opacity:0')])]
        return svg, css
    if kind == 'whale':
        body = [(32, 2), (28, -12), (16, -20), (0, -22), (-16, -18), (-28, -8), (-34, 2), (-30, 12), (-14, 19), (6, 20), (24, 15)]
        tail = [(-30, 0), (-44, -16), (-46, -6), (-40, 2), (-46, 10), (-44, 16)]
        wb = crayon(d, tail, accent, ln, 2.2, 101, .4, 4, (.8, -.6), hatch=None) + crayon(d, body, accent, ln, 2.4, 102, .6, 5, (1, -.7), hatchA=.16)
        belly = f'<path d="{smooth_d(wobble([(-22, 12), (0, 18), (22, 13), (2, 10)], .3, 3, 103))}" fill="#fff" opacity=".55"/>'
        face = (f'<circle cx="16" cy="-4" r="2.8" fill="{ln}"/><circle cx="15.2" cy="-5" r=".9" fill="#fff"/>'
                f'<ellipse cx="20" cy="4" rx="4" ry="2.2" fill="{p["pink"]}" opacity=".8"/>'
                + scribble_line([(22, 8), (27, 9), (31, 6)], 1.8, ln, 104, .2, 3))
        spout = (scribble_line([(2, -22), (-2, -34), (-8, -38)], 2, p['sky'], 105, .2, 3)
                 + scribble_line([(2, -22), (6, -34), (12, -38)], 2, p['sky'], 106, .2, 3))
        hrt = f'<g transform="translate(36 -10)"><g class="kh">{heart(0, 0, 8, p["rose"], ln, 1.3, 107)}</g></g>'
        svg = f'<g transform="translate({cx + 3} {cy + 4})"><g class="wh">{spout}{wb}{belly}{face}</g>{hrt}</g>'
        css += ['.wh{animation:wh 3s ease-in-out infinite}' + kf('wh', [(0, 'transform:translateY(0) rotate(0)'), (50, 'transform:translateY(-4px) rotate(-4deg)'), (100, 'transform:translateY(0) rotate(0)')]),
                '.kh{animation:kh 3s ease-out infinite}' + kf('kh', [(0, 'transform:translate(0,0) scale(.2);opacity:0'), (40, 'transform:translate(0,0) scale(.2);opacity:0'),
                                                                     (55, 'transform:translate(4px,-6px) scale(1.1);opacity:1'), (95, 'transform:translate(10px,-30px) scale(.8);opacity:0'),
                                                                     (100, 'opacity:0')])]
        return svg, css
    if kind == 'gauge':
        ln2 = p['line'] if p['name'] == 'dark' else ln  # bare strokes on the badge need the themed line colour
        R = 30
        # 180-degree dial: t in [0,1] maps to the upper semicircle, left -> top -> right
        dp = lambda t, rr: (math.cos(math.radians(180 + 180 * t)) * rr, math.sin(math.radians(180 + 180 * t)) * rr)
        dial = scribble_line([dp(i / 48, R) for i in range(49)], 3.2, ln2, 120, .4, 5)
        redzone = scribble_line([dp(.76 + .24 * i / 16, R) for i in range(17)], 4.4, p['red'], 121, .35, 4)
        ticks = ''.join(scribble_line([dp(t, R - 2), dp(t, R - 9)], 2.2, p['text2'], 122 + int(t * 9), .2, 3)
                        for t in (0.0, .25, .5, .75, 1.0))
        hub = crayon(d, ell_pts(0, 0, 7, 7, 14), accent, ln2, 2, 125, .4, 4, (.5, -.4), hatch=None)
        needle = (scribble_line([(0, 7), (0, -25)], 3.4, p['red'], 126, .25, 4)
                  + f'<circle cx="0" cy="-25" r="2.6" fill="{p["red"]}"/>')
        spark = f'<g transform="translate(22 -17)"><g class="gmx">' + sparkle(0, 0, 7, p['butter'], ln2, 1.3) + '</g></g>'
        svg = (f'<g transform="translate({cx} {cy + 13})">{dial}{redzone}{ticks}'
               f'<g class="gnd">{needle}</g>{hub}{spark}</g>')
        css += ['.gnd{transform-origin:0px 0px;animation:gnd 3s cubic-bezier(.5,.1,.4,1) infinite}'
                + kf('gnd', [(0, 'transform:rotate(-86deg)'), (7, 'transform:rotate(-86deg)'), (42, 'transform:rotate(58deg)'),
                             (50, 'transform:rotate(82deg)'), (56, 'transform:rotate(68deg)'), (62, 'transform:rotate(84deg)'),
                             (68, 'transform:rotate(72deg)'), (74, 'transform:rotate(82deg)'), (82, 'transform:rotate(48deg)'),
                             (90, 'transform:rotate(-86deg)'), (100, 'transform:rotate(-86deg)')]),
                '.gmx{transform-origin:0px 0px;animation:gmx 3s ease-in-out infinite}'
                + kf('gmx', [(0, 'opacity:0;transform:scale(0)'), (48, 'opacity:0;transform:scale(0)'),
                             (56, 'opacity:1;transform:scale(1)'), (74, 'opacity:1;transform:scale(1.1)'),
                             (84, 'opacity:0;transform:scale(.4)'), (100, 'opacity:0;transform:scale(0)')])]
        return svg, css
    return '', css


def project_card(pal, cfg, proj, repo, idx):
    p = pal
    dark = p['name'] == 'dark'
    accent = p.get(proj.get('color', 'clay'), p['clay'])
    W, H = 500, 200
    d = Doc(W, H, pal, proj['title'], proj['desc'])
    hatch_def(d)
    frame, clip, tapes = card(d, 8, 14, 482, 170, 20, seed=60 + idx * 7,
                              tapes=[(58, 18, 64, 20, -8 + idx * 3, accent)])
    d.add(frame, f'<g clip-path="url(#{clip})">')
    css = []
    icx, icy = 76, 104
    d.add(crayon(d, ell_pts(icx, icy, 47, 47, 30), accent, None, seed=70 + idx, amp=1.2, step=6, fill_op=.2 if not dark else .16, hatch=None))
    d.add(crayon(d, ell_pts(icx, icy, 47, 47, 30), None, accent, 2.2, 71 + idx, 1.2, 6))
    svg, c = project_icon(proj['icon'], d, icx, icy, p, accent)
    d.add(svg)
    css += c
    tx = 140
    title = proj['title']
    ts = 26
    while measure(title, ts, 'mixb') > 334 and ts > 16:
        ts -= 1
    t, _, _ = d.text(title, tx, 58, ts, 'mixb', p['text'])
    d.add(t)
    t, _, _ = d.text(proj.get('source') or f"{cfg['user']}/{proj['repo']}", tx, 79, 14, 'gb', p['text2'])
    d.add(t)
    for i, line in enumerate(wrap(proj['desc'], 16, 330, 'mix', 3)):
        t, _, _ = d.text(line, tx, 105 + i * 21, 16, 'mix', p['text'])
        d.add(t)
    # footer: language, stars, forks, link
    fy = 172
    x = tx
    lang = (repo or {}).get('language') or proj.get('language')
    if lang:
        d.add(crayon(d, ell_pts(x + 6, fy - 5, 6, 6, 12), LANG_COLORS.get(lang, '#bdb3a6'), p['cink'], 1.3, 5, .3, 3, (.4, -.3), hatch=None))
        t, w, _ = d.text(lang, x + 17, fy, 14, 'gb', p['text2'])
        d.add(t)
        x += 17 + w + 16
    for kind, val in (('star', (repo or {}).get('stars', 0)), ('fork', (repo or {}).get('forks', 0))):
        d.add(icon(kind, d, x + 7, fy - 5, 15, p))
        t, w, _ = d.text(str(val), x + 18, fy, 14, 'gb', p['text2'])
        d.add(t)
        x += 18 + w + 14
    if proj.get('link'):
        lab = proj.get('link_label', 'Website')
        lw_ = measure(lab, 14, 'gb')
        pw = lw_ + 34
        px0 = 474 - pw
        d.add(crayon(d, rrect_pts(px0, fy - 18, pw, 25, 12.5, 5), accent, accent, 1.6, 9 + idx, .4, 5, (.6, -.4), hatch=None, fill_op=.18))
        t, _, _ = d.text(lab, px0 + 11, fy, 14, 'gb', p['text'])
        d.add(t, arrow_ne(px0 + lw_ + 15, fy - 3.5, 7, p['text'], 1.7))
    d.add('</g>', tapes)
    d.style('\n'.join(css))
    return d


# ====================================================================== footer
def footer(pal, cfg):
    p = pal
    W, H = 1000, 170
    d = Doc(W, H, pal, 'Thanks for stopping by', 'Thanks for stopping by — Clawd dozes in a nightcap')
    hatch_def(d)
    frame, clip, tapes = card(d, 10, 10, W - 26, H - 26, 24, seed=83, tapes=[(70, 20, 84, 22, -6, p['lav'])])
    d.add(frame, f'<g clip-path="url(#{clip})">')
    t, w, _ = d.text('Thanks for stopping by!', 48, 80, 30, 'gs', p['text'])
    d.add(t, f'<g transform="translate({fmt(48 + w + 24)} 70)"><g class="beat">' + heart(0, 0, 13, p['rose'], p['cink'], 1.8, 3) + '</g></g>')
    t, _, _ = d.text('Every drawing here is generated in code · data refreshed daily by GitHub Actions', 48, 118, 17, 'mix', p['text2'])
    d.add(t)
    gy = 138
    d.add(scribble_line([(720, gy), (820, gy - 1), (900, gy + 1), (990, gy)], 2.4, p['line'], 7, .7, 8))
    gcol = '#6fae5b' if p['name'] == 'light' else '#7fc58f'
    for i, x in enumerate([742, 790, 952, 975]):
        d.add(grass(x, gy, gcol, 140 + i))
    s = 84
    cx = 872
    # nightcap (clawd.js "night" hat), drawn in the bob layer so it breathes with the body
    top = BODY_TOP * s
    a = .25
    def rot(pt):
        x, y = pt
        return (.05 * s + x * s * math.cos(a) - y * s * math.sin(a), top + .02 * s + x * s * math.sin(a) + y * s * math.cos(a))
    cap = [rot(q) for q in [(-.21, 0), (.21, 0), (.12, -.2), (.33, -.37), (0, -.25)]]
    pom = rot((.34, -.38))
    hat = (crayon(d, cap, p['sky'], p['cink'], 2, 8, .5, 4, (.8, -.6), hatchA=.18)
           + crayon(d, ell_pts(pom[0], pom[1], s * .05, s * .05, 12), '#fffaf0', p['cink'], 1.6, 9, .3, 3, (0, 0), hatch=None))
    d.add(clawd(d, cx, gy, s, 'zz', seed=15, faces=('closed',), mouths=('w',), extra_front=hat))
    for i in range(3):
        d.add(f'<g transform="translate({cx + 30} {gy - s * .95})"><g class="z" style="animation-delay:{fmt(i * 1.1, 2)}s">'
              + zzz_glyph(d, 9 + i * 1.5, p['lav'], p['cink'] if p['name'] == 'light' else '#e9e1ff') + '</g></g>')
    css = ['.zz-bob{animation:breathe 3.3s ease-in-out infinite}' + kf('breathe', [(0, 'transform:scale(1,1)'), (50, 'transform:scale(1.025,.965)'), (100, 'transform:scale(1,1)')]),
           '.z{opacity:0;animation:z 3.3s ease-out infinite}' + kf('z', [(0, 'transform:translate(0,0) scale(.4);opacity:0'), (15, 'opacity:1'),
                                                                         (100, 'transform:translate(26px,-46px) scale(1.15);opacity:0')]),
           '.beat{animation:beat 1.6s ease-in-out infinite}' + kf('beat', [(0, 'transform:scale(1)'), (14, 'transform:scale(1.25)'), (28, 'transform:scale(1)'),
                                                                          (42, 'transform:scale(1.18)'), (60, 'transform:scale(1)'), (100, 'transform:scale(1)')])]
    d.add('</g>', tapes)
    d.style('\n'.join(css))
    return d


# ====================================================================== README projects block
def readme_projects(cfg):
    rows = []
    projs = cfg['projects']
    for i in range(0, len(projs), 2):
        cells = []
        for proj in projs[i:i + 2]:
            slug = proj['repo']
            href = proj.get('source') or f'{cfg["user"]}/{slug}'
            cells.append(f'<a href="https://github.com/{href}"><picture>'
                         f'<source media="(prefers-color-scheme: dark)" srcset="assets/project-{slug}-dark.svg">'
                         f'<img alt="{proj["title"]}" src="assets/project-{slug}-light.svg" width="49%"></picture></a>')
        rows.append('\n'.join(cells))
    more = ' · '.join(f'<a href="https://github.com/{cfg["user"]}/{r}">{t}</a>' for r, t in cfg.get('more', []))
    block = '<p align="center">\n' + '\n<br>\n'.join(rows) + '\n</p>\n'
    if more:
        block += f'\n<p align="center"><sub>Also: {more}</sub></p>\n'
    return block


def write(doc, name):
    path = os.path.join(ASSETS, f'{name}-{doc.pal["name"]}.svg')
    svg = doc.render()
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if svg != old:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(svg)
    return len(svg)


def main():
    offline = '--offline' in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith('--')]
    with open(os.path.join(ROOT, 'profile.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    extras = [p['source'] for p in cfg['projects'] if p.get('source')]
    data = ghdata.load(cfg['user'], offline, extras)
    os.makedirs(ASSETS, exist_ok=True)
    sizes = {}
    for pal in PALETTES:
        if not only or 'hero' in only:
            sizes[f'hero-{pal["name"]}'] = write(hero(pal, cfg), 'hero')
        if not only or 'contrib' in only:
            sizes[f'contrib-{pal["name"]}'] = write(contrib(pal, cfg, data), 'contrib')
        if not only or 'stats' in only:
            sizes[f'stats-{pal["name"]}'] = write(stats_card(pal, cfg, data), 'stats')
        if not only or 'projects' in only:
            for i, proj in enumerate(cfg['projects']):
                sizes[f'project-{proj["repo"]}-{pal["name"]}'] = write(
                    project_card(pal, cfg, proj, data['repos'].get(proj.get('source') or proj['repo']), i), f'project-{proj["repo"]}')
        if not only or 'footer' in only:
            sizes[f'footer-{pal["name"]}'] = write(footer(pal, cfg), 'footer')
    readme = os.path.join(ROOT, 'README.md')
    if os.path.exists(readme):
        txt = open(readme, encoding='utf-8').read()
        new = re.sub(r'(<!-- projects:start -->\n).*?(<!-- projects:end -->)',
                     lambda m: m.group(1) + readme_projects(cfg) + m.group(2), txt, flags=re.S)
        if new != txt:
            with open(readme, 'w', encoding='utf-8') as f:
                f.write(new)
    for k, v in sizes.items():
        print(f'{k:40s} {v / 1024:7.1f} KB')


if __name__ == '__main__':
    main()
