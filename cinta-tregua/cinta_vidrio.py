"""
Cinta de vidrio — escena para Blender (3.6 o 4.x). Variante de la cinta Tregua en acrílico.

Cómo usarlo:
  1. Abrí Blender, andá a la pestaña "Scripting".
  2. Text > Open… y elegí este archivo.
  3. Apretá "Run Script". Borra la escena actual y arma todo de cero.
  4. Para ver la animación: modo "Rendered" en el viewport y barra espaciadora.
  5. Para el video: guardá el .blend y Render > Render Animation (sale un MP4 vertical).

Qué arma:
  - Una cinta gruesa de vidrio esmerilado, en espiral vertical de poco más de dos vueltas,
    con degradé rosa → magenta → violeta → lavanda a lo largo y cantos biselados que
    atrapan la luz.
  - Fondo celeste liso que se aclara hacia arriba, lejano y desenfocado.
  - Luz de estudio blanca y suave: un softbox grande arriba y tiras a los costados que
    dibujan los bordes brillantes del vidrio.
  - Movimiento tranquilo en loop: la espiral gira despacio, flota y se mece.

Todo lo ajustable está en PARÁMETROS.
"""

import math

import bmesh
import bpy
from mathutils import Euler, Vector

# ------------------------------------------------------------------ PARÁMETROS
# Degradé a lo largo de la cinta (de abajo hacia arriba)
DEGRADE = [
    (0.00, "#FF7AD0"),   # rosa
    (0.38, "#E8399C"),   # magenta
    (0.66, "#8B4DFF"),   # violeta
    (1.00, "#7EA2FF"),   # lavanda azulada
]
COLOR_FONDO_ARRIBA = "#E3EEF8"
COLOR_FONDO_ABAJO = "#9FCBF2"

RUGOSIDAD = 0.16          # esmerilado: 0 = vidrio transparente, 0.4 = muy opaco
TINTE = 6.0               # cuánto se satura el color donde el vidrio es más grueso (cantos)
GROSOR = 0.08             # espesor del acrílico
BISEL = 0.018             # chanfle de los cantos (lo que brilla)

ANCHO = 0.95              # ancho de la cinta
RADIO = 1.15              # radio de la espiral
PASO = 2.7                # altura de cada vuelta
VUELTAS = 2.1
INCLINACION = 8           # grados que se inclina la espiral (arriba a la izquierda)

FPS = 30
DURACION_LOOP = 16        # segundos que tarda en dar una vuelta completa
RESOLUCION = (1080, 1920) # vertical, como la referencia
MUESTRAS = 128
FLOTAR = 0.08             # cuánto sube y baja
BALANCEO = 3.0            # grados que se mece
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


# ---------- Material: acrílico esmerilado con degradé y una capa de brillo encima ----------
def material_vidrio():
    mat = bpy.data.materials.new("Vidrio esmerilado")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    entrada(bsdf, "Transmission Weight", "Transmission").default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.49  # acrílico
    disp = entrada(bsdf, "Dispersion")
    if disp:  # Blender 4.2+: separa un poco los colores en los cantos
        disp.default_value = 0.08
    # capa transparente encima: reflejos nítidos sobre el cuerpo esmerilado
    coat = entrada(bsdf, "Coat Weight", "Clearcoat")
    if coat:
        coat.default_value = 0.6
    coat_r = entrada(bsdf, "Coat Roughness", "Clearcoat Roughness")
    if coat_r:
        coat_r.default_value = 0.04

    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    elementos = rampa.color_ramp.elements
    elementos[0].position, elementos[0].color = DEGRADE[0][0], hex_a_lineal(DEGRADE[0][1])
    elementos[1].position, elementos[1].color = DEGRADE[-1][0], hex_a_lineal(DEGRADE[-1][1])
    for pos, col in DEGRADE[1:-1]:
        e = elementos.new(pos)
        e.color = hex_a_lineal(col)
    rampa.color_ramp.interpolation = "EASE"
    nt.links.new(coord.outputs["UV"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], rampa.inputs["Fac"])
    # superficie en tono pastel; el color fuerte lo da el espesor (absorción en volumen), así
    # las caras se ven claras y translúcidas y los cantos, saturados como en el acrílico
    pastel = nt.nodes.new("ShaderNodeMix")
    pastel.data_type = "RGBA"
    pastel.inputs["Factor"].default_value = 0.3
    a_col = next(i for i in pastel.inputs if i.identifier == "A_Color")
    b_col = next(i for i in pastel.inputs if i.identifier == "B_Color")
    res = next(o for o in pastel.outputs if o.identifier == "Result_Color")
    b_col.default_value = (1, 1, 1, 1)
    nt.links.new(rampa.outputs["Color"], a_col)
    nt.links.new(res, bsdf.inputs["Base Color"])
    absorcion = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorcion.inputs["Density"].default_value = TINTE
    nt.links.new(rampa.outputs["Color"], absorcion.inputs["Color"])
    salida = nt.nodes.get("Material Output")
    nt.links.new(absorcion.outputs["Volume"], salida.inputs["Volume"])

    # esmerilado parejo: granito fino que varía la rugosidad
    grano = nt.nodes.new("ShaderNodeTexNoise")
    grano.inputs["Scale"].default_value = 420.0
    grano.inputs["Detail"].default_value = 4.0
    rango = nt.nodes.new("ShaderNodeMapRange")
    rango.inputs["To Min"].default_value = RUGOSIDAD * 0.65
    rango.inputs["To Max"].default_value = RUGOSIDAD * 1.35
    nt.links.new(coord.outputs["Object"], grano.inputs["Vector"])
    nt.links.new(grano.outputs["Fac"], rango.inputs["Value"])
    nt.links.new(rango.outputs["Result"], bsdf.inputs["Roughness"])
    mat.diffuse_color = hex_a_lineal(DEGRADE[2][1])
    return mat


# ---------- Cinta: banda sobre una espiral vertical, con grosor y bisel ----------
def crear_cinta(mat):
    largo_vuelta = math.hypot(2 * math.pi * RADIO, PASO)
    total = largo_vuelta * VUELTAS
    pasos = int(total / 0.025)
    div = 4
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    filas = []
    for i in range(pasos + 1):
        s = total * i / pasos
        th = 2 * math.pi * s / largo_vuelta
        z = PASO * th / (2 * math.pi) - PASO * VUELTAS / 2
        r = RADIO * (1 + 0.06 * math.sin(0.9 * th + 0.4))  # apenas despareja, hecha a mano
        c = Vector((r * math.cos(th), r * math.sin(th), z))
        t = Vector((-r * math.sin(th), r * math.cos(th), PASO / (2 * math.pi))).normalized()
        n = Vector((math.cos(th), math.sin(th), 0.0))
        b = n.cross(t).normalized()
        filas.append([(bm.verts.new(c + b * (-ANCHO / 2 + ANCHO * j / div)), s / total, j / div)
                      for j in range(div + 1)])
    for fa, fb in zip(filas, filas[1:]):
        for j in range(div):
            esquinas = (fa[j], fb[j], fb[j + 1], fa[j + 1])
            cara = bm.faces.new([e[0] for e in esquinas])
            for loop, e in zip(cara.loops, esquinas):
                loop[uv].uv = (e[1], e[2])
    me = bpy.data.meshes.new("CintaVidrio")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new("CintaVidrio", me)
    bpy.context.scene.collection.objects.link(ob)

    sol = ob.modifiers.new("Grosor", "SOLIDIFY")
    sol.thickness = GROSOR
    sol.offset = 0.0
    sol.use_even_offset = True
    bis = ob.modifiers.new("Bisel", "BEVEL")
    bis.width = BISEL
    bis.segments = 2
    bis.limit_method = "ANGLE"
    bis.angle_limit = math.radians(40)
    try:
        bis.harden_normals = True
    except AttributeError:
        pass
    return ob


# ---------- Fondo celeste lejano, con su propio brillo para que el color sea exacto ----------
def crear_fondo():
    me = bpy.data.meshes.new("Fondo")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Fondo", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 22, 0)
    ob.rotation_euler = (math.pi / 2, 0, 0)
    ob.visible_shadow = False

    mat = bpy.data.materials.new("Fondo celeste")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    els = rampa.color_ramp.elements
    els[0].position, els[0].color = 0.3, hex_a_lineal(COLOR_FONDO_ABAJO)
    els[1].position, els[1].color = 0.75, hex_a_lineal(COLOR_FONDO_ARRIBA)
    rampa.color_ramp.interpolation = "EASE"
    emision = nt.nodes.new("ShaderNodeEmission")
    emision.inputs["Strength"].default_value = 1.0
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Y"], rampa.inputs["Fac"])
    nt.links.new(rampa.outputs["Color"], emision.inputs["Color"])
    nt.links.new(emision.outputs["Emission"], salida.inputs["Surface"])
    me.materials.append(mat)
    return ob


def configurar_mundo():
    mundo = bpy.data.worlds.get("Estudio blanco") or bpy.data.worlds.new("Estudio blanco")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes.get("Background")
    fondo.inputs["Color"].default_value = (0.82, 0.89, 1.0, 1.0)  # estudio blanco azulado
    fondo.inputs["Strength"].default_value = 0.6


def configurar_render():
    escena = bpy.context.scene
    escena.render.resolution_x, escena.render.resolution_y = RESOLUCION
    escena.render.fps = FPS
    escena.frame_start = 1
    escena.frame_end = FPS * DURACION_LOOP
    escena.render.engine = "CYCLES"  # el vidrio necesita Cycles
    escena.cycles.samples = MUESTRAS
    escena.cycles.use_denoising = True
    escena.cycles.max_bounces = 16
    escena.cycles.transmission_bounces = 14
    escena.cycles.glossy_bounces = 6
    escena.cycles.transparent_max_bounces = 16
    escena.cycles.caustics_reflective = False
    escena.cycles.caustics_refractive = False
    # "Standard" deja el celeste del fondo y los pasteles tal cual (AgX los agrisa)
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


def main():
    limpiar_escena()
    escena = bpy.context.scene

    pivote = bpy.data.objects.new("Pivote", None)
    escena.collection.objects.link(pivote)
    pivote.rotation_mode = "XYZ"

    cinta = crear_cinta(material_vidrio())
    cinta.parent = pivote
    crear_fondo()

    # Cámara: lente larga, apenas desde arriba
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 85
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 16.0
    cam_data.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    cam.location = (0, -15.6, 3.2)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, energia, pos, tam_x, tam_y, color=(1, 1, 1)):
        datos = bpy.data.lights.new(nombre, "AREA")
        datos.energy = energia
        datos.color = color
        datos.shape = "RECTANGLE"
        datos.size, datos.size_y = tam_x, tam_y
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (Vector((0, 0, 0)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()

    # softbox grande arriba y adelante: brillo amplio y parejo en las caras
    luz("Softbox", 380, (-3, -6, 8), 4, 3)
    # tiras a los costados y atrás: los cantos biselados se encienden
    luz("Tira izquierda", 1100, (-7, 2, 1), 0.6, 9, (0.85, 0.9, 1.0))
    luz("Tira derecha", 1000, (7, 1, 0), 0.6, 9, (1.0, 0.88, 0.95))

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
