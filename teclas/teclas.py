"""
Teclas — escena para Blender (3.6 o 4.x).

Seis teclas de teclado mecánico en dos filas, con las letras en el orden del teclado
(Q W E / A S D). La columna de la izquierda es azul, y la tecla de abajo es de plástico
azul medio transparente. Fondo gris claro, vista casi cenital, como una foto de producto.

Cómo usarlo:
  1. Abrí Blender, andá a la pestaña "Scripting".
  2. Text > Open… y elegí este archivo (la carpeta fuentes/ tiene que estar al lado).
  3. Apretá "Run Script". Borra la escena actual y arma todo de cero.
  4. F12 para la imagen.

Todo lo ajustable está en PARÁMETROS.
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ PARÁMETROS
FILAS = [["Q", "W", "E"], ["A", "S", "D"]]   # orden del teclado
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

# Teclas paradas de frente y animación de apretado
GIRO_CAMARA = 24          # grados que la cámara mira desde la derecha (como la referencia)
COLOR_PARED = "#CFCFCF"   # pared del fondo, con una luz que se nota
FPS = 30
DURACION = 4              # segundos del loop
RECORRIDO = 0.22          # cuánto se hunde una tecla al apretarla (≈ 4 mm, como una tecla real)
ORDEN_APRETADO = ["W", "A", "S", "D", "Q", "E"]       # en qué orden se aprietan
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
    ob.location = (0, 7, 0)
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


def main():
    limpiar_escena()
    escena = bpy.context.scene

    blanco = plastico("PBT blanco", COLOR_BLANCO)
    azul = plastico("PBT azul", COLOR_AZUL)
    azul_transp = plastico_transparente("Azul transparente", COLOR_AZUL)
    tinta_oscura = tinta("Letra oscura", COLOR_LETRA_OSCURA)
    tinta_clara = tinta("Letra clara", COLOR_LETRA_CLARA)

    # las teclas se arman acostadas y después se paran todas juntas, de frente a la cámara
    teclado = bpy.data.objects.new("Teclado", None)
    escena.collection.objects.link(teclado)
    grupos = {}
    paso = TECLA + SEPARACION
    columnas = len(FILAS[0])
    for f, fila in enumerate(FILAS):
        for c, caracter in enumerate(fila):
            x = (c - (columnas - 1) / 2) * paso
            y = ((len(FILAS) - 1) / 2 - f) * paso
            grupo = bpy.data.objects.new("Pulsador " + caracter, None)
            escena.collection.objects.link(grupo)
            grupo.location = (x, y, 0)
            grupo.parent = teclado
            grupos[caracter] = grupo
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
    # parado: la cara de las letras mira a la cámara (-Y), la fila Q W E arriba
    teclado.rotation_euler = (math.pi / 2, 0, 0)
    teclado.location = (0, ALTO / 2, 0)
    crear_pared()

    # cámara de frente, apenas desde la derecha y arriba, como la referencia
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 125
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    centro = Vector((0, 0, 0))
    a = math.radians(GIRO_CAMARA)
    cam.location = centro + Vector((math.sin(a), -math.cos(a), 0.18)).normalized() * 15
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

    # principal arriba a la izquierda y adelante: sombras suaves hacia abajo a la derecha
    luz("Softbox", 520, (-5, -6, 5), 5)
    luz("Relleno", 120, (6, -6, 0), 6, (0.96, 0.97, 1.0))
    # luz en la pared: un círculo suave arriba a la izquierda que se apaga hacia los bordes
    pared = luz("Luz pared", 260, (-2, 1.5, 3.5), 6, mira=(-1, 7, 2))
    pared.data.spread = math.radians(120)
    # contraluz detrás: hace brillar la tecla transparente (sólo a ella, con light linking)
    contra = luz("Contraluz", 60, (-2.5, 3, 0.5), 3, mira=(-1.6, 0, -0.5))
    solo_transp = bpy.data.collections.new("Solo tecla transparente")
    solo_transp.objects.link(bpy.data.objects["Tecla " + TRANSPARENTE])
    try:
        contra.light_linking.receiver_collection = solo_transp
    except AttributeError:
        pass

    configurar_mundo()
    configurar_render()
    escena.render.fps = FPS
    escena.frame_start, escena.frame_end = 1, FPS * DURACION

    # animación: cada tecla se aprieta una vez por loop, en ORDEN_APRETADO, con superposición
    total = FPS * DURACION
    hueco = total / len(ORDEN_APRETADO)
    largo = int(FPS * 0.55)  # cuánto dura una pulsación
    prefs = bpy.context.preferences.edit
    interp = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for i, caracter in enumerate(ORDEN_APRETADO):
            if caracter not in grupos:
                continue
            g = grupos[caracter]
            inicio = int(i * hueco + hueco * 0.15)
            base = g.location.z
            for fr in range(total + 1):
                t = (fr - inicio) / largo
                g.location.z = base - RECORRIDO * apretado(t)
                g.keyframe_insert("location", index=2, frame=fr + 1)
    finally:
        prefs.keyframe_new_interpolation_type = interp
    escena.frame_set(1)


main()
