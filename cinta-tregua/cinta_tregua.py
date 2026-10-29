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
  - Fondo infinito naranja: un papel de estudio lejano (piso que sube en curva a la pared),
    con un círculo de luz detrás de la cinta que se apaga hacia los bordes.
  - Una cinta azul de cartulina (mate, con fibra de papel y canto claro) que cae en espiral
    suelta y despareja, en diagonal: las vueltas cambian de tamaño y separación, el eje se
    curva y la cinta se tuerce sola, como una tira de papel soltada a mano.
  - "TREGUA — ESTUDIO →" y un anillo de puntos impresos en blanco que corren por la cinta.
  - Luz de tarde: principal cálida y rasante desde la izquierda, contra fría que marca
    los cantos, y profundidad de campo suave.
  - Movimiento relajado: el texto se desliza sin apuro, acelerando y frenando suave;
    la cinta respira con el aire y toda la espiral se mece. El loop es perfecto
    (frame 1 = frame final + 1).

Todo lo ajustable está en PARÁMETROS.
"""

import math
import os

import bmesh
import bpy
from mathutils import Euler, Vector

# ------------------------------------------------------------------ PARÁMETROS
TEXTO = "TREGUA — ESTUDIO →"
FONT_PATH = ""            # ruta a un .ttf/.otf; vacío = tipografía por defecto de Blender

COLOR_FONDO = "#FF6B1F"   # naranja
COLOR_CINTA = "#1F3FE0"   # azul
COLOR_TEXTO = "#FFFFFF"   # blanco
COLOR_CANTO = "#EDE7DC"   # el alma clara de la cartulina que se ve en el corte
GROSOR = 0.018            # grosor de la cartulina

# Forma de la espiral (suelta, no perfecta)
ANCHO = 1.0               # ancho de la cinta
RADIO = 2.3               # radio promedio de las vueltas
VARIACION_RADIO = 0.28    # cuánto cambia el tamaño de una vuelta a otra (0 = todas iguales)
PASO = 2.8                # separación promedio entre vueltas
VARIACION_PASO = 0.3      # vueltas más juntas y más separadas (0 = parejas)
CURVA_EJE = 1.3           # cuánto se curva el eje de la espiral (0 = recto)
TORSION = 0.45            # cuánto se tuerce la cinta sola, en radianes (0 = siempre de frente)
VUELTAS = 11
ALTO_TEXTO = 0.62         # tamaño del texto respecto del ancho de la cinta
ESPACIO = 0.7             # separación entre repeticiones del texto

FPS = 30
DURACION_LOOP = 24        # segundos
TRAMOS_POR_LOOP = 2       # cuántas repeticiones del texto avanzan en cada loop (más = más rápido)
RESOLUCION = (1920, 1080)
MOTOR = "CYCLES"          # "CYCLES" (más lindo) o el nombre de EEVEE de tu versión
MUESTRAS = 96

# Movimiento relajado
VARIACION_VELOCIDAD = 0.35  # el texto acelera y frena ±35 %
PULSOS_VELOCIDAD = 2        # cuántas veces acelera y frena en cada loop
VIENTO = 0.45               # cuánto respira la cinta en el aire (0 = quieta)
ESCALA_VIENTO = 3.4         # tamaño de las ondulaciones
BALANCEO = 3.0              # grados que se mece toda la espiral
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


def material(nombre, color_hex, rugosidad):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(color_hex)
    bsdf.inputs["Roughness"].default_value = rugosidad
    mat.diffuse_color = hex_a_lineal(color_hex)  # color en el viewport sólido
    return mat


def ajustar_escala(mat, me):
    """Pone en el material el tamaño real del objeto (ver material_cartulina)."""
    xs, ys, zs = zip(*(v.co for v in me.vertices))
    dims = (max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0, max(zs) - min(zs) or 1.0)
    mat.node_tree.nodes["EscalaObjeto"].inputs[1].default_value = dims


def material_cartulina(nombre, color_hex, rugosidad=0.9, fibra=1.0):
    """Papel grueso mate: fibra fina en relieve, leve variación de tono y un brillo de terciopelo."""
    mat = material(nombre, color_hex, rugosidad)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    spec = entrada(bsdf, "Specular IOR Level", "Specular")
    if spec:
        spec.default_value = 0.25
    sheen = entrada(bsdf, "Sheen Weight", "Sheen")
    if sheen:
        sheen.default_value = 0.35

    coord = nt.nodes.new("ShaderNodeTexCoord")
    # coordenadas "Generated" (de la malla sin deformar) llevadas a metros con el tamaño del
    # objeto: así la fibra queda pegada al papel aunque la cinta se ondule
    escala = nt.nodes.new("ShaderNodeVectorMath")
    escala.name = "EscalaObjeto"
    escala.operation = "MULTIPLY"
    escala.inputs[1].default_value = (1.0, 1.0, 1.0)
    nt.links.new(coord.outputs["Generated"], escala.inputs[0])
    # fibra: ruido fino, un poco estirado en una dirección como el grano del papel
    mapeo = nt.nodes.new("ShaderNodeMapping")
    mapeo.inputs["Scale"].default_value = (1.0, 3.0, 1.0)
    fibra_n = nt.nodes.new("ShaderNodeTexNoise")
    fibra_n.inputs["Scale"].default_value = 70.0
    fibra_n.inputs["Detail"].default_value = 10.0
    poro = nt.nodes.new("ShaderNodeTexNoise")
    poro.inputs["Scale"].default_value = 220.0
    poro.inputs["Detail"].default_value = 2.0
    suma = nt.nodes.new("ShaderNodeMath")
    suma.operation = "ADD"
    relieve = nt.nodes.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.22 * fibra
    relieve.inputs["Distance"].default_value = 0.006
    nt.links.new(escala.outputs["Vector"], mapeo.inputs["Vector"])
    nt.links.new(mapeo.outputs["Vector"], fibra_n.inputs["Vector"])
    nt.links.new(escala.outputs["Vector"], poro.inputs["Vector"])
    nt.links.new(fibra_n.outputs["Fac"], suma.inputs[0])
    nt.links.new(poro.outputs["Fac"], suma.inputs[1])
    nt.links.new(suma.outputs["Value"], relieve.inputs["Height"])
    nt.links.new(relieve.outputs["Normal"], bsdf.inputs["Normal"])

    # manchado muy sutil del pigmento
    mancha = nt.nodes.new("ShaderNodeTexNoise")
    mancha.inputs["Scale"].default_value = 14.0
    tono = nt.nodes.new("ShaderNodeHueSaturation")
    tono.inputs["Color"].default_value = hex_a_lineal(color_hex)
    rampa = nt.nodes.new("ShaderNodeMapRange")
    rampa.inputs["To Min"].default_value = 0.93
    rampa.inputs["To Max"].default_value = 1.05
    nt.links.new(escala.outputs["Vector"], mancha.inputs["Vector"])
    nt.links.new(mancha.outputs["Fac"], rampa.inputs["Value"])
    nt.links.new(rampa.outputs["Result"], tono.inputs["Value"])
    nt.links.new(tono.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


# ---------- Espiral suelta: camino, ejes y largo recorrido ----------
def camino():
    """Puntos a lo largo de la cinta con sus ejes: T a lo largo, B a lo ancho, N hacia afuera.

    Es una espiral alrededor del eje X local, pero despareja: el radio y la separación cambian
    de vuelta en vuelta, el eje se curva y la cinta se tuerce un poco por su cuenta.
    """
    pasos = int(VUELTAS * 1100)
    th_max = 2 * math.pi * VUELTAS
    puntos, ejes = [], []
    for i in range(pasos + 1):
        th = th_max * i / pasos
        x = PASO / (2 * math.pi) * (th + VARIACION_PASO * math.sin(0.31 * th) / 0.31)
        r = RADIO * (1 + VARIACION_RADIO * (0.7 * math.sin(0.23 * th + 1.0) + 0.3 * math.sin(0.71 * th)))
        cy = CURVA_EJE * math.sin(0.11 * th + 0.3)
        cz = CURVA_EJE * 0.7 * math.sin(0.08 * th + 2.1)
        puntos.append(Vector((x, cy + r * math.cos(th), cz + r * math.sin(th))))
        ejes.append(Vector((x, cy, cz)))
    medio = (puntos[0].x + puntos[-1].x) / 2
    for p in puntos + ejes:
        p.x -= medio

    s = 0.0
    marcos = []
    for i, p in enumerate(puntos):
        if i:
            s += (p - puntos[i - 1]).length
        t = (puntos[min(i + 1, pasos)] - puntos[max(i - 1, 0)]).normalized()
        radial = p - ejes[i]
        n = (radial - t * radial.dot(t)).normalized()
        b = n.cross(t)
        # torsión libre: la cinta no queda siempre perfectamente apoyada en la espiral
        giro = TORSION * (math.sin(0.17 * s + 0.8) + 0.5 * math.sin(0.41 * s))
        n = n * math.cos(giro) + b * math.sin(giro)
        b = n.cross(t).normalized()  # T × B = N: lo que mira hacia afuera no queda espejado
        marcos.append((p, b, n, s))
    return marcos


# ---------- Texto impreso: se renderiza una vez a una imagen que se repite en la cinta ----------
def imagen_del_texto():
    """Renderiza "TREGUA — ESTUDIO →" + anillo de puntos a un PNG con transparencia.

    Devuelve (imagen, largo del tramo en metros). La imagen queda guardada dentro del .blend.
    """
    principal = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    tmp = bpy.data.scenes.new("TextoTmp")

    curva = bpy.data.curves.new("TextoTramo", type="FONT")
    curva.body = TEXTO
    curva.size = ALTO_TEXTO * ANCHO
    curva.align_x = "LEFT"
    curva.align_y = "CENTER"
    if FONT_PATH:
        curva.font = bpy.data.fonts.load(FONT_PATH, check_existing=True)
    texto = bpy.data.objects.new("TextoTramo", curva)
    principal.collection.objects.link(texto)  # un momento en la escena principal, para convertirlo
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(texto.evaluated_get(deps))
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    largo_texto = max(xs) - min(xs)

    # anillo de puntos con uno faltante, como un dial
    alto = ALTO_TEXTO * ANCHO
    r_anillo, r_punto = alto * 0.36, alto * 0.075
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.translate(bm, verts=bm.verts,
                        vec=Vector((ESPACIO / 2 - min(xs), -(min(ys) + max(ys)) / 2, 0)))
    cx = ESPACIO / 2 + largo_texto + ESPACIO * 0.6 + r_anillo
    for i in range(10):
        if i == 2:
            continue
        a = i / 10 * 2 * math.pi + math.pi / 2
        ret = bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=r_punto)
        bmesh.ops.translate(bm, verts=ret["verts"],
                            vec=Vector((cx + math.cos(a) * r_anillo, math.sin(a) * r_anillo, 0)))
    largo_tramo = cx + r_anillo + r_punto + ESPACIO / 2
    bm.to_mesh(me)
    bm.free()
    bpy.data.objects.remove(texto, do_unlink=True)
    bpy.data.curves.remove(curva)
    plano = bpy.data.objects.new("TramoPlano", me)
    tmp.collection.objects.link(plano)

    cam_data = bpy.data.cameras.new("CamTramo")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = largo_tramo
    cam_data.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("CamTramo", cam_data)
    tmp.collection.objects.link(cam)
    cam.location = (largo_tramo / 2, 0, 5)
    tmp.camera = cam

    ancho_px = 6144
    # Cycles con un material de emisión blanco: funciona igual con o sin placa de video
    blanco = bpy.data.materials.new("TintaTmp")
    blanco.use_nodes = True
    nt = blanco.node_tree
    nt.nodes.clear()
    emision = nt.nodes.new("ShaderNodeEmission")
    salida_mat = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emision.outputs["Emission"], salida_mat.inputs["Surface"])
    me.materials.append(blanco)
    tmp.render.engine = "CYCLES"
    tmp.cycles.samples = 8
    tmp.cycles.use_denoising = False
    tmp.render.resolution_x = ancho_px
    tmp.render.resolution_y = max(8, round(ancho_px * ANCHO / largo_tramo))
    tmp.render.resolution_percentage = 100
    tmp.render.film_transparent = True
    tmp.view_settings.view_transform = "Standard"
    tmp.render.image_settings.file_format = "PNG"
    tmp.render.image_settings.color_mode = "RGBA"
    ruta = os.path.join(bpy.app.tempdir or "/tmp", "tregua_tramo.png")
    tmp.render.filepath = ruta
    bpy.ops.render.render(write_still=True, scene=tmp.name)

    img = bpy.data.images.load(ruta, check_existing=False)
    img.name = "Texto impreso"
    img.pack()
    for ob in list(tmp.collection.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    bpy.data.meshes.remove(me)
    bpy.data.materials.remove(blanco)
    bpy.data.scenes.remove(tmp)
    if bpy.context.window:
        bpy.context.window.scene = principal
    return img, largo_tramo


def agregar_texto_impreso(mat, img, largo_tramo):
    """Mezcla la tinta blanca sobre la cartulina; devuelve el nodo cuyo desplazamiento la hace correr."""
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    coord = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeTexCoord")
    tono = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeHueSaturation")
    corre = nt.nodes.new("ShaderNodeMapping")
    corre.name = "CorreTexto"
    imagen = nt.nodes.new("ShaderNodeTexImage")
    imagen.image = img
    imagen.extension = "REPEAT"
    imagen.interpolation = "Cubic"
    mezcla = nt.nodes.new("ShaderNodeMix")
    mezcla.data_type = "RGBA"
    entrada_a = next(i for i in mezcla.inputs if i.identifier == "A_Color")
    entrada_b = next(i for i in mezcla.inputs if i.identifier == "B_Color")
    salida = next(o for o in mezcla.outputs if o.identifier == "Result_Color")
    entrada_b.default_value = hex_a_lineal(COLOR_TEXTO)
    nt.links.new(coord.outputs["UV"], corre.inputs["Vector"])
    nt.links.new(corre.outputs["Vector"], imagen.inputs["Vector"])
    nt.links.new(imagen.outputs["Alpha"], mezcla.inputs["Factor"])
    nt.links.new(tono.outputs["Color"], entrada_a)
    nt.links.new(salida, bsdf.inputs["Base Color"])
    return corre


def crear_cinta(mat, mat_canto, mat_dorso, largo_tramo):
    marcos = camino()
    div = 6
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    filas = []
    for p, b, n, s in marcos:
        filas.append([(bm.verts.new(p + b * (-ANCHO / 2 + ANCHO * j / div)), s / largo_tramo, j / div)
                      for j in range(div + 1)])
    for fa, fb in zip(filas, filas[1:]):
        for j in range(div):
            esquinas = (fa[j], fb[j], fb[j + 1], fa[j + 1])
            cara = bm.faces.new([e[0] for e in esquinas])
            for loop, e in zip(cara.loops, esquinas):
                loop[uv].uv = (e[1], e[2])
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.dot(marcos[0][2]) < 0:  # que la cara impresa mire hacia afuera
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Cinta")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    me.materials.append(mat_canto)
    me.materials.append(mat_dorso)
    ob = bpy.data.objects.new("Cinta", me)
    bpy.context.scene.collection.objects.link(ob)
    sol = ob.modifiers.new("Grosor", "SOLIDIFY")
    sol.thickness = GROSOR
    sol.offset = -1.0  # crece hacia adentro: la cara impresa queda afuera
    sol.material_offset_rim = 1  # el corte muestra el alma clara de la cartulina
    sol.material_offset = 2      # el dorso es cartulina lisa: está impresa de un solo lado
    return ob


def crear_ciclorama():
    """Papel infinito de estudio, lejos de la cinta: piso que sube en curva hasta la pared."""
    piso_z, pared_y, radio, ancho = -6.5, 16.0, 9.0, 160.0
    perfil = [(y, piso_z) for y in (-40.0, -20.0, 0.0, pared_y - radio)]
    for i in range(1, 32):
        a = i / 32 * math.pi / 2
        perfil.append((pared_y - radio + radio * math.sin(a), piso_z + radio - radio * math.cos(a)))
    perfil += [(pared_y, piso_z + radio + h) for h in (0.0, 20.0, 60.0)]
    bm = bmesh.new()
    filas = [[bm.verts.new((x, y, z)) for x in (-ancho / 2, 0.0, ancho / 2)] for y, z in perfil]
    for a, b in zip(filas, filas[1:]):
        for j in range(2):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:  # que mire hacia arriba / hacia la cámara
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Ciclorama")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    papel = material_cartulina("Papel de fondo", COLOR_FONDO, 0.95, fibra=0.4)
    me.materials.append(papel)
    ajustar_escala(papel, me)
    ob = bpy.data.objects.new("Ciclorama", me)
    bpy.context.scene.collection.objects.link(ob)
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
    fondo_luz.inputs["Strength"].default_value = 0.22  # relleno bajo: manda la luz de tarde
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
    escena.frame_end = FPS * DURACION_LOOP
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

    # Orientación: el eje de la espiral cruza el cuadro en diagonal, de arriba a la izquierda
    # hacia abajo a la derecha, con una leve inclinación hacia cámara
    orient = bpy.data.objects.new("Orientacion", None)
    escena.collection.objects.link(orient)
    orient.rotation_mode = "QUATERNION"
    orient.rotation_quaternion = Vector((1.0, -0.3, -0.78)).to_track_quat("X", "Z")

    mat_cinta = material_cartulina("Cartulina azul impresa", COLOR_CINTA, 0.88)
    mat_canto = material_cartulina("Canto de cartulina", COLOR_CANTO, 0.92, fibra=0.6)
    mat_dorso = material_cartulina("Dorso de cartulina", COLOR_CINTA, 0.9)
    img, largo_tramo = imagen_del_texto()
    corre = agregar_texto_impreso(mat_cinta, img, largo_tramo)
    cinta = crear_cinta(mat_cinta, mat_canto, mat_dorso, largo_tramo)
    cinta.parent = orient
    ajustar_escala(mat_cinta, cinta.data)
    ajustar_escala(mat_canto, cinta.data)
    ajustar_escala(mat_dorso, cinta.data)
    crear_ciclorama()

    # Viento: un campo de ruido suave que viaja en círculo y hace respirar la cinta
    viento = bpy.data.objects.new("Viento", None)
    escena.collection.objects.link(viento)
    textura_viento = bpy.data.textures.new("Viento", "CLOUDS")
    textura_viento.noise_scale = ESCALA_VIENTO
    textura_viento.noise_depth = 1
    textura_viento.cloud_type = "COLOR"
    mod = cinta.modifiers.new("Viento", "DISPLACE")
    mod.texture = textura_viento
    mod.texture_coords = "OBJECT"
    mod.texture_coords_object = viento
    mod.direction = "RGB_TO_XYZ"
    mod.space = "GLOBAL"
    mod.strength = VIENTO
    mod.mid_level = 0.5

    # Se hornea una clave por frame (lineales entre sí); todo vuelve al inicio en el último
    # frame, así el loop empalma. Se restaura la preferencia del usuario al final.
    total_frames = FPS * DURACION_LOOP
    base = orient.rotation_quaternion.copy()
    desplazamiento = corre.inputs["Location"]
    prefs = bpy.context.preferences.edit
    interp_original = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for f in range(total_frames + 1):
            u = f / total_frames
            a = 2 * math.pi * u
            # el texto avanza siempre hacia adelante, acelerando y frenando suave
            n = PULSOS_VELOCIDAD
            avance = TRAMOS_POR_LOOP * (u + VARIACION_VELOCIDAD * math.sin(n * a) / (n * 2 * math.pi))
            desplazamiento.default_value[0] = -avance
            desplazamiento.keyframe_insert("default_value", index=0, frame=f + 1)

            viento.location = (1.8 * math.cos(a), 1.8 * math.sin(a), 0.9 * math.sin(2 * a))
            viento.keyframe_insert("location", frame=f + 1)

            balanceo = Euler((math.radians(BALANCEO) * math.sin(2 * a + 0.6),
                              math.radians(BALANCEO * 0.6) * math.sin(a),
                              math.radians(BALANCEO * 0.8) * math.sin(3 * a + 1.3)))
            orient.rotation_quaternion = base @ balanceo.to_quaternion()
            orient.keyframe_insert("rotation_quaternion", frame=f + 1)
    finally:
        prefs.keyframe_new_interpolation_type = interp_original

    # Cámara de frente, apenas desde arriba para que se vea el piso perderse en la pared
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 50
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 19.2
    cam_data.dof.aperture_fstop = 3.5
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    cam.location = (0, -19, 2.2)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, tipo, energia, color, pos, mira, **extra):
        datos = bpy.data.lights.new(nombre, tipo)
        datos.energy = energia
        datos.color = color
        for k, v in extra.items():
            setattr(datos, k, v)
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        return ob

    # Luz de tarde: principal cálida y rasante desde la izquierda; deja sombras largas en el fondo
    luz("Sol de tarde", "AREA", 3200, (1.0, 0.8, 0.6), (-14, -7, 7), (0, 0, 0), size=2.5)
    # Contra fría desde atrás a la derecha: dibuja los cantos de la cartulina
    luz("Contra", "AREA", 1400, (0.75, 0.85, 1.0), (9, 7, 6), (0, 0, 0), size=1.5)
    # Círculo de luz en el papel de fondo, detrás de la cinta, que se apaga hacia los bordes
    luz("Halo de fondo", "SPOT", 9000, (1.0, 0.9, 0.8), (0, 2, 3), (0, 16, 2),
        spot_size=math.radians(70), spot_blend=1.0)

    configurar_mundo()
    configurar_render()
    escena.frame_set(1)


main()
