"""Genera la versión 2D (plenos de color, sin volumen) del logo FDL como SVG.

Usa la misma geometría que el modelo 3D (logo-fld.html): cubo de 10 unidades,
trazo 1.5, separación 0.9, F con brazo medio al 80 %, L con base al 75 %,
D al 88 % + 2.5 % de compensación óptica. Las letras se proyectan en isométrico.

Uso: python3 logo_2d.py  -> escribe logo-fld-2d-{color,mono,degradado}.svg
                            y logo-fld-extruido-{plenos,degradado}.svg
"""
import math
import os

S, T, GAP = 10.0, 1.5, 0.9

PALETAS = {
    # cada letra un pleno: F (cara de arriba), D (izquierda), L (derecha)
    "color": {"F": "#5B4BD8", "D": "#7032C8", "L": "#4A1F96"},
    "mono": {"F": "#6C32C8", "D": "#6C32C8", "L": "#6C32C8"},
    # un solo degradado para todo el logo (mismos colores que la versión 3D)
    "degradado": {"F": "url(#grad)", "D": "url(#grad)", "L": "url(#grad)"},
}

DEGRADADO = [(0.00, "#3A86E0"), (0.22, "#6A44DA"), (0.50, "#7C34D0"), (1.00, "#8526BE")]


def iso(p):
    x, y, z = p
    return ((x - z) / math.sqrt(2), -(-x + 2 * y - z) / math.sqrt(6))


def f_shape():
    arm_top = S - GAP
    arm_mid = GAP + 0.80 * (arm_top - GAP)
    mid = 0.42 * S
    pts = [(GAP, GAP), (arm_top, GAP), (arm_top, GAP + T), (GAP + T, GAP + T),
           (GAP + T, mid), (arm_mid, mid), (arm_mid, mid + T), (GAP + T, mid + T),
           (GAP + T, S - GAP), (GAP, S - GAP)]
    return [[(x, S, y) for x, y in pts]]  # cara de arriba: x = u, z = v


def l_shape():
    foot = GAP + 0.75 * (S - 2 * GAP)
    pts = [(GAP, GAP), (foot, GAP), (foot, GAP + T), (GAP + T, GAP + T),
           (GAP + T, S - GAP), (GAP, S - GAP)]
    return [[(S, y, S - w) for w, y in pts]]  # cara derecha: z = S - w


def d_outline(x0, y0, x1, y1, r, n=48):
    pts = [(x0, y0)]
    cx = x1 - r
    for i in range(n + 1):  # arco inferior: de abajo hacia la derecha
        a = -math.pi / 2 + (math.pi / 2) * i / n
        pts.append((cx + r * math.cos(a), y0 + r + r * math.sin(a)))
    for i in range(n + 1):  # arco superior
        a = (math.pi / 2) * i / n
        pts.append((cx + r * math.cos(a), y1 - r + r * math.sin(a)))
    pts.append((x0, y1))
    return pts


def d_shape():
    h = (S - GAP) - GAP
    x0, y0, y1 = GAP, GAP, S - GAP
    x1 = GAP + 0.88 * h + 0.025 * h
    r = h / 2
    outer = d_outline(x0, y0, x1, y1, r)
    inner = d_outline(x0 + T, y0 + T, x1 - T, y1 - T, r - T)
    return [[(u, v, S) for u, v in ring] for ring in (outer, inner)]  # cara izquierda


def svg(paleta, size=1024, margin=0.08):
    letras = {"F": f_shape(), "D": d_shape(), "L": l_shape()}
    proj = {k: [[iso(p) for p in ring] for ring in rings] for k, rings in letras.items()}
    xs = [x for rings in proj.values() for ring in rings for x, _ in ring]
    ys = [y for rings in proj.values() for ring in rings for _, y in ring]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = size * (1 - 2 * margin) / max(w, h)
    ox = (size - w * scale) / 2 - min(xs) * scale
    oy = (size - h * scale) / 2 - min(ys) * scale
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    if paleta == "degradado":
        # diagonal de arriba-izquierda a abajo-derecha del logo
        x0, y0 = min(xs) * scale + ox, min(ys) * scale + oy
        x1, y1 = max(xs) * scale + ox, max(ys) * scale + oy
        stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in DEGRADADO)
        out.append(f'  <defs><linearGradient id="grad" gradientUnits="userSpaceOnUse" '
                   f'x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}">{stops}</linearGradient></defs>')
    for k in ("F", "D", "L"):
        d = " ".join("M" + " L".join(f"{x * scale + ox:.2f},{y * scale + oy:.2f}" for x, y in ring) + " Z"
                     for ring in proj[k])
        out.append(f'  <path id="{k}" d="{d}" fill="{PALETAS[paleta][k]}" fill-rule="evenodd"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# Estilo "letra extruida" plana: cara en un color, canto en otro más oscuro, sin sombras
EXTRUIDO = {
    "plenos": {"cara": "#8A4FE8", "canto": "#3B1580"},
    "degradado": {"cara": "url(#grad)", "canto": "url(#grad-canto)"},
}
# Recorrido amplio azul -> violeta, como en el render 3D
DEGRADADO_CARA = [(0.00, "#2F95F0"), (0.30, "#4F63E0"), (0.60, "#7442D6"), (1.00, "#8A2CC4")]
DEGRADADO_CANTO = [(0.00, "#123A86"), (0.40, "#25267A"), (1.00, "#3B1270")]
PROFUNDIDAD = 1.3
NORMALES = {"F": (0, 1, 0), "D": (0, 0, 1), "L": (1, 0, 0)}  # hacia la cámara


def svg_extruido(estilo, size=1024, margin=0.08):
    letras = {"F": f_shape(), "D": d_shape(), "L": l_shape()}
    piezas = {}  # letra -> (polígonos del canto, anillos de la cara)
    for k, rings in letras.items():
        n = NORMALES[k]
        frente = [[(x + n[0] * PROFUNDIDAD, y + n[1] * PROFUNDIDAD, z + n[2] * PROFUNDIDAD) for x, y, z in r]
                  for r in rings]
        canto = []  # solo las paredes laterales: la cara trasera no se ve y taparía el hueco de la D
        for atras, adelante in zip(rings, frente):
            for i in range(len(atras)):
                j = (i + 1) % len(atras)
                canto.append([iso(atras[i]), iso(atras[j]), iso(adelante[j]), iso(adelante[i])])
        piezas[k] = (canto, [list(map(iso, r)) for r in frente])

    pts = [p for c, f in piezas.values() for poly in c + f for p in poly]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = size * (1 - 2 * margin) / max(w, h)
    ox = (size - w * scale) / 2 - min(xs) * scale
    oy = (size - h * scale) / 2 - min(ys) * scale
    fmt = lambda poly: "M" + " L".join(f"{x * scale + ox:.2f},{y * scale + oy:.2f}" for x, y in poly) + " Z"

    col = EXTRUIDO[estilo]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    if col["cara"].startswith("url"):
        x0, y0 = min(xs) * scale + ox, min(ys) * scale + oy
        x1, y1 = max(xs) * scale + ox, max(ys) * scale + oy
        out.append("  <defs>")
        for gid, paradas in (("grad", DEGRADADO_CARA), ("grad-canto", DEGRADADO_CANTO)):
            stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in paradas)
            out.append(f'    <linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
                       f'x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}">{stops}</linearGradient>')
        out.append("  </defs>")
    for k in ("F", "D", "L"):  # de atrás hacia adelante
        canto, cara = piezas[k]
        out.append(f'  <g id="{k}">')
        # cada pieza del canto por separado: en un solo path las superpuestas se cancelan
        for poly in canto:
            out.append(f'    <path d="{fmt(poly)}" fill="{col["canto"]}" '
                       f'stroke="{col["canto"]}" stroke-width="0.6" stroke-linejoin="round"/>')
        out.append(f'    <path d="{" ".join(fmt(r) for r in cara)}" fill="{col["cara"]}" fill-rule="evenodd"/>')
        out.append("  </g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for nombre in PALETAS:
        with open(os.path.join(here, f"logo-fld-2d-{nombre}.svg"), "w") as fh:
            fh.write(svg(nombre))
    for estilo in EXTRUIDO:
        with open(os.path.join(here, f"logo-fld-extruido-{estilo}.svg"), "w") as fh:
            fh.write(svg_extruido(estilo))
