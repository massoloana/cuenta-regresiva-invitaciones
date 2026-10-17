"""
Cinta Tregua Estudio — escena para Blender (3.6 o 4.x).

Cómo usarlo:
  1. Abrí Blender, andá a la pestaña "Scripting".
  2. Text > Open… y elegí este archivo (o pegalo en un texto nuevo).
  3. Apretá "Run Script" (▶). Borra la escena actual y arma todo de cero.
  4. Para ver la animación: barra espaciadora en el viewport (modo "Rendered" para ver colores).
  5. Para el video: Render > Render Animation. Sale un MP4 al lado del .blend
     (guardá el .blend antes) o en la carpeta temporal si no lo guardaste.

Qué arma:
  - Fondo naranja liso (exacto en cámara; la luz que rebota es neutra para no teñir la cinta).
  - Una cinta azul enrollada en hélice, en diagonal, con "TREGUA — ESTUDIO →" y un
    anillo de puntos en blanco, en geometría real (no es una imagen).
  - La cinta "corre": un movimiento de tornillo hace que la hélice quede en su lugar
    mientras el texto avanza. El loop es perfecto (frame 1 = frame final + 1).

Todo lo ajustable está en PARÁMETROS.
"""

import math

import bmesh
import bpy
from mathutils import Vector

# ------------------------------------------------------------------ PARÁMETROS
TEXTO = "TREGUA — ESTUDIO →"
FONT_PATH = ""            # ruta a un .ttf/.otf; vacío = tipografía por defecto de Blender

COLOR_FONDO = "#FF6B1F"   # naranja
COLOR_CINTA = "#1F3FE0"   # azul
COLOR_TEXTO = "#FFFFFF"   # blanco

ANCHO = 1.0               # ancho de la cinta
RADIO = 2.3               # radio de la hélice
PASO = 2.7                # avance por vuelta (tiene que ser mayor que ANCHO para no chocarse)
VUELTAS = 12              # vueltas totales (las puntas quedan fuera de cuadro)
ALTO_TEXTO = 0.62         # tamaño del texto (cuerpo de la fuente)
ESPACIO_MIN = 0.45        # separación mínima entre repeticiones

FPS = 30
FRAMES_POR_VUELTA = 240   # 8 s por vuelta: más alto = corre más lento
RESOLUCION = (1920, 1080)
MOTOR = "CYCLES"          # "CYCLES" (más lindo) o el nombre de EEVEE de tu versión
MUESTRAS = 96
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


def material(nombre, color_hex, rugosidad):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(color_hex)
    bsdf.inputs["Roughness"].default_value = rugosidad
    mat.diffuse_color = hex_a_lineal(color_hex)  # color en el viewport sólido
    return mat


# ---------- Hélice: eje X local; s = largo recorrido sobre la cinta ----------
LARGO_VUELTA = math.hypot(2 * math.pi * RADIO, PASO)


def marco(s):
    """Centro y ejes (T a lo largo, B a lo ancho, N hacia afuera) en el punto s de la cinta."""
    th = 2 * math.pi * s / LARGO_VUELTA
    c = Vector((PASO * s / LARGO_VUELTA, RADIO * math.cos(th), RADIO * math.sin(th)))
    t = Vector((PASO / (2 * math.pi), -RADIO * math.sin(th), RADIO * math.cos(th))).normalized()
    n = Vector((0.0, math.cos(th), math.sin(th)))
    b = n.cross(t).normalized()  # T × B = N: lo que mira hacia afuera no queda espejado
    return c, t, b, n


def enrollar(bm, separacion=0.0):
    """Lleva un mesh plano (x = largo, y = ancho, z = altura) a la superficie de la hélice."""
    for v in bm.verts:
        c, _, b, n = marco(v.co.x)
        v.co = c + b * v.co.y + n * (v.co.z + separacion)


# ---------- Tramo de texto plano ----------
def mesh_de_texto():
    curva = bpy.data.curves.new("TextoTramo", type="FONT")
    curva.body = TEXTO
    curva.size = ALTO_TEXTO
    curva.align_x = "LEFT"
    curva.align_y = "CENTER"
    curva.resolution_u = 6
    if FONT_PATH:
        curva.font = bpy.data.fonts.load(FONT_PATH, check_existing=True)
    ob = bpy.data.objects.new("TextoTramo", curva)
    bpy.context.scene.collection.objects.link(ob)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(curva)
    return me


def armar_tramo():
    """Devuelve (bmesh del tramo plano, largo del tramo) con texto + anillo de puntos."""
    bm = bmesh.new()
    me = mesh_de_texto()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    x0, x1 = min(xs), max(xs)
    centro_y = (min(ys) + max(ys)) / 2
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-x0, -centro_y, 0)))
    largo_texto = x1 - x0

    # anillo de puntos con uno faltante, como un dial
    r_anillo = ALTO_TEXTO * 0.36
    r_punto = ALTO_TEXTO * 0.075
    cx = largo_texto + ESPACIO_MIN * 0.6 + r_anillo
    for i in range(10):
        if i == 2:
            continue
        a = i / 10 * 2 * math.pi + math.pi / 2
        ret = bmesh.ops.create_circle(bm, cap_ends=True, segments=16, radius=r_punto)
        bmesh.ops.translate(bm, verts=ret["verts"],
                            vec=Vector((cx + math.cos(a) * r_anillo, math.sin(a) * r_anillo, 0)))
    contenido = cx + r_anillo + r_punto

    # cantidad entera de tramos por vuelta, así el loop de la animación es perfecto
    por_vuelta = max(1, int(LARGO_VUELTA // (contenido + ESPACIO_MIN)))
    largo_tramo = LARGO_VUELTA / por_vuelta

    # cortes cada 4 cm para que las letras se curven con la cinta en vez de atravesarla
    paso_corte = 0.04
    k = paso_corte
    while k < largo_tramo:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(k, 0, 0), plane_no=(1, 0, 0))
        k += paso_corte
    return bm, largo_tramo


def crear_texto(padre, mat):
    tramo, largo_tramo = armar_tramo()
    me_tramo = bpy.data.meshes.new("tmp")
    tramo.to_mesh(me_tramo)
    tramo.free()

    total = LARGO_VUELTA * VUELTAS
    n = int(math.ceil(total / largo_tramo))
    bm = bmesh.new()
    inicio = -total / 2
    for i in range(n):
        bm.from_mesh(me_tramo)  # agrega una copia nueva al final de la lista de vértices
        bm.verts.ensure_lookup_table()
        nuevos = bm.verts[len(bm.verts) - len(me_tramo.vertices):]
        bmesh.ops.translate(bm, verts=nuevos, vec=Vector((inicio + i * largo_tramo, 0, 0)))
    bpy.data.meshes.remove(me_tramo)

    enrollar(bm, separacion=0.004)
    me = bpy.data.meshes.new("Texto")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new("Texto", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = padre
    return ob


def crear_cinta(padre, mat):
    total = LARGO_VUELTA * VUELTAS
    pasos = int(total / 0.04)
    bm = bmesh.new()
    filas = []
    for i in range(pasos + 1):
        s = -total / 2 + total * i / pasos
        filas.append([bm.verts.new((s, y, 0.0)) for y in (-ANCHO / 2, 0.0, ANCHO / 2)])
    for a, b in zip(filas, filas[1:]):
        for j in range(2):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    enrollar(bm)
    bm.normal_update()
    # que las normales miren hacia afuera de la hélice (donde va el texto)
    bm.faces.ensure_lookup_table()
    _, _, _, n = marco(-total / 2)
    if bm.faces[0].normal.dot(n) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Cinta")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new("Cinta", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = padre
    sol = ob.modifiers.new("Grosor", "SOLIDIFY")
    sol.thickness = 0.012
    sol.offset = -1.0  # crece hacia adentro: la cara impresa queda donde está el texto
    return ob


def configurar_mundo():
    mundo = bpy.data.worlds.get("Mundo Tregua") or bpy.data.worlds.new("Mundo Tregua")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    nt = mundo.node_tree
    nt.nodes.clear()
    salida = nt.nodes.new("ShaderNodeOutputWorld")
    camino = nt.nodes.new("ShaderNodeLightPath")
    mezcla = nt.nodes.new("ShaderNodeMixShader")
    fondo_cam = nt.nodes.new("ShaderNodeBackground")
    fondo_luz = nt.nodes.new("ShaderNodeBackground")
    fondo_cam.inputs["Color"].default_value = hex_a_lineal(COLOR_FONDO)
    fondo_cam.inputs["Strength"].default_value = 1.0
    # la luz ambiente es casi neutra (apenas cálida) para que el azul no se ensucie
    fondo_luz.inputs["Color"].default_value = (1.0, 0.93, 0.88, 1.0)
    fondo_luz.inputs["Strength"].default_value = 0.55
    nt.links.new(camino.outputs["Is Camera Ray"], mezcla.inputs["Fac"])
    nt.links.new(fondo_luz.outputs["Background"], mezcla.inputs[1])
    nt.links.new(fondo_cam.outputs["Background"], mezcla.inputs[2])
    nt.links.new(mezcla.outputs["Shader"], salida.inputs["Surface"])
    mundo.color = hex_a_lineal(COLOR_FONDO)[:3]


def configurar_render():
    escena = bpy.context.scene
    escena.render.resolution_x, escena.render.resolution_y = RESOLUCION
    escena.render.fps = FPS
    escena.frame_start = 1
    escena.frame_end = FRAMES_POR_VUELTA
    try:
        escena.render.engine = MOTOR
    except TypeError:
        escena.render.engine = "CYCLES"
    if escena.render.engine == "CYCLES":
        escena.cycles.samples = MUESTRAS
        escena.cycles.use_denoising = True
    # "Standard" deja el naranja y el azul exactos (AgX/Filmic los lavan)
    escena.view_settings.view_transform = "Standard"
    escena.view_settings.look = "None"
    try:
        escena.render.image_settings.file_format = "FFMPEG"
        escena.render.ffmpeg.format = "MPEG4"
        escena.render.ffmpeg.codec = "H264"
        escena.render.ffmpeg.constant_rate_factor = "HIGH"
    except (TypeError, AttributeError):
        pass  # si tu versión no lo acepta, elegí FFmpeg/MPEG-4 en Output Properties
    escena.render.filepath = "//cinta_tregua_"


def main():
    limpiar_escena()
    escena = bpy.context.scene

    # Orientación: el eje de la hélice cruza el cuadro en diagonal, de arriba a la izquierda
    # hacia abajo a la derecha, con una leve inclinación hacia cámara
    orient = bpy.data.objects.new("Orientacion", None)
    escena.collection.objects.link(orient)
    orient.rotation_mode = "QUATERNION"
    orient.rotation_quaternion = Vector((1.0, -0.3, -0.78)).to_track_quat("X", "Z")

    # Tornillo: gira y avanza a la vez; la hélice se superpone consigo misma y el texto corre
    tornillo = bpy.data.objects.new("Tornillo", None)
    escena.collection.objects.link(tornillo)
    tornillo.parent = orient
    # claves lineales (velocidad constante); se restaura la preferencia del usuario al final
    prefs = bpy.context.preferences.edit
    interp_original = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        tornillo.rotation_euler = (0, 0, 0)
        tornillo.location = (0, 0, 0)
        tornillo.keyframe_insert("rotation_euler", index=0, frame=1)
        tornillo.keyframe_insert("location", index=0, frame=1)
        tornillo.rotation_euler[0] = 2 * math.pi
        tornillo.location[0] = PASO
        tornillo.keyframe_insert("rotation_euler", index=0, frame=FRAMES_POR_VUELTA + 1)
        tornillo.keyframe_insert("location", index=0, frame=FRAMES_POR_VUELTA + 1)
    finally:
        prefs.keyframe_new_interpolation_type = interp_original

    mat_cinta = material("Cinta azul", COLOR_CINTA, 0.55)
    mat_texto = material("Texto blanco", COLOR_TEXTO, 0.5)
    crear_cinta(tornillo, mat_cinta)
    crear_texto(tornillo, mat_texto)

    # Cámara de frente
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 50
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    cam.location = (0, -19, 0)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    escena.camera = cam

    # Luz principal suave, arriba a la izquierda y de frente
    luz_data = bpy.data.lights.new("Softbox", "AREA")
    luz_data.energy = 2500
    luz_data.size = 8
    luz = bpy.data.objects.new("Softbox", luz_data)
    escena.collection.objects.link(luz)
    luz.location = (-7, -12, 8)
    luz.rotation_euler = (Vector((0, 0, 0)) - luz.location).to_track_quat("-Z", "Y").to_euler()

    configurar_mundo()
    configurar_render()
    escena.frame_set(1)


main()
