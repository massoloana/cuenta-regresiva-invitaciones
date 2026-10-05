"""
"HOLA" en letras infladas de vidrio rosa, apoyadas en un piso blanco.

Uso en Blender (4.2 o superior):
  1. Abrí Blender > pestaña "Scripting" > Open > este archivo > Run Script.
  2. O desde terminal:
       blender --background --python hola_vidrio.py -- --render hola_vidrio.png --save hola_vidrio.blend

Animación (ver HOLA_PARA_RENDER.md):
       blender -b -P hola_vidrio.py -- --animar --gpu --frames 1 120 --render-anim cuadros/
  Opciones: --muestras N   --res ANCHO ALTO   --mp4 salida.mp4   --save archivo.blend

Cada letra es un metaball (bolitas y cápsulas que se fusionan solas), así
quedan redondas e infladas como globos. Después se convierten a malla.
Para cambiar la forma, editá el "esqueleto" de cada letra en LETRAS.
"""
import sys
import math
import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
GROSOR = 0.33            # radio del trazo inflado (alto de letra ≈ 2)
APLASTADO = 0.88         # profundidad relativa: <1 = más "almohadón"
UMBRAL = 0.6             # superficie exterior del metaball
UMBRAL_INTERIOR = 3.2    # pared interna (más alto = vidrio más grueso)
VIDRIO = (1.0, 0.50, 0.70, 1.0)     # rosa del vidrio
ABSORCION = (1.0, 0.30, 0.50, 1.0)  # color que toma en las partes gruesas
DENSIDAD = 4.0                      # cuánto se tiñe en lo grueso
FONDO = (0.80, 0.77, 0.78, 1.0)      # piso/fondo: gris claro (se ve casi blanco)
EXPOSICION = -0.5
GIRO_PALABRA = 20.0      # 0 = de frente; 45 = diagonal; 90 = de perfil

# Grosor propio para alguna letra (si no está, usa GROSOR)
GROSOR_LETRA = {}
SOMBRA = (1.0, 0.22, 0.42, 1.0)    # tinte de la luz que atraviesa el vidrio
REFLEJO_NARANJA = (1.0, 0.45, 0.08, 1.0)
REFLEJO_AMARILLO = (1.0, 0.82, 0.15, 1.0)
INTENSIDAD_REFLEJOS = 45.0
PELICULA_NM = 250.0          # espesor de la película iridiscente (nm); 0 = sin efecto

# Animación (a 24 cuadros por segundo)
FPS = 24
CUADROS = 120              # 5 segundos
ENTRADA_DESFASAJE = 6      # cuadros entre que se infla una letra y la siguiente
REBOTE = 0.12              # amortiguación del rebote (s): más chico = rebota menos
RESPIRA = 0.015            # cuánto se inflan/desinflan después (1.5 %)
FLOTA = 0.06               # cuánto sube la palabra al flotar
BRILLO_DESDE, BRILLO_HASTA = 66, 102   # cuadros en que pasa el brillo dorado

# Esqueleto de cada letra: lista de trazos; cada trazo es una lista de
# puntos (x, z). Las letras se tocan apenas entre sí.
def elipse(cx, cz, rx, rz, n=40):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cz + rz * math.sin(2 * math.pi * i / n))
            for i in range(n + 1)]

LETRAS = {
    "H": [
        [(0.00, 0.30), (0.00, 1.70)],
        [(1.00, 0.30), (1.00, 1.70)],
        [(0.00, 1.00), (1.00, 1.00)],
    ],
    "O": [
        elipse(2.15, 1.02, 0.40, 0.66),  # O angosta y alta: mismo trazo, agujero chiquito
    ],
    "L": [
        [(3.31, 1.70), (3.31, 0.30), (3.91, 0.30)],
    ],
    "A": [
        [(4.40, 0.30), (4.80, 1.42), (4.92, 1.66), (5.05, 1.73),
         (5.18, 1.66), (5.30, 1.42), (5.70, 0.30)],
        [(4.60, 0.62), (5.50, 0.62)],
    ],
}


def limpiar_escena():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def muestrear(trazo, paso=0.06):
    """Puntos equiespaciados a lo largo de una polilínea."""
    pts = []
    for (x0, z0), (x1, z1) in zip(trazo, trazo[1:]):
        largo = math.hypot(x1 - x0, z1 - z0)
        n = max(1, int(largo / paso))
        for i in range(n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
    pts.append(trazo[-1])
    return pts


def superficie(nombre, trazos, umbral, grosor=GROSOR):
    """Metaball de los trazos convertido a malla; más umbral = superficie más chica."""
    mb = bpy.data.metaballs.new(nombre)
    mb.resolution = 0.02
    mb.threshold = umbral
    obj = bpy.data.objects.new(nombre, mb)
    bpy.context.collection.objects.link(obj)
    for trazo in trazos:
        for x, z in muestrear(trazo):
            el = mb.elements.new(type="BALL")
            el.co = (x, 0.0, z)
            el.radius = grosor * 1.25
            el.stiffness = 2.0
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.active_object
    obj.name = nombre
    return obj


def crear_letra(nombre, trazos, mat):
    g = GROSOR_LETRA.get(nombre, GROSOR)
    exterior = superficie(f"letra_{nombre}", trazos, UMBRAL, g)
    # Pared interna: la misma forma un poco más chica, con normales hacia
    # adentro. Así la letra es un casco de vidrio hueco, como un globo.
    interior = superficie(f"interior_{nombre}", trazos, UMBRAL_INTERIOR, g)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    interior.select_set(True)
    exterior.select_set(True)
    bpy.context.view_layer.objects.active = exterior
    bpy.ops.object.join()
    obj = exterior
    obj.scale.y = APLASTADO
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    # Apoyar la letra en el piso
    piso_z = min(v.co.z for v in obj.data.vertices)
    obj.location.z -= piso_z
    obj.data.materials.append(mat)
    obj.select_set(False)
    return obj


def acomodar(letras, separacion=0.004):
    """Junta las letras hasta que apenas se toquen, sin meterse una en otra.

    Si los vidrios se superponen, la refracción en la zona de contacto se ve
    deformada; así quedan pegadas pero cada una conserva su forma.
    """
    from mathutils.bvhtree import BVHTree

    def arbol(obj, dx=0.0):
        mw = obj.matrix_world
        verts = [mw @ v.co + Vector((dx, 0, 0)) for v in obj.data.vertices]
        return BVHTree.FromPolygons(verts, [p.vertices for p in obj.data.polygons])

    def se_tocan(a, b, dx):
        return bool(arbol(a).overlap(arbol(b, dx)))

    for i in range(1, len(letras)):
        prev, act = letras[i - 1], letras[i]
        lejos, cerca = 1.0, -0.5
        if se_tocan(prev, act, lejos):
            continue
        for _ in range(18):  # búsqueda binaria del desplazamiento justo
            medio = (lejos + cerca) / 2
            if se_tocan(prev, act, medio):
                cerca = medio
            else:
                lejos = medio
        dx = lejos + separacion
        for o in letras[i:]:
            o.location.x += dx
        bpy.context.view_layer.update()


def girar_palabra(letras, grados):
    """Gira toda la palabra alrededor de su centro (la cámara queda quieta)."""
    xs = [(o.matrix_world @ v.co).x for o in letras for v in o.data.vertices]
    centro = Vector(((min(xs) + max(xs)) / 2, 0.0, 0.0))
    pivote = bpy.data.objects.new("palabra", None)
    pivote.location = centro
    bpy.context.collection.objects.link(pivote)
    bpy.context.view_layer.update()
    for o in letras:
        mw = o.matrix_world.copy()
        o.parent = pivote
        o.matrix_world = mw
    pivote.rotation_euler.z = math.radians(-grados)
    bpy.context.view_layer.update()


def origen_abajo(obj):
    """Pone el origen de la letra en el centro de su base: se infla desde el piso."""
    vs = obj.data.vertices
    cx = (min(v.co.x for v in vs) + max(v.co.x for v in vs)) / 2
    cy = (min(v.co.y for v in vs) + max(v.co.y for v in vs)) / 2
    cz = min(v.co.z for v in vs)
    c = Vector((cx, cy, cz))
    for v in vs:
        v.co -= c
    obj.location += c


def resorte(t):
    """0 -> 1 con un rebote amortiguado (t en segundos desde que arranca)."""
    if t <= 0:
        return 0.0
    w = 2 * math.pi / 0.45
    return 1 - math.exp(-t / REBOTE) * math.cos(w * t)


def animar(letras, scene):
    """Entrada: cada letra se infla con rebote. Después respiran, la palabra
    flota apenas y un brillo dorado la recorre. Todo queda en keyframes."""
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, CUADROS
    pivote = bpy.data.objects["palabra"]
    base_z = pivote.location.z
    for i, o in enumerate(letras):
        inicio = 1 + i * ENTRADA_DESFASAJE
        for f in range(1, CUADROS + 1):
            t = (f - inicio) / FPS
            r = resorte(t)
            # se estira un poco más para arriba que para los costados (globo)
            sxy = max(0.001, 1 + 0.6 * (r - 1))
            sz = max(0.001, 1 + 1.3 * (r - 1)) if r > 0 else 0.001
            if r == 0:
                sxy = 0.001
            # respiración: arranca suave cuando la letra ya se asentó
            fase = i * 0.7
            entra = min(1.0, max(0.0, (t - 0.8) / 0.8))
            b = 1 + RESPIRA * entra * math.sin(2 * math.pi * t / 2.0 + fase)
            o.scale = (sxy * b, sxy * b, sz * b)
            o.keyframe_insert("scale", frame=f)
    # flotar: la palabra entera sube y baja apenas, después de la entrada
    arranque = 1 + len(letras) * ENTRADA_DESFASAJE + 12
    for f in range(1, CUADROS + 1):
        t = max(0, f - arranque) / FPS
        pivote.location.z = base_z + FLOTA * (1 - math.cos(2 * math.pi * t / 2.5)) / 2
        pivote.keyframe_insert("location", index=2, frame=f)
    for o in [pivote] + letras:
        if o.animation_data and o.animation_data.action:
            for fc in iter_fcurves(o.animation_data.action):
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"

    # brillo dorado que cruza (solo se ve en los reflejos del vidrio)
    tm = bpy.data.materials.new("brillo_dorado")
    tm.use_nodes = True
    tn = tm.node_tree.nodes
    tn.remove(tn["Principled BSDF"])
    em = tn.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = REFLEJO_AMARILLO
    em.inputs["Strength"].default_value = 0.0
    tm.node_tree.links.new(em.outputs["Emission"], tn["Material Output"].inputs["Surface"])
    cx = pivote.location.x
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx - 7, -5.0, 3.5),
                                     rotation=(math.radians(60), 0, 0))
    barra = bpy.context.active_object
    barra.name = "brillo_dorado"
    barra.scale = (0.6, 4.0, 1)
    barra.data.materials.append(tm)
    barra.visible_camera = False
    barra.visible_shadow = False
    barra.visible_diffuse = False
    barra.visible_transmission = False
    fuerza = em.inputs["Strength"]
    for f, x, w in [(BRILLO_DESDE - 1, cx - 7, 0.0), (BRILLO_DESDE, cx - 7, 60.0),
                    (BRILLO_HASTA, cx + 7, 60.0), (BRILLO_HASTA + 1, cx + 7, 0.0)]:
        barra.location.x = x
        barra.keyframe_insert("location", index=0, frame=f)
        fuerza.default_value = w
        fuerza.keyframe_insert("default_value", frame=f)


def iter_fcurves(action):
    """F-curves de una acción (Blender 4.x y 5.x guardan las curvas distinto)."""
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        yield from action.fcurves
        return
    for capa in getattr(action, "layers", []):
        for tira in capa.strips:
            for bolsa in tira.channelbags:
                yield from bolsa.fcurves


def usar_gpu(scene):
    """Usa la placa de video si hay (OptiX en RTX, si no CUDA/HIP/Metal/oneAPI)."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return None
    for tipo in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = tipo
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == tipo]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == tipo
            scene.cycles.device = "GPU"
            return tipo
    return None


def crear_vidrio():
    mat = bpy.data.materials.new("vidrio_rosa")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = VIDRIO
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.5
    # Película fina iridiscente (como burbuja de jabón): da reflejos de color
    bsdf.inputs["Thin Film Thickness"].default_value = PELICULA_NM
    bsdf.inputs["Thin Film IOR"].default_value = 1.33

    # Sombra rosada: para los rayos de sombra el vidrio deja pasar luz teñida,
    # así el piso recibe ese brillo rosa en vez de una sombra gris.
    camino = nodes.new("ShaderNodeLightPath")
    trans = nodes.new("ShaderNodeBsdfTransparent")
    trans.inputs["Color"].default_value = SOMBRA
    mezcla = nodes.new("ShaderNodeMixShader")
    links.new(camino.outputs["Is Shadow Ray"], mezcla.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mezcla.inputs[1])
    links.new(trans.outputs["BSDF"], mezcla.inputs[2])
    links.new(mezcla.outputs["Shader"], out.inputs["Surface"])
    # Absorción: donde el vidrio es más grueso, más rosa
    vol = nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = ABSORCION
    vol.inputs["Density"].default_value = DENSIDAD
    links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def crear_escena(letras):
    scene = bpy.context.scene

    # Piso + fondo curvo (ciclorama) para que no se vea el horizonte
    bpy.ops.mesh.primitive_plane_add(size=1)
    piso = bpy.context.active_object
    piso.name = "ciclorama"
    me = piso.data
    import bmesh
    bm = bmesh.new()
    ancho, prof, alto, radio = 40.0, 8.0, 15.0, 3.0
    perfil = [(-30.0, 0.0), (prof - radio, 0.0)]
    for i in range(1, 16):
        a = (math.pi / 2) * i / 16
        perfil.append((prof - radio + radio * math.sin(a), radio - radio * math.cos(a)))
    perfil.append((prof, alto))
    filas = []
    for y, z in perfil:
        filas.append([bm.verts.new((x, y, z)) for x in (-ancho / 2, ancho / 2)])
    for f0, f1 in zip(filas, filas[1:]):
        bm.faces.new((f0[0], f0[1], f1[1], f1[0]))
    bm.to_mesh(me)
    bm.free()
    bpy.ops.object.shade_smooth()
    pm = bpy.data.materials.new("piso")
    pm.use_nodes = True
    pb = pm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = FONDO
    pb.inputs["Roughness"].default_value = 0.6
    me.materials.append(pm)
    piso.location = (2.8, -2.5, 0.0)

    # Mundo blanco suave
    world = bpy.data.worlds.new("mundo")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.15

    def luz(nombre, loc, energia, ancho, alto, mirar=(2.8, 0, 1), apertura=70):
        data = bpy.data.lights.new(nombre, "AREA")
        data.shape = "RECTANGLE"
        data.size, data.size_y = ancho, alto
        data.energy = energia
        data.spread = math.radians(apertura)
        o = bpy.data.objects.new(nombre, data)
        o.location = loc
        d = Vector(mirar) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(o)
        return o

    # Luz principal arriba-izquierda-adelante: la sombra rosada cae atrás a la derecha
    key = luz("principal", (-4.0, -2.5, 4.5), 2200, 3.0, 3.0, apertura=180)
    # Relleno frontal grande y suave
    luz("relleno", (2.8, -8.0, 3.0), 250, 8.0, 4.0)
    # Tiras laterales: bordes brillantes en el vidrio
    izq = luz("tira_izq", (-3.5, -1.5, 2.0), 900, 0.6, 4.0)
    izq.data.color = REFLEJO_NARANJA[:3]
    izq.visible_diffuse = False  # tiñe los reflejos, no el piso
    izq.visible_transmission = False
    der = luz("tira_der", (9.5, -1.0, 2.0), 900, 0.6, 4.0)
    der.data.color = REFLEJO_AMARILLO[:3]
    der.visible_diffuse = False
    der.visible_transmission = False

    # Tarjetas de color fuera de cuadro: el vidrio las refleja como manchas
    # de luz naranja y amarilla (no se ven ni hacen sombra).
    for nombre, color, loc, rot, escala in [
        ("tarjeta_naranja", REFLEJO_NARANJA, (-0.5, -9.0, 2.2), (math.pi / 2, 0, math.radians(-15)), (1.0, 3.0, 1)),
        ("tarjeta_amarilla", REFLEJO_AMARILLO, (6.2, -9.0, 2.6), (math.pi / 2, 0, math.radians(15)), (1.0, 3.0, 1)),
        ("tarjeta_durazno", REFLEJO_AMARILLO, (2.8, -4.0, 5.5), (math.radians(35), 0, 0), (6.0, 0.6, 1)),
    ]:
        tm = bpy.data.materials.new(nombre)
        tm.use_nodes = True
        tn = tm.node_tree.nodes
        tn.remove(tn["Principled BSDF"])
        em = tn.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = color
        em.inputs["Strength"].default_value = INTENSIDAD_REFLEJOS
        tm.node_tree.links.new(em.outputs["Emission"], tn["Material Output"].inputs["Surface"])
        bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
        t = bpy.context.active_object
        t.name = nombre
        t.scale = escala
        t.data.materials.append(tm)
        t.visible_camera = False
        t.visible_shadow = False
        t.visible_diffuse = False  # solo aparece en los reflejos del vidrio
        t.visible_transmission = False

    # Paneles oscuros fuera de cuadro: el vidrio los refleja y eso dibuja
    # los bordes y rebotes internos (truco clásico de foto de producto).
    negro = bpy.data.materials.new("panel_oscuro")
    negro.use_nodes = True
    nb = negro.node_tree.nodes["Principled BSDF"]
    nb.inputs["Base Color"].default_value = (0.02, 0.015, 0.02, 1.0)
    nb.inputs["Roughness"].default_value = 1.0
    for nombre, loc, rot in [
        ("panel_izq", (-3.0, -4.0, 2.0), (math.pi / 2, 0, math.radians(-50))),
        ("panel_der", (8.6, -4.0, 2.0), (math.pi / 2, 0, math.radians(50))),
        ("panel_arriba", (2.8, -2.0, 6.5), (math.radians(20), 0, 0)),
    ]:
        bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
        pnl = bpy.context.active_object
        pnl.name = nombre
        pnl.scale = (2.5, 4.0, 1) if nombre != "panel_arriba" else (5.0, 1.2, 1)
        pnl.data.materials.append(negro)
        pnl.visible_camera = False
        pnl.visible_shadow = False

    # Cámara
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 62 if GIRO_PALABRA == 0 else 80
    cam = bpy.data.objects.new("cam", cam_data)
    # Centro de la palabra y cámara girada CAMARA_ANGULO grados alrededor de ella
    xs = [(o.matrix_world @ o.data.vertices[i].co).x for o in letras
          for i in range(0, len(o.data.vertices), 50)]
    centro = Vector(((min(xs) + max(xs)) / 2, 0.0, 0.9))
    cam.location = centro + Vector((0.0, -14.0, 3.6))
    d = centro - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Render
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 24
    scene.cycles.transmission_bounces = 24
    scene.cycles.glossy_bounces = 12
    scene.cycles.volume_bounces = 4
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1080
    scene.view_settings.view_transform = "Khronos PBR Neutral"  # conserva el color de los brillos
    scene.view_settings.exposure = EXPOSICION


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    limpiar_escena()
    mat = crear_vidrio()
    letras = [crear_letra(n, t, mat) for n, t in LETRAS.items()]
    acomodar(letras)
    for o in letras:
        origen_abajo(o)
    bpy.context.view_layer.update()
    girar_palabra(letras, GIRO_PALABRA)
    crear_escena(letras)
    scene = bpy.context.scene

    def arg(nombre, n=1):
        i = argv.index(nombre)
        return argv[i + 1:i + 1 + n]

    if "--animar" in argv:
        animar(letras, scene)
    if "--gpu" in argv:
        print("GPU:", usar_gpu(scene) or "no hay, uso CPU")
    if "--muestras" in argv:
        scene.cycles.samples = int(arg("--muestras")[0])
    if "--res" in argv:
        w, h = arg("--res", 2)
        scene.render.resolution_x, scene.render.resolution_y = int(w), int(h)

    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=arg("--save")[0])
    if "--render" in argv:
        scene.render.filepath = arg("--render")[0]
        bpy.ops.render.render(write_still=True)
    if "--render-anim" in argv or "--mp4" in argv:
        if "--frames" in argv:
            a, b = arg("--frames", 2)
            scene.frame_start, scene.frame_end = int(a), int(b)
        scene.render.use_persistent_data = True
        if "--mp4" in argv:
            if hasattr(scene.render.image_settings, "media_type"):  # Blender 5
                scene.render.image_settings.media_type = "VIDEO"
            scene.render.image_settings.file_format = "FFMPEG"
            scene.render.ffmpeg.format = "MPEG4"
            scene.render.ffmpeg.codec = "H264"
            scene.render.ffmpeg.constant_rate_factor = "HIGH"
            scene.render.filepath = arg("--mp4")[0]
        else:
            # cuadros PNG numerados: si se corta, se retoma sin perder lo hecho
            scene.render.image_settings.file_format = "PNG"
            scene.render.use_overwrite = False
            scene.render.use_placeholder = True
            carpeta = arg("--render-anim")[0]
            scene.render.filepath = carpeta.rstrip("/\\") + "/hola_####"
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
