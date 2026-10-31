"""
Cinta de vidrio — escena para Blender (3.6 o 4.x). Variante de la cinta Tregua en acrílico.

Cómo usarlo:
  1. Abrí Blender, andá a la pestaña "Scripting".
  2. Text > Open… y elegí este archivo.
  3. Apretá "Run Script". Borra la escena actual y arma todo de cero.
  4. Para ver la animación: modo "Rendered" en el viewport y barra espaciadora.
  5. Para el video: guardá el .blend y Render > Render Animation (sale un MP4 vertical).

Qué arma:
  - Una cinta gruesa de acrílico pulido, en espiral vertical de poco más de dos vueltas,
    con degradé rosa → magenta → violeta → lavanda (más intenso en los cantos, donde el
    vidrio es más grueso) y bordes biselados que se encienden con la luz.
  - "TREGUA TALLER" grabado en el vidrio: esmerilado, mate y apenas hundido, sobre una
    superficie que es todo brillo.
  - Fondo celeste iluminado desde arriba (un cenital que lo aclara hacia el borde superior).
  - Luz de estudio: cenital fuerte, tiras verticales a los costados y paneles que se reflejan
    como ventanas en el vidrio.
  - Movimiento tranquilo en loop: la espiral gira despacio, flota y se mece.

Todo lo ajustable está en PARÁMETROS.
"""

import math
import os

import bmesh
import bpy
from mathutils import Euler, Vector

# ------------------------------------------------------------------ PARÁMETROS
GRABADO = "TREGUA TALLER"   # se repite a lo largo de toda la cinta
SEPARACION = 1.1          # espacio entre repeticiones, en anchos de cinta
# Tipografía: Archivo Expanded Medium (Google Fonts, licencia OFL), en la carpeta fuentes/ al
# lado del script. Podés poner la ruta a otro .ttf/.otf; si no la encuentra, usa la de Blender.
FONT_PATH = "fuentes/ArchivoExpanded-Medium.ttf"
ALTO_GRABADO = 0.34       # alto de las mayúsculas respecto del ancho de la cinta

# Degradé a lo largo de la cinta (de abajo hacia arriba)
DEGRADE = [
    (0.00, "#FF7AD0"),   # rosa
    (0.38, "#E8399C"),   # magenta
    (0.66, "#7638FF"),   # violeta intenso
    (1.00, "#7EA2FF"),   # lavanda azulada
]
COLOR_FONDO = "#8AB5E6"   # celeste de abajo (un poco más profundo: la cinta resalta)
COLOR_FONDO_LUZ = "#EEF5FC"  # arriba, donde pega la luz cenital, casi blanco
COLOR_HALO = "#D9BDF4"    # el vidrio tiñe apenas el aire detrás: halo rosado violeta

RUGOSIDAD = 0.015         # el vidrio: pulido, casi espejo
RUGOSIDAD_GRABADO = 0.5   # el grabado: esmerilado
TINTE = 1.6               # cuánto se satura el color en curvas y cantos (más = más color)
GROSOR = 0.17             # espesor del acrílico
BISEL = 0.05              # redondeo de los cantos (lo que brilla)
CORTE_DIAGONAL = 0.7      # las puntas cortadas en diagonal (0 = corte recto)

ANCHO = 0.95              # ancho de la cinta
RADIO = 1.15              # radio de la espiral
PASO = 2.7                # altura de cada vuelta
VUELTAS = 2.1
INCLINACION = 8           # grados que se inclina la espiral

FPS = 30
DURACION_LOOP = 16        # segundos que tarda en dar una vuelta completa
RESOLUCION = (1080, 1920) # vertical, como la referencia
MUESTRAS = 160
FLOTAR = 0.08             # cuánto sube y baja
BALANCEO = 3.0            # grados que se mece
# -----------------------------------------------------------------------------

LARGO_VUELTA = math.hypot(2 * math.pi * RADIO, PASO)
LARGO_TOTAL = LARGO_VUELTA * VUELTAS


def hex_a_lineal(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


def limpiar_escena():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coleccion in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                      bpy.data.cameras, bpy.data.lights, bpy.data.textures):
        for bloque in list(coleccion):
            if bloque.users == 0:
                coleccion.remove(bloque)


def entrada(nodo, *nombres):
    """Primera entrada que exista (los nombres cambian entre Blender 3.x y 4.x)."""
    for n in nombres:
        if n in nodo.inputs:
            return nodo.inputs[n]
    return None


def mezcla_color(nt, factor):
    """Nodo Mix en modo color; devuelve (nodo, entrada A, entrada B, salida)."""
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    if isinstance(factor, float):
        m.inputs["Factor"].default_value = factor
    else:
        nt.links.new(factor, m.inputs["Factor"])
    a = next(i for i in m.inputs if i.identifier == "A_Color")
    b = next(i for i in m.inputs if i.identifier == "B_Color")
    out = next(o for o in m.outputs if o.identifier == "Result_Color")
    return m, a, b, out


def mezcla_valor(nt, factor, a, b):
    """a + (b - a) * factor, con factor conectado a un socket."""
    m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs["To Min"].default_value = a
    m.inputs["To Max"].default_value = b
    nt.links.new(factor, m.inputs["Value"])
    return m.outputs["Result"]


# ---------- Grabado: se renderiza el texto una vez a una imagen (máscara) ----------
def buscar_fuente():
    """Ruta absoluta a FONT_PATH: tal cual, al lado del script o al lado del .blend."""
    if not FONT_PATH:
        return None
    candidatas = [FONT_PATH, bpy.path.abspath("//" + FONT_PATH)]
    carpetas = []
    if "__file__" in globals():
        carpetas.append(os.path.dirname(os.path.abspath(__file__)))
    carpetas += [os.path.dirname(bpy.path.abspath(t.filepath)) for t in bpy.data.texts if t.filepath]
    candidatas += [os.path.join(c, FONT_PATH) for c in carpetas]
    for ruta in candidatas:
        if ruta and os.path.isfile(ruta):
            return ruta
    print("No encontré la tipografía", FONT_PATH, "- uso la de Blender")
    return None


def imagen_del_grabado():
    """Renderiza GRABADO a un PNG con transparencia. Devuelve (imagen, largo del tramo en metros).

    El tramo se ajusta para que entre una cantidad exacta de veces en la cinta.
    """
    principal = bpy.context.scene
    curva = bpy.data.curves.new("Grabado", type="FONT")
    curva.body = GRABADO
    curva.size = ALTO_GRABADO * ANCHO / 0.72  # el cuerpo de la fuente es más alto que la mayúscula
    curva.align_x = "LEFT"
    curva.align_y = "CENTER"
    curva.space_character = 1.12
    fuente = buscar_fuente()
    if fuente:
        curva.font = bpy.data.fonts.load(fuente, check_existing=True)
    texto = bpy.data.objects.new("Grabado", curva)
    principal.collection.objects.link(texto)  # un momento en la escena, para convertirlo
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(texto.evaluated_get(deps))
    bpy.data.objects.remove(texto, do_unlink=True)
    bpy.data.curves.remove(curva)

    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    largo_texto = max(xs) - min(xs)
    repeticiones = max(1, round(LARGO_TOTAL / (largo_texto + SEPARACION * ANCHO)))
    margen = (LARGO_TOTAL / repeticiones - largo_texto) / 2
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.translate(bm, verts=bm.verts,
                        vec=Vector((margen - min(xs), -(min(ys) + max(ys)) / 2, 0)))
    bm.to_mesh(me)
    bm.free()
    largo = largo_texto + 2 * margen

    tmp = bpy.data.scenes.new("GrabadoTmp")
    plano = bpy.data.objects.new("GrabadoPlano", me)
    tmp.collection.objects.link(plano)
    blanco = bpy.data.materials.new("GrabadoTmp")
    blanco.use_nodes = True
    nt = blanco.node_tree
    nt.nodes.clear()
    emision = nt.nodes.new("ShaderNodeEmission")
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emision.outputs["Emission"], salida.inputs["Surface"])
    me.materials.append(blanco)

    cam_data = bpy.data.cameras.new("CamGrabado")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = largo
    cam_data.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("CamGrabado", cam_data)
    tmp.collection.objects.link(cam)
    cam.location = (largo / 2, 0, 5)
    tmp.camera = cam

    ancho_px = 4096
    # Cycles con emisión blanca: funciona igual con o sin placa de video
    tmp.render.engine = "CYCLES"
    tmp.cycles.samples = 8
    tmp.cycles.use_denoising = False
    tmp.render.resolution_x = ancho_px
    tmp.render.resolution_y = max(8, round(ancho_px * ANCHO / largo))
    tmp.render.resolution_percentage = 100
    tmp.render.film_transparent = True
    tmp.view_settings.view_transform = "Standard"
    tmp.render.image_settings.file_format = "PNG"
    tmp.render.image_settings.color_mode = "RGBA"
    ruta = os.path.join(bpy.app.tempdir or "/tmp", "tregua_grabado.png")
    tmp.render.filepath = ruta
    bpy.ops.render.render(write_still=True, scene=tmp.name)

    img = bpy.data.images.load(ruta, check_existing=False)
    img.name = "Grabado"
    img.pack()
    for ob in list(tmp.collection.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    bpy.data.meshes.remove(me)
    bpy.data.materials.remove(blanco)
    bpy.data.scenes.remove(tmp)
    if bpy.context.window:
        bpy.context.window.scene = principal
    return img, largo


# ---------- Material: acrílico pulido con degradé; opcionalmente con el grabado ----------
def material_vidrio(nombre, grabado=None, claridad=0.32):
    """claridad: cuánto se aclara el color de frente (0 = color pleno, 1 = blanco)."""
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    transm = entrada(bsdf, "Transmission Weight", "Transmission")
    transm.default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.49  # acrílico
    bsdf.inputs["Roughness"].default_value = RUGOSIDAD
    disp = entrada(bsdf, "Dispersion")
    if disp:  # Blender 4.2+: separa un poco los colores en los cantos
        disp.default_value = 0.15
    coat = entrada(bsdf, "Coat Weight", "Clearcoat")
    if coat:
        coat.default_value = 1.0
    coat_r = entrada(bsdf, "Coat Roughness", "Clearcoat Roughness")
    if coat_r:
        coat_r.default_value = 0.0

    # degradé a lo largo: la UV x está en metros sobre el largo de la cinta
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    a_fraccion = nt.nodes.new("ShaderNodeMath")
    a_fraccion.operation = "DIVIDE"
    a_fraccion.inputs[1].default_value = LARGO_TOTAL
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    els = rampa.color_ramp.elements
    els[0].position, els[0].color = DEGRADE[0][0], hex_a_lineal(DEGRADE[0][1])
    els[1].position, els[1].color = DEGRADE[-1][0], hex_a_lineal(DEGRADE[-1][1])
    for pos, col in DEGRADE[1:-1]:
        els.new(pos).color = hex_a_lineal(col)
    rampa.color_ramp.interpolation = "EASE"
    nt.links.new(coord.outputs["UV"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], a_fraccion.inputs[0])
    nt.links.new(a_fraccion.outputs["Value"], rampa.inputs["Fac"])

    # de frente el vidrio se ve claro (tono pastel); de costado, en curvas y cantos, donde se
    # mira a través de más espesor, el color se satura como en el acrílico
    _, pa, pb, claro = mezcla_color(nt, claridad)
    pb.default_value = (1, 1, 1, 1)
    nt.links.new(rampa.outputs["Color"], pa)
    angulo = nt.nodes.new("ShaderNodeLayerWeight")
    angulo.inputs["Blend"].default_value = 0.35
    curva_tinte = nt.nodes.new("ShaderNodeMath")
    curva_tinte.operation = "POWER"
    curva_tinte.inputs[1].default_value = 1 / TINTE
    nt.links.new(angulo.outputs["Facing"], curva_tinte.inputs[0])
    _, ta, tb, pastel = mezcla_color(nt, curva_tinte.outputs["Value"])
    nt.links.new(claro, ta)
    nt.links.new(rampa.outputs["Color"], tb)

    if grabado is None:
        nt.links.new(pastel, bsdf.inputs["Base Color"])
        mat.diffuse_color = hex_a_lineal(DEGRADE[2][1])
        return mat

    img, largo = grabado
    ubica = nt.nodes.new("ShaderNodeMapping")
    ubica.inputs["Scale"].default_value = (1 / largo, 1 / ANCHO, 1)
    # corrido medio corte diagonal: las palabras completas arrancan después de la punta
    ubica.inputs["Location"].default_value = (-(CORTE_DIAGONAL * ANCHO / 2) / largo, 0, 0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"  # "TREGUA TALLER" en loop a lo largo de toda la cinta
    tex.interpolation = "Cubic"
    nt.links.new(coord.outputs["UV"], ubica.inputs["Vector"])
    nt.links.new(ubica.outputs["Vector"], tex.inputs["Vector"])
    # la máscara del grabado se apaga cerca de las puntas (el canto queda limpio) y se
    # suaviza vista desde adentro del vidrio (el texto espejado queda como una sombra leve)
    def rango(valor, desde, hasta, a, b):
        m = nt.nodes.new("ShaderNodeMapRange")
        m.clamp = True
        m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = desde, hasta
        m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = a, b
        nt.links.new(valor, m.inputs["Value"])
        return m.outputs["Result"]

    def multiplicar(a, b):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        nt.links.new(a, m.inputs[0])
        nt.links.new(b, m.inputs[1])
        return m.outputs["Value"]

    limpio = CORTE_DIAGONAL * ANCHO * 0.5
    puntas = multiplicar(rango(sep.outputs["X"], limpio, limpio + 0.5, 0.0, 1.0),
                         rango(sep.outputs["X"], LARGO_TOTAL - limpio - 0.5, LARGO_TOTAL - limpio, 1.0, 0.0))
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    desde_adentro = rango(geo.outputs["Backfacing"], 0.0, 1.0, 1.0, 0.25)
    # mirado muy de costado (cerca de los cantos) el grabado se apaga: evita las copias
    # refractadas que aparecían como rayitas debajo de las letras
    costado = nt.nodes.new("ShaderNodeLayerWeight")
    costado.inputs["Blend"].default_value = 0.5
    de_frente = rango(costado.outputs["Facing"], 0.55, 0.9, 1.0, 0.2)
    mascara = multiplicar(multiplicar(multiplicar(tex.outputs["Alpha"], puntas), desde_adentro), de_frente)

    # dentro del grabado: esmerilado con granito, más blanco, sin brillo de laca y apenas hundido
    grano = nt.nodes.new("ShaderNodeTexNoise")
    grano.inputs["Scale"].default_value = 450.0
    grano.inputs["Detail"].default_value = 3.0
    rug_grabado = nt.nodes.new("ShaderNodeMapRange")
    rug_grabado.inputs["To Min"].default_value = RUGOSIDAD_GRABADO * 0.75
    rug_grabado.inputs["To Max"].default_value = RUGOSIDAD_GRABADO * 1.25
    nt.links.new(coord.outputs["Object"], grano.inputs["Vector"])
    nt.links.new(grano.outputs["Fac"], rug_grabado.inputs["Value"])
    rug = nt.nodes.new("ShaderNodeMix")
    rug.data_type = "FLOAT"
    nt.links.new(mascara, rug.inputs["Factor"])
    rug.inputs["A"].default_value = RUGOSIDAD
    # destellos del arenado: puntitos pulidos dentro del esmerilado que atrapan la luz
    destellos = nt.nodes.new("ShaderNodeTexVoronoi")
    destellos.inputs["Scale"].default_value = 520.0
    nt.links.new(coord.outputs["Object"], destellos.inputs["Vector"])
    punto_pulido = rango(destellos.outputs["Distance"], 0.0, 0.12, 1.0, 0.0)
    rug_final = nt.nodes.new("ShaderNodeMix")
    rug_final.data_type = "FLOAT"
    nt.links.new(punto_pulido, rug_final.inputs["Factor"])
    nt.links.new(rug_grabado.outputs["Result"], rug_final.inputs["A"])
    rug_final.inputs["B"].default_value = 0.04
    nt.links.new(rug_final.outputs["Result"], rug.inputs["B"])
    nt.links.new(rug.outputs["Result"], bsdf.inputs["Roughness"])

    # esmerilado con granito: el blanco varía apenas de punto a punto
    _, ga, gb, blanco = mezcla_color(nt, grano.outputs["Fac"])
    ga.default_value = (0.74, 0.75, 0.86, 1.0)  # menos blanco: se ve el vidrio debajo
    gb.default_value = (0.93, 0.93, 0.98, 1.0)
    _, ca, cb, color = mezcla_color(nt, 0.0)
    nt.links.new(mascara, ca.node.inputs["Factor"])
    nt.links.new(pastel, ca)
    nt.links.new(blanco, cb)
    nt.links.new(color, bsdf.inputs["Base Color"])

    if coat:
        nt.links.new(mezcla_valor(nt, mascara, 1.0, 0.0), coat)
    nt.links.new(mezcla_valor(nt, mascara, 1.0, 0.7), transm)

    hundido = nt.nodes.new("ShaderNodeBump")
    hundido.invert = True
    hundido.inputs["Strength"].default_value = 0.6
    hundido.inputs["Distance"].default_value = 0.01
    nt.links.new(mascara, hundido.inputs["Height"])
    # micro relieve del arenado, sólo dentro de las letras
    arena = nt.nodes.new("ShaderNodeTexNoise")
    arena.inputs["Scale"].default_value = 950.0
    arena.inputs["Detail"].default_value = 2.0
    nt.links.new(coord.outputs["Object"], arena.inputs["Vector"])
    granito = nt.nodes.new("ShaderNodeBump")
    granito.inputs["Strength"].default_value = 0.55
    granito.inputs["Distance"].default_value = 0.002
    nt.links.new(multiplicar(arena.outputs["Fac"], mascara), granito.inputs["Height"])
    nt.links.new(hundido.outputs["Normal"], granito.inputs["Normal"])
    nt.links.new(granito.outputs["Normal"], bsdf.inputs["Normal"])
    mat.diffuse_color = hex_a_lineal(DEGRADE[2][1])
    return mat


# ---------- Cinta: banda sobre una espiral vertical, con grosor y bisel ----------
def crear_cinta(mat_frente, mat_resto, mat_puntas):
    """Sólido cerrado: cara de afuera (grabada), cara de adentro y cantos, y las dos puntas."""
    pasos = int(LARGO_TOTAL / 0.02)
    div = 6
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    def punto(s, y, d=0.0):
        th = 2 * math.pi * s / LARGO_VUELTA
        z = PASO * th / (2 * math.pi) - PASO * VUELTAS / 2
        r = RADIO * (1 + 0.06 * math.sin(0.9 * th + 0.4))  # apenas despareja, hecha a mano
        c = Vector((r * math.cos(th), r * math.sin(th), z))
        t = Vector((-r * math.sin(th), r * math.cos(th), PASO / (2 * math.pi))).normalized()
        n = Vector((math.cos(th), math.sin(th), 0.0))
        b = n.cross(t).normalized()  # T × B = N: el grabado se lee derecho desde afuera
        return c + b * y - n * d   # d: hacia adentro, para el espesor

    # cada línea a lo largo arranca y termina un poco corrida: las puntas quedan en diagonal,
    # así el corte no se ve de frente como un bloque y refracta la luz
    corrimiento = CORTE_DIAGONAL * ANCHO
    afuera, adentro = [], []
    for i in range(pasos + 1):
        fa, fi = [], []
        for j in range(div + 1):
            k = j / div
            s0 = corrimiento * k
            s1 = LARGO_TOTAL - corrimiento * (1 - k)
            s = s0 + (s1 - s0) * i / pasos
            y = -ANCHO / 2 + ANCHO * k
            # UV en metros: x a lo largo, y a lo ancho
            fa.append((bm.verts.new(punto(s, y)), s, ANCHO * k))
            fi.append((bm.verts.new(punto(s, y, GROSOR)), s, ANCHO * k))
        afuera.append(fa)
        adentro.append(fi)

    def cara(esquinas, material):
        c = bm.faces.new([e[0] for e in esquinas])
        c.material_index = material
        for loop, e in zip(c.loops, esquinas):
            loop[uv].uv = (e[1], e[2])

    for i in range(pasos):
        for j in range(div):
            cara((afuera[i][j], afuera[i + 1][j], afuera[i + 1][j + 1], afuera[i][j + 1]), 0)
            cara((adentro[i][j], adentro[i][j + 1], adentro[i + 1][j + 1], adentro[i + 1][j]), 1)
        for j in (0, div):  # cantos largos
            cara((afuera[i][j], adentro[i][j], adentro[i + 1][j], afuera[i + 1][j]), 1)
    for i in (0, pasos):    # puntas
        for j in range(div):
            cara((afuera[i][j], afuera[i][j + 1], adentro[i][j + 1], adentro[i][j]), 2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])  # todas hacia afuera del sólido

    me = bpy.data.meshes.new("CintaVidrio")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat_frente)
    me.materials.append(mat_resto)
    me.materials.append(mat_puntas)
    ob = bpy.data.objects.new("CintaVidrio", me)
    bpy.context.scene.collection.objects.link(ob)

    bis = ob.modifiers.new("Bisel", "BEVEL")
    bis.width = BISEL
    bis.segments = 10  # bisel redondeado y suave: las líneas de luz no se cortan en facetas
    bis.profile = 0.5
    bis.limit_method = "ANGLE"
    bis.angle_limit = math.radians(40)
    # normales pesadas por cara: caras planas limpias y puntas que se ven de vidrio, no grises
    try:
        if bpy.app.version < (4, 1, 0):
            me.use_auto_smooth = True
        wn = ob.modifiers.new("Normales", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 100
    except (AttributeError, RuntimeError):
        pass
    return ob


# ---------- Fondo celeste lejano, que se aclara arriba como si lo bañara un cenital ----------
def crear_fondo():
    me = bpy.data.meshes.new("Fondo")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Fondo", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 16, 0)
    ob.rotation_euler = (math.pi / 2, 0, 0)

    # color exacto (emisión): un degradé vertical más un brillo redondo arriba al centro
    mat = bpy.data.materials.new("Fondo celeste")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    # el plano está rotado: la Y de "Generated" es la altura en cuadro
    vertical = nt.nodes.new("ShaderNodeMapRange")
    vertical.inputs["From Min"].default_value, vertical.inputs["From Max"].default_value = 0.3, 0.75
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Y"], vertical.inputs["Value"])
    centro = nt.nodes.new("ShaderNodeMapRange")  # más luz al centro que en los costados
    centro.inputs["From Min"].default_value, centro.inputs["From Max"].default_value = 0.5, 0.15
    resta = nt.nodes.new("ShaderNodeMath")
    resta.operation = "ABSOLUTE"
    menos = nt.nodes.new("ShaderNodeMath")
    menos.operation = "SUBTRACT"
    menos.inputs[1].default_value = 0.5
    nt.links.new(sep.outputs["X"], menos.inputs[0])
    nt.links.new(menos.outputs["Value"], resta.inputs[0])
    nt.links.new(resta.outputs["Value"], centro.inputs["Value"])
    luz_total = nt.nodes.new("ShaderNodeMath")
    luz_total.operation = "MULTIPLY"
    nt.links.new(vertical.outputs["Result"], luz_total.inputs[0])
    nt.links.new(centro.outputs["Result"], luz_total.inputs[1])
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    els = rampa.color_ramp.elements
    els[0].color = hex_a_lineal(COLOR_FONDO)
    els[1].color = hex_a_lineal(COLOR_FONDO_LUZ)
    rampa.color_ramp.interpolation = "EASE"
    nt.links.new(luz_total.outputs["Value"], rampa.inputs["Fac"])
    emision = nt.nodes.new("ShaderNodeEmission")
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    # halo de color detrás de la cinta, redondo y muy suave
    distancia = nt.nodes.new("ShaderNodeVectorMath")
    distancia.operation = "DISTANCE"
    distancia.inputs[1].default_value = (0.5, 0.52, 0.0)
    plano = nt.nodes.new("ShaderNodeVectorMath")
    plano.operation = "MULTIPLY"
    plano.inputs[1].default_value = (1.0, 1.0, 0.0)
    nt.links.new(coord.outputs["Generated"], plano.inputs[0])
    nt.links.new(plano.outputs["Vector"], distancia.inputs[0])
    halo = nt.nodes.new("ShaderNodeMapRange")
    halo.inputs["From Min"].default_value, halo.inputs["From Max"].default_value = 0.11, 0.0
    halo.inputs["To Max"].default_value = 0.6
    nt.links.new(distancia.outputs["Value"], halo.inputs["Value"])
    halo_suave = nt.nodes.new("ShaderNodeMath")
    halo_suave.operation = "POWER"
    halo_suave.inputs[1].default_value = 1.6
    nt.links.new(halo.outputs["Result"], halo_suave.inputs[0])
    tinte = nt.nodes.new("ShaderNodeMix")
    tinte.data_type = "RGBA"
    nt.links.new(halo_suave.outputs["Value"], tinte.inputs["Factor"])
    nt.links.new(rampa.outputs["Color"], next(i for i in tinte.inputs if i.identifier == "A_Color"))
    next(i for i in tinte.inputs if i.identifier == "B_Color").default_value = hex_a_lineal(COLOR_HALO)
    nt.links.new(next(o for o in tinte.outputs if o.identifier == "Result_Color"), emision.inputs["Color"])
    nt.links.new(emision.outputs["Emission"], salida.inputs["Surface"])
    me.materials.append(mat)
    return ob


def configurar_mundo():
    mundo = bpy.data.worlds.get("Estudio") or bpy.data.worlds.new("Estudio")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes.get("Background")
    fondo.inputs["Color"].default_value = (0.9, 0.93, 1.0, 1.0)  # estudio blanco, apenas azulado
    fondo.inputs["Strength"].default_value = 0.8  # más luz ambiente: los cantos no reflejan oscuro


def configurar_render():
    escena = bpy.context.scene
    escena.render.resolution_x, escena.render.resolution_y = RESOLUCION
    escena.render.fps = FPS
    escena.frame_start = 1
    escena.frame_end = FPS * DURACION_LOOP
    escena.render.engine = "CYCLES"  # el vidrio necesita Cycles
    escena.cycles.samples = MUESTRAS
    escena.cycles.use_denoising = True
    escena.cycles.max_bounces = 24
    escena.cycles.transmission_bounces = 20
    escena.cycles.glossy_bounces = 8
    escena.cycles.transparent_max_bounces = 16
    escena.cycles.caustics_reflective = False
    escena.cycles.caustics_refractive = False
    # "Standard": el celeste y los pasteles tal cual; los brillos llegan a blanco como en la foto
    escena.view_settings.view_transform = "Standard"
    escena.view_settings.look = "None"
    try:
        escena.render.image_settings.file_format = "FFMPEG"
        escena.render.ffmpeg.format = "MPEG4"
        escena.render.ffmpeg.codec = "H264"
        escena.render.ffmpeg.constant_rate_factor = "HIGH"
    except (TypeError, AttributeError):
        pass
    escena.render.filepath = "//cinta_vidrio_"
    configurar_resplandor(escena)


def configurar_resplandor(escena):
    """Bloom suave en las luces altas, como el halo de una foto (compositor)."""
    escena.use_nodes = True
    nt = escena.node_tree
    nt.nodes.clear()
    capas = nt.nodes.new("CompositorNodeRLayers")
    brillo = nt.nodes.new("CompositorNodeGlare")
    salida = nt.nodes.new("CompositorNodeComposite")
    try:
        brillo.glare_type = "FOG_GLOW"
        brillo.quality = "HIGH"
        brillo.threshold = 0.7
        brillo.mix = -0.5   # -1 = sólo la imagen; -0.5 = halo suave y visible
        brillo.size = 8
    except (AttributeError, TypeError):
        pass  # versiones nuevas cambiaron estas opciones: queda el resplandor por defecto
    nt.links.new(capas.outputs["Image"], brillo.inputs["Image"])
    # grano fotográfico muy sutil: le saca lo digital al fondo y evita cortes en el degradé
    textura = bpy.data.textures.get("Grano de foto") or bpy.data.textures.new("Grano de foto", "NOISE")
    ruido = nt.nodes.new("CompositorNodeTexture")
    ruido.texture = textura
    grano = nt.nodes.new("CompositorNodeMixRGB")
    grano.blend_type = "OVERLAY"
    grano.inputs["Fac"].default_value = 0.03
    nt.links.new(brillo.outputs["Image"], grano.inputs[1])
    nt.links.new(ruido.outputs["Color"], grano.inputs[2])
    nt.links.new(grano.outputs["Image"], salida.inputs["Image"])


def main():
    limpiar_escena()
    escena = bpy.context.scene

    pivote = bpy.data.objects.new("Pivote", None)
    escena.collection.objects.link(pivote)

    grabado = imagen_del_grabado()
    # puntas: corte satinado, como el acrílico cortado y apenas lijado; junta luz y brilla
    puntas = material_vidrio("Corte satinado", claridad=0.35)
    pnt = puntas.node_tree
    pbsdf = pnt.nodes.get("Principled BSDF")
    pbsdf.inputs["Roughness"].default_value = 0.28
    # de frente el corte deja ver adentro; hacia los bordes redondeados se vuelve lechoso y claro
    frente = pnt.nodes.new("ShaderNodeLayerWeight")
    frente.inputs["Blend"].default_value = 0.4
    transp = pnt.nodes.new("ShaderNodeMapRange")
    transp.inputs["To Min"].default_value, transp.inputs["To Max"].default_value = 0.8, 0.25
    pnt.links.new(frente.outputs["Facing"], transp.inputs["Value"])
    pnt.links.new(transp.outputs["Result"], entrada(pbsdf, "Transmission Weight", "Transmission"))
    color_actual = pbsdf.inputs["Base Color"].links[0].from_socket
    _, ba, bb, borde = mezcla_color(pnt, frente.outputs["Facing"])
    pnt.links.new(color_actual, ba)
    bb.default_value = (1.0, 0.9, 0.97, 1.0)
    pnt.links.new(borde, pbsdf.inputs["Base Color"])
    coat_p = entrada(pbsdf, "Coat Weight", "Clearcoat")
    if coat_p:
        coat_p.default_value = 0.0
    cinta = crear_cinta(material_vidrio("Vidrio con grabado", grabado),
                        material_vidrio("Vidrio", claridad=0.12),  # cantos y dorso: color más intenso
                        puntas)
    cinta.parent = pivote
    crear_fondo()

    # Cámara: lente larga, apenas desde arriba
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 78
    cam_data.shift_x = 0.035   # la espiral queda centrada y con aire abajo
    cam_data.shift_y = -0.02
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 16.0
    cam_data.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    cam.location = (0, -15.6, 3.2)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, energia, pos, mira, tam_x, tam_y, color=(1, 1, 1)):
        datos = bpy.data.lights.new(nombre, "AREA")
        datos.energy = energia
        datos.color = color
        datos.shape = "RECTANGLE"
        datos.size, datos.size_y = tam_x, tam_y
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        return ob

    # Cenital: viene de arriba, enciende los bordes superiores y baña el fondo desde arriba
    luz("Cenital", 2600, (0, 2, 10), (0, 6, 0), 7, 4)
    # Una tira nítida a la izquierda (la línea de luz en los cantos) y un softbox ancho a la
    # derecha que deja un brillo grande y difuso sobre las caras
    luz("Tira izquierda", 650, (-6, -1, 2), (0, 0, 0), 0.6, 12)
    luz("Softbox derecho", 420, (7, -2.5, 1), (0, 0, 0), 5, 10, (1.0, 0.94, 0.98))
    # Panel grande adelante: un reflejo amplio y suave, como una ventana
    luz("Ventana", 160, (-3, -9, 4), (0, 0, 0), 5, 6)
    # rebote suave desde abajo, como una mesa blanca: las puntas no reflejan negro
    luz("Rebote", 1300, (0, -3, -8), (0, 0, 0), 9, 6, (0.9, 0.95, 1.0))
    # acento chico de costado y abajo: marca el volumen de los cantos redondeados de las puntas
    luz("Acento puntas", 120, (3.5, 2.5, -5), (0.8, 0, -2.2), 0.8, 0.8, (1.0, 0.92, 0.98))

    configurar_mundo()
    configurar_render()

    # Movimiento en loop: un giro completo, flotando y meciéndose (inclinada hacia la izquierda)
    total = FPS * DURACION_LOOP
    inclinacion = math.radians(INCLINACION)
    prefs = bpy.context.preferences.edit
    interp_original = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for f in range(total + 1):
            a = 2 * math.pi * f / total
            # el giro va sobre el eje propio de la espiral; la inclinación y el vaivén, en el pivote
            cinta.rotation_euler = (0, 0, a)
            cinta.keyframe_insert("rotation_euler", index=2, frame=f + 1)
            pivote.rotation_euler = Euler((
                math.radians(BALANCEO) * math.sin(2 * a + 0.5),
                inclinacion + math.radians(BALANCEO * 0.7) * math.sin(a + 1.1),
                0,
            ))
            pivote.location = (0, 0, FLOTAR * math.sin(2 * a))
            pivote.keyframe_insert("rotation_euler", frame=f + 1)
            pivote.keyframe_insert("location", frame=f + 1)
    finally:
        prefs.keyframe_new_interpolation_type = interp_original
    escena.frame_set(1)


main()
