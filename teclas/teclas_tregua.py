"""
Teclas TREGUA — escena para Blender (3.6 o 4.x), con sonido.

Dos filas de teclado de verdad (Q W E R T Y U / A S D F G H J, la de abajo corrida como en
un teclado real), paradas de frente a la cámara. Las teclas saltan con anticipación y rebote,
después alguien escribe T R E G U A: cada letra aparece arriba en 3D al apretar su tecla,
las vecinas acusan el golpe, y al final se aprietan todas y la palabra se va. Loop de 8 s.

El script también genera el sonido (clicks de teclado mecánico, golpes de aterrizaje y el
"pop" de cada letra), lo guarda como WAV al lado del .blend y lo pone en el editor de video,
así Render Animation saca un MP4 con audio.

Cómo usarlo:
  1. Guardá un .blend vacío en la carpeta donde quieras el video (el WAV se guarda al lado).
  2. Scripting > Text > Open… > este archivo (la carpeta fuentes/ tiene que estar al lado).
  3. Run Script. Para el video: Render > Render Animation.

Todo lo ajustable está en PARÁMETROS.
"""

import array
import math
import os
import random
import wave

import bmesh
import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ PARÁMETROS
FILAS = [list("QWERTYU"), list("ASDFGHJ")]    # dos filas de un teclado real
CORRIMIENTO_FILA = 0.25                       # la fila de abajo corrida 1/4 de tecla
PALABRA = "TREGUA"                            # lo que se escribe
AZULES = {"Q", "A"}                           # teclas de plástico azul
TRANSPARENTE = "A"                            # la tecla de azul medio transparente
VASTAGO = True            # se ve la cruz del vástago adentro de la tecla transparente

COLOR_AZUL = "#2D5BE3"
COLOR_BLANCO = "#E9E7E2"      # PBT blanco hueso, como la referencia
COLOR_LETRA_OSCURA = "#1B1B1D"
COLOR_LETRA_CLARA = "#FFFFFF"
COLOR_FONDO = "#E2E2E2"   # gris claro: con la luz se ve como el de la referencia

FONT_PATH = "fuentes/JetBrainsMono-Medium.ttf"   # Google Fonts, licencia OFL
TAMANO_LETRA = 0.46

TECLA = 1.0          # ancho de la base de la tecla
SEPARACION = 0.05    # aire entre teclas
ALTO = 0.5           # alto de la tecla

RESOLUCION = (1080, 1080)
MUESTRAS = 192

# Teclas paradas de frente, animación y sonido
GIRO_CAMARA = 24          # grados que la cámara mira desde la derecha
COLOR_PARED = "#CFCFCF"   # pared del fondo, con luz y sombras de persiana
FPS = 30
DURACION = 8              # segundos del loop
RECORRIDO = 0.22          # cuánto se hunde una tecla al apretarla (≈ 4 mm, como una real)
SALTO = 0.55              # cuánto saltan hacia adelante al principio
# cuándo se aprieta cada letra de PALABRA (segundos): ritmo de alguien escribiendo, no de máquina
TIEMPOS_LETRAS = [2.05, 2.38, 2.56, 3.02, 3.26, 3.72]
TODAS_JUNTAS = 5.9        # momento en que se aprietan todas y la palabra se va
TAMANO_PALABRA = 1.0      # alto del cuerpo de la tipografía de la palabra de arriba
VOLUMEN = 0.9             # volumen general del sonido
# -----------------------------------------------------------------------------


def hex_a_lineal(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


def limpiar_escena():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coleccion in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                      bpy.data.cameras, bpy.data.lights):
        for bloque in list(coleccion):
            if bloque.users == 0:
                coleccion.remove(bloque)


def entrada(nodo, *nombres):
    for n in nombres:
        if n in nodo.inputs:
            return nodo.inputs[n]
    return None


def buscar_fuente():
    candidatas = [FONT_PATH, bpy.path.abspath("//" + FONT_PATH)]
    if "__file__" in globals():
        candidatas.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), FONT_PATH))
    candidatas += [os.path.join(os.path.dirname(bpy.path.abspath(t.filepath)), FONT_PATH)
                   for t in bpy.data.texts if t.filepath]
    for ruta in candidatas:
        if ruta and os.path.isfile(ruta):
            return ruta
    print("No encontré la tipografía", FONT_PATH, "- uso la de Blender")
    return None


# ---------- Geometría ----------
def anillo_redondeado(medio, radio, z, por_esquina=10):
    """Cuadrado de lado 2*medio con esquinas de radio `radio`, a la altura z."""
    pts = []
    c = medio - radio
    for k, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        a0 = k * math.pi / 2
        for i in range(por_esquina + 1):
            a = a0 + (math.pi / 2) * i / por_esquina
            pts.append(Vector((sx * c + radio * math.cos(a), sy * c + radio * math.sin(a), z)))
    return pts


# Medidas reales de una tecla MX (1u ≈ 18 mm de base): 1 mm ≈ 0.0556 unidades
MM = TECLA / 18.0
PARED = 1.4 * MM          # espesor de las paredes laterales
TECHO = 1.7 * MM          # espesor del techo (debajo del plato)


def tecla(nombre):
    """Tecla de perfil bajo, hueca como una tecla real: paredes en talud, borde redondeado
    y un plato arriba, apenas hundido, con un escalón suave (como la referencia)."""
    m = TECLA / 2
    h = ALTO
    # superficie de afuera: (z, medio lado, radio de esquina) de abajo hacia arriba
    afuera = [
        (0.0, m, 0.07), (0.03, m, 0.07), (0.08, m * 0.995, 0.08),
        (h * 0.70, m * 0.90, 0.10), (h * 0.88, m * 0.86, 0.11), (h * 0.96, m * 0.81, 0.12),
        (h, m * 0.76, 0.13),                       # borde de arriba
        (h * 0.985, m * 0.72, 0.11),               # escalón hacia el plato
        (h * 0.975, m * 0.64, 0.10), (h * 0.97, m * 0.3, 0.10),
    ]
    # superficie de adentro: la pared copia el talud con PARED de espesor y cierra en un
    # techo plano TECHO por debajo del plato
    techo = h * 0.97 - TECHO
    adentro = [
        (techo, m * 0.3, 0.06), (techo, m * 0.70 - PARED, 0.07),
        (techo - 0.6 * MM, m * 0.80 - PARED, 0.08),   # el techo se redondea contra la pared
        (h * 0.70, m * 0.90 - PARED, 0.10 - PARED * 0.5),
        (0.08, m * 0.995 - PARED, 0.08 - PARED * 0.5), (0.0, m - PARED, 0.07 - PARED * 0.5),
    ]
    bm = bmesh.new()
    anillos = [[bm.verts.new(p) for p in anillo_redondeado(lado, r, z)]
               for z, lado, r in afuera + adentro]
    n = len(anillos[0])
    i_tope = len(afuera) - 1   # último anillo de afuera (centro del plato)
    i_techo = len(afuera)      # primer anillo de adentro (centro del techo)
    for i, (a, b) in enumerate(zip(anillos, anillos[1:])):
        if i == i_tope:  # el plato y el techo son superficies distintas: no se unen
            continue
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    centro_afuera = bm.verts.new((0, 0, h * 0.968))
    centro_adentro = bm.verts.new((0, 0, techo))
    for k in range(n):
        bm.faces.new((anillos[i_tope][k], anillos[i_tope][(k + 1) % n], centro_afuera))
        bm.faces.new((anillos[i_techo][(k + 1) % n], anillos[i_techo][k], centro_adentro))
    # el borde de abajo: el labio entre la pared de afuera y la de adentro
    for k in range(n):
        bm.faces.new((anillos[0][(k + 1) % n], anillos[0][k], anillos[-1][k], anillos[-1][(k + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(ob)
    sub = ob.modifiers.new("Suave", "SUBSURF")
    sub.levels, sub.render_levels = 2, 2
    return ob


def vastago(x, y, mat):
    """El encastre MX que cuelga del techo por dentro de la tecla: un barril redondo de
    5.6 mm con el agujero en cruz de 4.1 × 1.2 mm, que termina apenas arriba del borde."""
    curva = bpy.data.curves.new("Vastago", type="CURVE")
    curva.dimensions = "2D"
    curva.fill_mode = "BOTH"
    radio = 2.8 * MM
    lado, brazo = 4.1 * MM / 2, 1.2 * MM / 2
    circulo = [(radio * math.cos(2 * math.pi * k / 48), radio * math.sin(2 * math.pi * k / 48))
               for k in range(48)]
    cruz = [(brazo, lado), (-brazo, lado), (-brazo, brazo), (-lado, brazo), (-lado, -brazo),
            (-brazo, -brazo), (-brazo, -lado), (brazo, -lado), (brazo, -brazo), (lado, -brazo),
            (lado, brazo), (brazo, brazo)]
    for puntos in (circulo, cruz):
        sp = curva.splines.new("POLY")
        sp.points.add(len(puntos) - 1)
        for p, (px, py) in zip(sp.points, puntos):
            p.co = (px, py, 0, 1)
        sp.use_cyclic_u = True
    techo = ALTO * 0.97 - TECHO
    abajo = 0.6 * MM
    curva.extrude = (techo - abajo) / 2 + 0.002  # se mete apenas en el techo: sin rendija
    ob = bpy.data.objects.new("Vastago", curva)
    bpy.context.scene.collection.objects.link(ob)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(curva)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)  # tapas y paredes en una pieza
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(mat)
    ob = bpy.data.objects.new("Vastago", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (x, y, (techo + abajo) / 2)
    return ob


def letra(caracter, nombre):
    curva = bpy.data.curves.new(nombre, type="FONT")
    curva.body = caracter
    curva.size = TAMANO_LETRA
    curva.align_x = "CENTER"
    curva.align_y = "CENTER"
    curva.extrude = 0.002
    fuente = buscar_fuente()
    if fuente:
        curva.font = bpy.data.fonts.load(fuente, check_existing=True)
    ob = bpy.data.objects.new(nombre, curva)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------- Materiales ----------
def plastico(nombre, color, rugosidad=0.42):
    """Plástico PBT mate: un poco de luz que entra y se difunde (subsurface)."""
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(color)
    bsdf.inputs["Roughness"].default_value = rugosidad
    sss = entrada(bsdf, "Subsurface Weight", "Subsurface")
    if sss:
        sss.default_value = 0.15
    radio = entrada(bsdf, "Subsurface Radius")
    if radio:
        radio.default_value = (0.05, 0.05, 0.05)
    # grano fino del PBT
    nt = mat.node_tree
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 520.0
    relieve = nt.nodes.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.16
    relieve.inputs["Distance"].default_value = 0.002
    nt.links.new(ruido.outputs["Fac"], relieve.inputs["Height"])
    nt.links.new(relieve.outputs["Normal"], bsdf.inputs["Normal"])
    mat.diffuse_color = hex_a_lineal(color)
    return mat


def plastico_transparente(nombre, color):
    """Plástico azul medio transparente: deja pasar la luz y se ve borroso a través."""
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal("#B5C8FF")  # superficie clara: se lee como plástico translúcido
    entrada(bsdf, "Transmission Weight", "Transmission").default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.18
    bsdf.inputs["IOR"].default_value = 1.49
    absorcion = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorcion.inputs["Color"].default_value = hex_a_lineal(color)
    absorcion.inputs["Density"].default_value = 0.18
    nt.links.new(absorcion.outputs["Volume"], nt.nodes.get("Material Output").inputs["Volume"])
    mat.diffuse_color = hex_a_lineal(color)
    return mat


def tinta(nombre, color):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(color)
    bsdf.inputs["Roughness"].default_value = 0.55
    mat.diffuse_color = hex_a_lineal(color)
    return mat


# ---------- Escena ----------
def crear_piso():
    # fondo infinito: el piso sube en curva atrás (se ve en las tomas bajas)
    pared_y, radio, ancho = 8.0, 6.0, 80.0
    perfil = [(y, 0.0) for y in (-40.0, 0.0, pared_y - radio)]
    for i in range(1, 32):
        a = i / 32 * math.pi / 2
        perfil.append((pared_y - radio + radio * math.sin(a), radio - radio * math.cos(a)))
    perfil += [(pared_y, radio + 40.0)]
    bm = bmesh.new()
    filas = [[bm.verts.new((x, y, z)) for x in (-ancho / 2, 0.0, ancho / 2)] for y, z in perfil]
    for a, b in zip(filas, filas[1:]):
        for j in range(2):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Piso")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Piso", me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("Fondo gris")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(COLOR_FONDO)
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    return ob


def configurar_mundo():
    mundo = bpy.data.worlds.get("Estudio") or bpy.data.worlds.new("Estudio")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes.get("Background")
    fondo.inputs["Color"].default_value = (1, 1, 1, 1)
    fondo.inputs["Strength"].default_value = 0.45


def configurar_render():
    escena = bpy.context.scene
    escena.render.resolution_x, escena.render.resolution_y = RESOLUCION
    escena.render.engine = "CYCLES"
    escena.cycles.samples = MUESTRAS
    escena.cycles.use_denoising = True
    escena.cycles.use_adaptive_sampling = True
    escena.cycles.max_bounces = 16
    escena.cycles.transmission_bounces = 12
    escena.view_settings.view_transform = "Standard"
    escena.view_settings.look = "None"
    escena.render.image_settings.file_format = "PNG"
    escena.render.filepath = "//teclas"


def crear_pared():
    """Pared del fondo, lejos de las teclas: con una luz que la recorre, no un blanco infinito."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
    me = bpy.data.meshes.new("Pared")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Pared", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 2.6, 0)  # cerca: recibe las sombras de las teclas
    ob.rotation_euler = (math.pi / 2, 0, 0)
    mat = bpy.data.materials.new("Pared gris")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(COLOR_PARED)
    bsdf.inputs["Roughness"].default_value = 0.95
    me.materials.append(mat)
    return ob


def apretado(t):
    """Recorrido de una tecla (0 = arriba, 1 = a fondo) en el tiempo t de su pulsación (0-1):
    baja rápido, se queda un instante y vuelve con un rebote chiquito."""
    if t <= 0 or t >= 1:
        return 0.0
    if t < 0.18:                       # baja
        k = t / 0.18
        return k * k * (3 - 2 * k)
    if t < 0.38:                       # queda abajo
        return 1.0
    k = (t - 0.38) / 0.62              # sube y rebota apenas
    return (1 - k) ** 2 * math.cos(k * math.pi * 1.5) if k < 1 else 0.0


def salto_con_anticipacion(t):
    """(alto, estiramiento) de un salto en el tiempo t (0-1): primero se agacha (anticipación),
    sale estirándose, cae y se aplasta apenas al aterrizar, con un rebote chiquito."""
    if t <= 0 or t >= 1:
        return 0.0, 0.0
    if t < 0.18:                                    # se agacha
        k = math.sin(math.pi / 2 * t / 0.18)
        return -0.12 * k, -0.05 * k
    if t < 0.64:                                    # salta
        u = (t - 0.18) / 0.46
        return -0.12 * (1 - u) + math.sin(math.pi * u), 0.07 * math.sin(math.pi * u)
    v = (t - 0.64) / 0.36                           # aterriza y rebota
    golpe = math.sin(math.pi * v) * (1 - v)
    return -0.1 * golpe, -0.07 * golpe


# ---------- Sonido: se genera acá mismo, sin archivos externos ----------
TASA = 48000


class Pista:
    """Una pista estéreo en memoria donde se suman los sonidos en su segundo exacto."""

    def __init__(self, segundos):
        self.n = int(segundos * TASA)
        self.izq = array.array("f", bytes(4 * self.n))
        self.der = array.array("f", bytes(4 * self.n))

    def sumar(self, inicio, muestras, paneo=0.0):
        """paneo: -1 izquierda … 1 derecha."""
        gi = math.cos((paneo + 1) * math.pi / 4)
        gd = math.sin((paneo + 1) * math.pi / 4)
        i0 = int(inicio * TASA)
        for k, m in enumerate(muestras):
            i = (i0 + k) % self.n          # lo que pasa del final vuelve al principio: loop
            self.izq[i] += m * gi
            self.der[i] += m * gd

    def guardar(self, ruta):
        pico = max(1e-6, max(max(map(abs, self.izq)), max(map(abs, self.der))))
        g = min(1.0, 0.92 / pico) * VOLUMEN
        datos = array.array("h")
        for a, b in zip(self.izq, self.der):
            datos.append(int(max(-1, min(1, a * g)) * 32767))
            datos.append(int(max(-1, min(1, b * g)) * 32767))
        with wave.open(ruta, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(TASA)
            w.writeframes(datos.tobytes())


def click(azar, fuerza=1.0, tono=1.0):
    """Click de tecla mecánica: un chasquido agudo y corto más el "thock" grave del plástico."""
    largo = int(0.07 * TASA)
    f1 = 280 * tono * azar.uniform(0.92, 1.08)     # cuerpo de la tecla
    f2 = 1900 * tono * azar.uniform(0.9, 1.1)      # resonancia del plástico
    previo, out = 0.0, []
    for k in range(largo):
        t = k / TASA
        ruido = azar.uniform(-1, 1)
        agudo = (ruido - previo) * math.exp(-t / 0.0025)   # ruido filtrado, muy corto
        previo = ruido
        cuerpo = math.sin(2 * math.pi * f1 * t) * math.exp(-t / 0.018)
        brillo = math.sin(2 * math.pi * f2 * t) * math.exp(-t / 0.006)
        out.append(fuerza * (0.55 * agudo + 0.5 * cuerpo + 0.18 * brillo))
    return out


def golpe_suave(azar, fuerza=1.0):
    """Aterrizaje: un toc grave y redondo."""
    f = 150 * azar.uniform(0.9, 1.1)
    return [fuerza * math.sin(2 * math.pi * f * (k / TASA)) * math.exp(-(k / TASA) / 0.03)
            for k in range(int(0.12 * TASA))]


def pop(azar, fuerza=1.0):
    """La letra que aparece: un "pop" que sube de tono."""
    out = []
    fase = 0.0
    for k in range(int(0.06 * TASA)):
        t = k / TASA
        fase += 2 * math.pi * (700 + 9000 * t) / TASA
        out.append(fuerza * math.sin(fase) * math.sin(math.pi * t / 0.06) ** 2)
    return out


def main():
    limpiar_escena()
    escena = bpy.context.scene
    azar = random.Random(7)

    blanco = plastico("PBT blanco", COLOR_BLANCO)
    azul = plastico("PBT azul", COLOR_AZUL)
    azul_transp = plastico_transparente("Azul transparente", COLOR_AZUL)
    tinta_oscura = tinta("Letra oscura", COLOR_LETRA_OSCURA)
    tinta_clara = tinta("Letra clara", COLOR_LETRA_CLARA)

    # las teclas se arman acostadas y después se paran todas juntas, de frente a la cámara
    teclado = bpy.data.objects.new("Teclado", None)
    escena.collection.objects.link(teclado)
    grupos, posiciones = {}, {}
    paso = TECLA + SEPARACION
    columnas = len(FILAS[0])
    for f, fila in enumerate(FILAS):
        for c, caracter in enumerate(fila):
            x = (c - (columnas - 1) / 2) * paso + f * CORRIMIENTO_FILA - CORRIMIENTO_FILA / 2
            y = ((len(FILAS) - 1) / 2 - f) * paso
            grupo = bpy.data.objects.new("Pulsador " + caracter, None)
            escena.collection.objects.link(grupo)
            grupo.location = (x, y, 0)
            grupo.parent = teclado
            grupos[caracter] = grupo
            posiciones[caracter] = (f, c, x, y)
            partes = []
            t = tecla("Tecla " + caracter)
            partes.append(t)
            if caracter == TRANSPARENTE:
                t.data.materials.append(azul_transp)
                if VASTAGO:
                    partes.append(vastago(0, 0, azul_transp))
            else:
                t.data.materials.append(azul if caracter in AZULES else blanco)
            le = letra(caracter, "Letra " + caracter)
            le.location = (0, 0, ALTO * 0.975 + 0.004)
            le.data.materials.append(tinta_clara if caracter in AZULES else tinta_oscura)
            partes.append(le)
            for p in partes:
                p.location = (0, 0, p.location.z)
                p.parent = grupo
    # parado: la cara de las letras mira a la cámara (-Y), la fila de arriba arriba
    teclado.rotation_euler = (math.pi / 2, 0, 0)
    teclado.location = (0, ALTO / 2, 0)
    crear_pared()

    def en_mundo(caracter):
        _, _, x, y = posiciones[caracter]
        return Vector((x, ALTO / 2, y))

    # la palabra que se escribe, arriba del teclado: letras 3D de plástico azul
    palabra = []
    avance = 0.62 * TAMANO_PALABRA
    alto_palabra = paso + 0.55 + 0.45 * TAMANO_PALABRA
    for i, caracter in enumerate(PALABRA):
        curva = bpy.data.curves.new("Palabra " + caracter, type="FONT")
        curva.body = caracter
        curva.size = TAMANO_PALABRA
        curva.align_x, curva.align_y = "CENTER", "CENTER"
        curva.extrude = 0.08
        curva.bevel_depth = 0.025
        curva.bevel_resolution = 4
        fuente = buscar_fuente()
        if fuente:
            curva.font = bpy.data.fonts.load(fuente, check_existing=True)
        curva.materials.append(azul if i else azul)
        ob = bpy.data.objects.new("Palabra " + caracter, curva)
        escena.collection.objects.link(ob)
        ob.location = ((i - (len(PALABRA) - 1) / 2) * avance, -0.05, alto_palabra)
        ob.rotation_euler = (math.pi / 2, 0, 0)
        palabra.append(ob)
    # cursor de texto que titila después de la última letra escrita
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(0.07, 0.07, 0.78 * TAMANO_PALABRA), verts=bm.verts)
    me = bpy.data.meshes.new("Cursor")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(azul)
    cursor = bpy.data.objects.new("Cursor", me)
    escena.collection.objects.link(cursor)

    # cámara de frente, apenas desde la derecha y arriba, como la referencia
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 112
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    centro = Vector((0.05, 0, alto_palabra * 0.45))
    a = math.radians(GIRO_CAMARA)
    cam.location = centro + Vector((math.sin(a), -math.cos(a), 0.16)).normalized() * 25
    cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, energia, pos, tam, color=(1, 1, 1), mira=None):
        datos = bpy.data.lights.new(nombre, "AREA")
        datos.energy = energia
        datos.color = color
        datos.size = tam
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        ob.location = pos
        destino = Vector(mira) if mira else centro
        ob.rotation_euler = (destino - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        ob.visible_camera = False
        return ob

    # principal arriba a la izquierda y adelante: sombras hacia abajo a la derecha, en la pared
    luz("Softbox", 900, (-7, -8, 7), 3.2)
    luz("Relleno", 200, (8, -8, 1), 8, (0.96, 0.97, 1.0))
    pared = luz("Luz pared", 110, (-3, 0.5, 4.5), 8, mira=(-1.5, 2.6, 2.5))
    pared.data.spread = math.radians(120)
    # contraluz detrás de la tecla transparente (sólo a ella, con light linking)
    pa = en_mundo(TRANSPARENTE)
    contra = luz("Contraluz", 60, pa + Vector((-0.9, 2.75, 1.0)), 3, mira=pa + Vector((0, -0.25, -0.5)))
    solo_transp = bpy.data.collections.new("Solo tecla transparente")
    solo_transp.objects.link(bpy.data.objects["Tecla " + TRANSPARENTE])
    try:
        contra.light_linking.receiver_collection = solo_transp
    except AttributeError:
        pass

    # sombras de una ventana con persiana cruzando la pared, en diagonal
    sol = bpy.data.lights.new("Sol ventana", "SUN")
    sol.energy = 1.6
    sol.angle = math.radians(2.5)
    sol.color = (1.0, 0.97, 0.92)
    sol_ob = bpy.data.objects.new("Sol ventana", sol)
    escena.collection.objects.link(sol_ob)
    direccion = Vector((0.55, 1.0, -0.45)).normalized()
    sol_ob.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
    for k in range(-12, 40):  # listones que sólo proyectan sombra (la cámara no los ve)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(34, 0.05, 0.22), verts=bm.verts)
        me = bpy.data.meshes.new("Liston")
        bm.to_mesh(me)
        bm.free()
        liston = bpy.data.objects.new("Liston", me)
        escena.collection.objects.link(liston)
        liston.location = Vector((-2.0, -3.0, 3.5)) + Vector((0, 0, k * 0.55))
        liston.rotation_euler = (0, math.radians(-28), 0)
        for prop in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter"):
            setattr(liston, prop, False)
    solo_pared = bpy.data.collections.new("Solo pared")
    solo_pared.objects.link(bpy.data.objects["Pared"])
    try:
        sol_ob.light_linking.receiver_collection = solo_pared
    except AttributeError:
        pass

    configurar_mundo()
    configurar_render()
    escena.render.fps = FPS
    escena.frame_start, escena.frame_end = 1, FPS * DURACION

    # ---------- Animación ----------
    total = FPS * DURACION
    # quién se aprieta y cuándo: la palabra y, al final, todas juntas (con un toque de azar)
    pulsaciones = {c: [] for c in grupos}
    for caracter, t0 in zip(PALABRA, TIEMPOS_LETRAS):
        pulsaciones[caracter].append((t0, 1.0))
    for c in grupos:
        pulsaciones[c].append((TODAS_JUNTAS + azar.uniform(0, 0.06), 1.0))
    # las vecinas acusan el golpe: se hunden un poco, un instante después (overlapping)
    vecinas = {c: [] for c in grupos}
    for c, lista in pulsaciones.items():
        fc, cc, xc, yc = posiciones[c]
        for t0, _ in lista:
            if t0 >= TODAS_JUNTAS:
                continue
            for d, (fd, cd, xd, yd) in posiciones.items():
                dist = math.hypot(xd - xc, yd - yc)
                if d != c and dist < 1.4:
                    vecinas[d].append((t0 + 0.045, 0.22 * (1.4 - dist) / 0.4 if dist > 1.0 else 0.22))

    prefs = bpy.context.preferences.edit
    interp = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for caracter, g in grupos.items():
            f, c, _, _ = posiciones[caracter]
            base = g.location.z
            inicio_salto = 0.12 + 0.075 * c + 0.06 * f   # ola de izquierda a derecha
            for fr in range(total + 1):
                seg = fr / FPS
                alto, estira = salto_con_anticipacion((seg - inicio_salto) / 0.8)
                presion = max([fuerza * apretado((seg - t0) / 0.32)
                               for t0, fuerza in pulsaciones[caracter] + vecinas[caracter]] or [0.0])
                g.location.z = base + SALTO * alto - RECORRIDO * presion
                g.rotation_euler = (0.16 * max(alto, 0.0), 0, 0)
                sz = 1 + estira
                sxy = 1 / math.sqrt(sz)
                g.scale = (sxy, sxy, sz)
                g.keyframe_insert("location", index=2, frame=fr + 1)
                g.keyframe_insert("rotation_euler", index=0, frame=fr + 1)
                g.keyframe_insert("scale", frame=fr + 1)

        # la palabra: cada letra aparece con un "pop" al apretar su tecla y se va al final
        def escala_letra(seg, t_aparece, t_se_va):
            if seg < t_aparece:
                return 0.0
            k = (seg - t_aparece) / 0.22
            entrada = 1.0 if k >= 1 else math.sin(k * math.pi * 0.62) / math.sin(0.62 * math.pi) * (1 + 0.18 * math.sin(k * math.pi))
            if seg < t_se_va:
                return entrada
            k2 = (seg - t_se_va) / 0.18
            return 0.0 if k2 >= 1 else entrada * (1 - k2 * k2) * (1 + 0.12 * math.sin(k2 * math.pi))

        for i, ob in enumerate(palabra):
            t_ap = TIEMPOS_LETRAS[i] + 0.05
            t_va = TODAS_JUNTAS + 0.12 + 0.05 * (len(palabra) - 1 - i)
            for fr in range(total + 1):
                e = escala_letra(fr / FPS, t_ap, t_va)
                ob.scale = (e, e, e)
                ob.keyframe_insert("scale", frame=fr + 1)

        # cursor: va detrás de la última letra escrita y titila cuando no se escribe
        for fr in range(total + 1):
            seg = fr / FPS
            escritas = sum(1 for t in TIEMPOS_LETRAS if seg >= t + 0.05)
            if seg >= TODAS_JUNTAS + 0.12:
                escritas = 0
            x = (escritas - (len(PALABRA) - 1) / 2 - 0.5) * avance + 0.04
            escribiendo = any(0 <= seg - t < 0.5 for t in TIEMPOS_LETRAS)
            visible = escribiendo or (int(seg / 0.5) % 2 == 0)
            cursor.location = (x, -0.05, alto_palabra)
            v = 1.0 if visible and seg > 1.5 else 0.0
            cursor.scale = (v, v, v)
            cursor.keyframe_insert("location", frame=fr + 1)
            cursor.keyframe_insert("scale", frame=fr + 1)
    finally:
        prefs.keyframe_new_interpolation_type = interp

    # ---------- Sonido ----------
    pista = Pista(DURACION)
    for caracter, g in grupos.items():
        f, c, x, _ = posiciones[caracter]
        paneo = max(-1, min(1, x / 5))
        inicio_salto = 0.12 + 0.075 * c + 0.06 * f
        pista.sumar(inicio_salto + 0.8 * 0.64, golpe_suave(azar, 0.35), paneo)  # aterriza
        for t0, fuerza in pulsaciones[caracter]:
            masiva = t0 >= TODAS_JUNTAS
            f_click = 0.5 if masiva else 1.0
            pista.sumar(t0 + 0.02, click(azar, f_click * fuerza), paneo)               # baja
            pista.sumar(t0 + 0.32 * 0.4, click(azar, 0.35 * f_click, 1.25), paneo)     # vuelve
    for i, t in enumerate(TIEMPOS_LETRAS):
        pista.sumar(t + 0.06, pop(azar, 0.22), (i - 2.5) / 4)
    for i in range(len(PALABRA)):
        pista.sumar(TODAS_JUNTAS + 0.12 + 0.05 * (len(PALABRA) - 1 - i), pop(azar, 0.12), 0)
    carpeta = bpy.path.abspath("//") if bpy.data.filepath else (bpy.app.tempdir or "/tmp")
    ruta_audio = os.path.join(carpeta, "teclas_tregua_sonido.wav")
    pista.guardar(ruta_audio)
    print("Sonido guardado en", ruta_audio)
    try:
        editor = escena.sequence_editor_create()
        for s in list(editor.sequences_all):
            editor.sequences.remove(s)
        editor.sequences.new_sound("Sonido", ruta_audio, 1, 1)
        escena.render.ffmpeg.audio_codec = "AAC"
        escena.render.ffmpeg.audio_bitrate = 192
    except (AttributeError, RuntimeError, TypeError):
        pass  # Blender 5 cambió el editor de video: el WAV queda al lado del .blend
    escena.frame_set(1)


main()
