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


def tecla(nombre):
    """Tecla de perfil bajo: paredes en talud, borde redondeado y un plato arriba, apenas
    hundido, con un escalón suave (como la referencia)."""
    m = TECLA / 2
    h = ALTO
    # (z, medio lado, radio de esquina) de abajo hacia arriba
    perfil = [
        (0.0, m, 0.10), (0.03, m, 0.10), (0.08, m * 0.995, 0.11),
        (h * 0.70, m * 0.90, 0.14), (h * 0.86, m * 0.86, 0.15), (h * 0.95, m * 0.80, 0.16),
        (h, m * 0.74, 0.18),                       # borde de arriba
        (h * 0.985, m * 0.70, 0.15),               # escalón hacia el plato
        (h * 0.975, m * 0.62, 0.13), (h * 0.97, m * 0.3, 0.13),
    ]
    bm = bmesh.new()
    anillos = [[bm.verts.new(p) for p in anillo_redondeado(lado, r, z)] for z, lado, r in perfil]
    n = len(anillos[0])
    for a, b in zip(anillos, anillos[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    centro = bm.verts.new((0, 0, h * 0.968))
    for k in range(n):
        bm.faces.new((anillos[-1][k], anillos[-1][(k + 1) % n], centro))
    bm.faces.new(list(reversed(anillos[0])))  # base cerrada
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
    """Cruz del vástago (stem) debajo de la tecla, que se ve a través del plástico."""
    for nombre, (sx, sy) in (("Vastago X", (0.28, 0.08)), ("Vastago Y", (0.08, 0.28))):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, ALTO * 0.55), verts=bm.verts)
        me = bpy.data.meshes.new(nombre)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        ob = bpy.data.objects.new(nombre, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = (x, y, ALTO * 0.35)


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
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    me = bpy.data.meshes.new("Piso")
    bm.to_mesh(me)
    bm.free()
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


def main():
    limpiar_escena()
    escena = bpy.context.scene

    blanco = plastico("PBT blanco", COLOR_BLANCO)
    azul = plastico("PBT azul", COLOR_AZUL, 0.38)
    azul_transp = plastico_transparente("Azul transparente", COLOR_AZUL)
    tinta_oscura = tinta("Letra oscura", COLOR_LETRA_OSCURA)
    tinta_clara = tinta("Letra clara", COLOR_LETRA_CLARA)

    paso = TECLA + SEPARACION
    columnas = len(FILAS[0])
    for f, fila in enumerate(FILAS):
        for c, caracter in enumerate(fila):
            x = (c - (columnas - 1) / 2) * paso
            y = ((len(FILAS) - 1) / 2 - f) * paso
            t = tecla("Tecla " + caracter)
            t.location = (x, y, 0)
            if caracter == TRANSPARENTE:
                t.data.materials.append(azul_transp)
                vastago(x, y, azul)  # se ve a través: el vástago en cruz de la tecla
            else:
                t.data.materials.append(azul if caracter in AZULES else blanco)
            le = letra(caracter, "Letra " + caracter)
            le.location = (x, y, ALTO * 0.975 + 0.004)
            le.data.materials.append(tinta_clara if caracter in AZULES else tinta_oscura)
    crear_piso()

    # cámara casi cenital, lente larga: como la foto de referencia
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 150
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    centro = Vector((0, 0, ALTO * 0.5))
    cam.location = centro + Vector((0, -0.16, 1)).normalized() * 19
    cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, energia, pos, tam, color=(1, 1, 1)):
        datos = bpy.data.lights.new(nombre, "AREA")
        datos.energy = energia
        datos.color = color
        datos.size = tam
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (centro - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        ob.visible_camera = False
        return ob

    # softbox grande arriba a la izquierda: sombras suaves hacia abajo a la derecha
    # dos softbox: uno grande y alto, centrado (fondo parejo) y uno arriba a la izquierda
    # que da la dirección de las sombras, como en la referencia
    luz("Cenital", 380, (0, 0, 14), 24)
    luz("Softbox", 320, (-3, 2.5, 8), 6)
    luz("Relleno", 90, (5, -4, 6), 6, (0.96, 0.97, 1.0))
    # contraluz baja detrás: hace brillar la tecla transparente
    contra = luz("Contraluz", 320, (-1.5, 5, 2), 3)
    # sólo ilumina la tecla transparente (light linking): no aclara el fondo de atrás
    solo_transp = bpy.data.collections.new("Solo tecla transparente")
    solo_transp.objects.link(bpy.data.objects["Tecla " + TRANSPARENTE])
    try:
        contra.light_linking.receiver_collection = solo_transp
    except AttributeError:
        pass

    configurar_mundo()
    configurar_render()


main()
