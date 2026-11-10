"""Clawd, the clay-orange crayon crab — proportions follow clawd.js from Carlown/clawd-pet.

Geometry is in body-width units (ground point between the feet = 0,0, y up is negative),
drawn as nested <g> layers so scenes can animate each part with CSS:

  .{p}-shadow  .{p}-jump > .{p}-bob > (.{p}-legA/.{p}-legB, .{p}-armL/.{p}-armR, body,
  .{p}-face > .{p}-eyesO(.{p}-blink) / .{p}-eyesH / .{p}-eyesC, blush, .{p}-m1 / .{p}-m2)

Every animated group has no transform attribute and its pivot at its local origin.
"""
from kit import crayon, ell_pts, fmt, rrect_pts, scribble_line, smooth_d, wobble

LEG_H, BODY_H = .2, .74
BODY_TOP = -(LEG_H + BODY_H)
LEG_X = [-.38, -.25, .24, .37]
ARM_TOP = BODY_TOP + BODY_H * .5
ARM_H, ARM_W = BODY_H * .27, .17
EYE_Y, EX, EYE_W, EYE_H = BODY_TOP + BODY_H * .40, .3, .072, .19
MOUTH_Y = EYE_Y + EYE_H * .56


def clawd(doc, x, y, s, p='cl', seed=11, faces=('open',), mouths=('smile',), hatch='hatch',
          color=None, shadow=True, extra_front=''):
    pal = doc.pal
    ink = pal['cink']
    col = color or pal['clay']
    lw = max(1.3, s * .024)
    amp = max(.35, s * .0065)
    step = max(2.5, s * .04)
    off = (s * .009, -s * .0065)
    S = lambda v: v * s

    def shape(pts, fill, sd, **kw):
        return crayon(doc, [(S(a), S(b)) for a, b in pts], fill, ink, lw, seed + sd, amp, step, off,
                      hatch=hatch if s > 60 else None, hatchA=.2, **kw)

    def rect(x0, y0, w, h, r=0.0, n=3):
        return rrect_pts(x0, y0, w, h, r, n) if r else [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]

    out = [f'<g transform="translate({fmt(x)} {fmt(y)})">']
    if shadow:
        out.append(f'<g class="{p}-shadow"><ellipse cx="0" cy="{fmt(S(.01))}" rx="{fmt(S(.6))}" '
                   f'ry="{fmt(S(.055))}" fill="{pal["shadow"]}" opacity="{.2 if pal["name"] == "light" else .45}"/></g>')
    out.append(f'<g class="{p}-jump"><g class="{p}-bob">')

    body_parts = []
    # legs (pairs 0,2 and 1,3 step in opposite phase)
    legs = {0: [], 1: []}
    for i, lx in enumerate(LEG_X):
        w = .078
        legs[i % 2].append(shape(rect(lx - w / 2, -LEG_H - .03, w, LEG_H + .03), col, i * 3))
    body_parts.append(f'<g class="{p}-legA">{"".join(legs[0])}</g><g class="{p}-legB">{"".join(legs[1])}</g>')
    # arms, pivot at the shoulder
    for side, name in ((-1, 'armL'), (1, 'armR')):
        x0 = -.04 if side > 0 else -ARM_W
        arm = shape(rect(x0, -ARM_H / 2, ARM_W + .04, ARM_H), col, 20 + side)
        body_parts.append(f'<g transform="translate({fmt(S(side * .5))} {fmt(S(ARM_TOP + ARM_H / 2))})">'
                          f'<g class="{p}-{name}">{arm}</g></g>')
    # body + soft shading + highlight
    body_parts.append(shape(rect(-.5, BODY_TOP, 1, BODY_H, .045, 3), col, 40))
    sh_pts = [(S(a), S(b)) for a, b in rect(-.46, BODY_TOP + BODY_H * .74, .92, BODY_H * .22)]
    body_parts.append(f'<path d="{smooth_d(wobble(sh_pts, amp * 1.2, step, seed + 41))}" fill="{pal["clayD"]}" opacity=".2"/>')
    hi_pts = [(S(a), S(b)) for a, b in rect(-.44, BODY_TOP + BODY_H * .06, .5, BODY_H * .1)]
    body_parts.append(f'<path d="{smooth_d(wobble(hi_pts, amp, step, seed + 42))}" fill="#ffffff" opacity=".25"/>')

    # face
    face = [f'<g class="{p}-face">']
    for fname in faces:
        vis = '' if fname == faces[0] else ' opacity="0"'
        if fname in ('open', 'wide'):
            k = 1.25 if fname == 'wide' else 1
            ew, eh = EYE_W * k, EYE_H * k
            eyes = []
            for side in (-1, 1):
                cx, cy = side * EX, EYE_Y
                e = rrect_pts(S(-ew / 2), S(-eh / 2), S(ew), S(eh), S(ew * .45), 4)
                hl = (f'<circle cx="{fmt(S(-ew * .12))}" cy="{fmt(S(-eh * .22))}" r="{fmt(S(ew * .2), 2)}" '
                      f'fill="#fff" opacity=".95"/>')
                eyes.append(f'<g transform="translate({fmt(S(cx))} {fmt(S(cy))})"><g class="{p}-blink">'
                            f'<path d="{smooth_d(wobble(e, amp * .5, step * .6, seed + 50 + side))}" fill="{ink}"/>{hl}</g></g>')
            face.append(f'<g class="{p}-eyesO"{vis}>{"".join(eyes)}</g>')
        elif fname == 'happy':
            arcs = ''.join(scribble_line([(S(side * EX - .065), S(EYE_Y + .035)), (S(side * EX), S(EYE_Y - .05)),
                                          (S(side * EX + .065), S(EYE_Y + .035))], lw * 1.4, ink, seed + side, amp * .5, step * .5)
                           for side in (-1, 1))
            face.append(f'<g class="{p}-eyesH"{vis}>{arcs}</g>')
        elif fname == 'closed':
            arcs = ''.join(scribble_line([(S(side * EX - .065), S(EYE_Y)), (S(side * EX), S(EYE_Y + .04)),
                                          (S(side * EX + .065), S(EYE_Y))], lw * 1.3, ink, seed + side, amp * .5, step * .5)
                           for side in (-1, 1))
            face.append(f'<g class="{p}-eyesC"{vis}>{arcs}</g>')
    for side in (-1, 1):
        bl = ell_pts(S(side * (EX + .085)), S(EYE_Y + EYE_H * .64), S(.075), S(.036), 16)
        face.append(f'<path d="{smooth_d(wobble(bl, amp * .5, step * .6, seed + 60 + side))}" fill="{pal["pink"]}" opacity=".6"/>')
    for i, m in enumerate(mouths):
        vis = '' if i == 0 else ' opacity="0"'
        my = MOUTH_Y
        if m == 'smile':
            g = scribble_line([(S(-.05), S(my)), (S(0), S(my + .04)), (S(.05), S(my))], lw, ink, seed + 71, amp * .4, step * .4)
        elif m == 'w':
            g = scribble_line([(S(-.06), S(my)), (S(-.03), S(my + .032)), (S(0), S(my + .006)), (S(.03), S(my + .032)),
                               (S(.06), S(my))], lw * .95, ink, seed + 72, amp * .4, step * .4)
        elif m == 'o':
            g = crayon(doc, ell_pts(0, S(my + .03), S(.042), S(.042), 16), pal['rose'], ink, lw * .8, seed + 70,
                       amp * .4, step * .5, (0, 0), hatch=None)
        elif m == 'grin':
            g = crayon(doc, [(S(a), S(b)) for a, b in [(-.07, my - .005), (.07, my - .005), (.045, my + .05), (0, my + .065), (-.045, my + .05)]],
                       pal['rose'], ink, lw * .85, seed + 74, amp * .4, step * .5, (0, 0), hatch=None)
        else:
            g = ''
        face.append(f'<g class="{p}-m{i + 1}"{vis}>{g}</g>')
    face.append('</g>')
    body_parts.append(''.join(face))
    body_parts.append(extra_front)
    out.append(''.join(body_parts))
    out.append('</g></g></g>')
    return ''.join(out)


def zzz_glyph(doc, s, color, line):
    """A small hand-drawn 'z'."""
    pts = [(-s * .5, -s * .5), (s * .5, -s * .5), (-s * .5, s * .5), (s * .5, s * .5)]
    return (scribble_line(pts, s * .42, line, 3, s * .03, s * .2) +
            scribble_line(pts, s * .22, color, 4, s * .03, s * .2))
