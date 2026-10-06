"""
Logo de YouTube como almohadón de tela inflado (estilo peluche/puffer).

Uso en Blender (4.2 o superior):
  1. Abrí Blender > pestaña "Scripting" > Open > este archivo > Run Script.
  2. O desde terminal:
       blender -b -P youtube_peluche.py -- --render foto.png
       blender -b -P youtube_peluche.py -- --animar --gpu --render-anim cuadros/
  Opciones: --frames A B   --muestras N   --res ANCHO ALTO   --mp4 salida.mp4   --save archivo.blend

El rectángulo rojo y el triángulo blanco son dos almohadones separados: se
modelan con metaballs (formas blandas), se inflan como un almohadón y llevan
una costura con pliegue alrededor del contorno.
"""
import sys
import math
import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
ANCHO, ALTO = 2.9, 2.0          # rectángulo rojo (como el logo, 1.45 : 1)
PROFUNDIDAD = 1.10              # grosor del almohadón rojo
INFLADO = 0.32                  # cuánto se abomba el centro de cada cara
TRIANGULO = [(-0.42, 0.50), (-0.42, -0.50), (0.56, 0.0)]   # play (x, z)
PROFUNDIDAD_TRIANGULO = 0.50
ROJO = (0.42, 0.0, 0.003, 1.0)
BLANCO = (0.88, 0.87, 0.85, 1.0)
FONDO = (0.92, 0.92, 0.92, 1.0)
EXPOSICION = -0.9

# Animación (24 cuadros por segundo)
FPS = 24
CUADROS = 168                   # 7 segundos
GIRO_DESDE, GIRO_HASTA = 12, 150   # dos vueltas completas sobre su eje
VUELTAS = 2
FLOTA = 0.08                    # cuánto sube y baja mientras gira


def limpiar_escena():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def suave(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def a_malla(obj):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.active_object


def almohadon(nombre, puntos2d, profundidad, radio, paso):
    """Almohadón con la silueta de un polígono (x, z): se rellena el
    polígono con bolitas de metaball que se funden en una forma blanda."""
    mb = bpy.data.metaballs.new(nombre)
    mb.resolution = 0.03
    mb.render_resolution = 0.02
    mb.threshold = 0.6
    obj = bpy.data.objects.new(nombre, mb)
    bpy.context.collection.objects.link(obj)

    def adentro(x, z):
        n, dentro = len(puntos2d), False
        for i in range(n):
            (x1, z1), (x2, z2) = puntos2d[i], puntos2d[(i + 1) % n]
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
                dentro = not dentro
        return dentro

    xs = [p[0] for p in puntos2d]
    zs = [p[1] for p in puntos2d]
    x = min(xs)
    while x <= max(xs):
        z = min(zs)
        while z <= max(zs):
            if adentro(x, z):
                el = mb.elements.new(type="ELLIPSOID")
                el.co = (x, 0.0, z)
                el.radius = radio
                el.size_x = el.size_z = 1.0
                el.size_y = profundidad / (2 * radio)
                el.stiffness = 1.0
            z += paso
        x += paso
    return a_malla(obj)


def rectangulo_redondeado(ancho, alto, r, n=10):
    pts = []
    for cx, cz, a0 in ((ancho / 2 - r, alto / 2 - r, 0), (-ancho / 2 + r, alto / 2 - r, 90),
                       (-ancho / 2 + r, -alto / 2 + r, 180), (ancho / 2 - r, -alto / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def inflar_y_coser(obj, inflado, pliegue=0.035):
    """Abomba las caras (almohadón) y marca un pliegue en la costura del
    contorno, donde se unen la tela de adelante y la de atrás."""
    vs = obj.data.vertices
    xmin, xmax = min(v.co.x for v in vs), max(v.co.x for v in vs)
    zmin, zmax = min(v.co.z for v in vs), max(v.co.z for v in vs)
    cx, cz = (xmin + xmax) / 2, (zmin + zmax) / 2
    hx, hz = (xmax - xmin) / 2, (zmax - zmin) / 2
    ymax = max(abs(v.co.y) for v in vs)
    for v in vs:
        u = (v.co.x - cx) / hx
        w = (v.co.z - cz) / hz
        domo = max(0.0, 1 - u * u) * max(0.0, 1 - w * w)
        lado = 1 if v.co.y >= 0 else -1
        v.co.y += lado * inflado * domo * (abs(v.co.y) / ymax)
        # pliegue de costura: los vértices cerca del "ecuador" se hunden
        cerca = math.exp(-(v.co.y / (ymax * 0.12)) ** 2)
        hacia = Vector((v.co.x - cx, 0, v.co.z - cz))
        if hacia.length > 1e-4:
            v.co -= hacia.normalized() * pliegue * cerca
    obj.data.update()


def material_tela(nombre, color, pespunte=None):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.72
    b.inputs["Sheen Weight"].default_value = 0.25
    b.inputs["Sheen Roughness"].default_value = 0.3
    b.inputs["Sheen Tint"].default_value = tuple(min(1.0, c * 1.4 + 0.1) for c in color[:3]) + (1.0,)
    b.inputs["Specular IOR Level"].default_value = 0.35

    coords = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(coords.outputs["Object"], sep.inputs["Vector"])

    # trama fina del tejido
    trama = n.new("ShaderNodeTexNoise")
    trama.inputs["Scale"].default_value = 260.0
    trama.inputs["Detail"].default_value = 2.0
    l.new(coords.outputs["Object"], trama.inputs["Vector"])

    # pespunte: línea de puntadas en el frente y atrás, a una distancia fija
    # del contorno (distancia a un rectángulo redondeado en x, z)
    def mate(op, a, b=None):
        nodo = n.new("ShaderNodeMath")
        nodo.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                nodo.inputs[i].default_value = x
            else:
                l.new(x, nodo.inputs[i])
        return nodo.outputs[0]
    if pespunte:
        mx, mz, r, adentro = pespunte
        qx = mate("ADD", mate("ABSOLUTE", sep.outputs["X"]), -(mx - r))
        qz = mate("ADD", mate("ABSOLUTE", sep.outputs["Z"]), -(mz - r))
        afuera = mate("SQRT", mate("ADD", mate("POWER", mate("MAXIMUM", qx, 0.0), 2.0),
                                   mate("POWER", mate("MAXIMUM", qz, 0.0), 2.0)))
        dist = mate("ADD", mate("ADD", afuera, mate("MINIMUM", mate("MAXIMUM", qx, qz), 0.0)), -r)
        # banda angosta en dist = -adentro, solo en las caras (no en el costado)
        cerca = mate("ABSOLUTE", mate("ADD", dist, adentro))
        linea = mate("LESS_THAN", cerca, 0.012)
        cara = mate("GREATER_THAN", mate("ABSOLUTE", sep.outputs["Y"]), 0.3)
        linea = mate("MULTIPLY", linea, cara)
        # frunce: arruguitas de la tela junto a la costura y al pespunte
        zona = mate("MULTIPLY", mate("LESS_THAN", cerca, 0.10), cara)
        arrugas = n.new("ShaderNodeTexWave")
        arrugas.wave_type = "RINGS"
        arrugas.inputs["Scale"].default_value = 9.0
        arrugas.inputs["Distortion"].default_value = 6.0
        arrugas.inputs["Detail"].default_value = 3.0
        l.new(coords.outputs["Object"], arrugas.inputs["Vector"])
        frunce = mate("MULTIPLY", mate("MULTIPLY", arrugas.outputs["Fac"], zona), 0.6)
    else:
        linea = mate("MULTIPLY", sep.outputs["X"], 0.0)
        frunce = linea
    # puntadas: cortes a lo largo del contorno (ángulo alrededor del centro)
    ang = n.new("ShaderNodeMath")
    ang.operation = "ARCTAN2"
    l.new(sep.outputs["Z"], ang.inputs[0])
    l.new(sep.outputs["X"], ang.inputs[1])
    puntos = n.new("ShaderNodeMath")
    puntos.operation = "SINE"
    mult = n.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    mult.inputs[1].default_value = 160.0
    l.new(ang.outputs[0], mult.inputs[0])
    l.new(mult.outputs[0], puntos.inputs[0])
    corte = n.new("ShaderNodeMath")
    corte.operation = "GREATER_THAN"
    corte.inputs[1].default_value = -0.2
    l.new(puntos.outputs[0], corte.inputs[0])
    puntada = n.new("ShaderNodeMath")
    puntada.operation = "MULTIPLY"
    l.new(linea, puntada.inputs[0])
    l.new(corte.outputs[0], puntada.inputs[1])

    # relieve: trama + puntadas hundidas
    alto = n.new("ShaderNodeMath")
    alto.operation = "MULTIPLY_ADD"
    alto.inputs[1].default_value = -0.6
    l.new(puntada.outputs[0], alto.inputs[0])
    trama_y_frunce = mate("ADD", trama.outputs["Fac"], frunce)
    l.new(trama_y_frunce, alto.inputs[2])
    relieve = n.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = 0.45
    relieve.inputs["Distance"].default_value = 0.01
    l.new(alto.outputs[0], relieve.inputs["Height"])
    l.new(relieve.outputs["Normal"], b.inputs["Normal"])

    # color: el hilo de la costura apenas más oscuro
    oscuro = n.new("ShaderNodeMix")
    oscuro.data_type = "RGBA"
    oscuro.inputs[6].default_value = color
    oscuro.inputs[7].default_value = tuple(c * 0.55 for c in color[:3]) + (1.0,)
    l.new(puntada.outputs[0], oscuro.inputs["Factor"])
    l.new(oscuro.outputs[2], b.inputs["Base Color"])
    return m


def crear_logo():
    rojo = almohadon("almohadon_rojo", rectangulo_redondeado(ANCHO, ALTO, 0.62),
                     PROFUNDIDAD, 0.34, 0.07)
    inflar_y_coser(rojo, INFLADO)
    rojo.data.materials.append(material_tela("tela_roja", ROJO, (ANCHO / 2, ALTO / 2, 0.62, 0.16)))
    bpy.ops.object.shade_smooth()

    blanco = almohadon("almohadon_blanco", TRIANGULO, PROFUNDIDAD_TRIANGULO, 0.26, 0.06)
    bpy.context.view_layer.objects.active = blanco
    inflar_y_coser(blanco, INFLADO * 0.6, pliegue=0.025)
    blanco.data.materials.append(material_tela("tela_blanca", BLANCO))
    bpy.ops.object.shade_smooth()
    # apoyado contra el frente del rojo, hundiéndolo apenas (se aprietan)
    frente_rojo = min(v.co.y for v in rojo.data.vertices)
    fondo_blanco = max(v.co.y for v in blanco.data.vertices)
    blanco.location.y = frente_rojo - fondo_blanco + 0.12

    logo = bpy.data.objects.new("logo", None)
    bpy.context.collection.objects.link(logo)
    for o in (rojo, blanco):
        o.parent = logo
    piso = min(v.co.z for v in rojo.data.vertices)
    logo.location.z = -piso + 0.35   # flota un poco sobre el piso
    return logo, rojo, blanco


def crear_estudio(scene):
    import bmesh
    me = bpy.data.meshes.new("estudio")
    est = bpy.data.objects.new("estudio", me)
    scene.collection.objects.link(est)
    bm = bmesh.new()
    radio, curva, alto, lados = 16.0, 5.0, 25.0, 96
    perfil = [(radio * 0.5, 0.0), (radio, 0.0)]
    for i in range(1, 17):
        a = (math.pi / 2) * i / 16
        perfil.append((radio + curva * math.sin(a), curva - curva * math.cos(a)))
    perfil.append((radio + curva, alto))
    anillos = [[bm.verts.new((r * math.cos(2 * math.pi * k / lados),
                              r * math.sin(2 * math.pi * k / lados), z)) for k in range(lados)]
               for r, z in perfil]
    c = bm.verts.new((0, 0, 0))
    for k in range(lados):
        bm.faces.new((c, anillos[0][k], anillos[0][(k + 1) % lados]))
    for a0, a1 in zip(anillos, anillos[1:]):
        for k in range(lados):
            k2 = (k + 1) % lados
            bm.faces.new((a0[k], a1[k], a1[k2], a0[k2]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new("estudio")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = FONDO
    b.inputs["Roughness"].default_value = 0.9
    # brillo propio solo en la pared lejana (fondo blanco parejo, el piso conserva la sombra)
    n, l = m.node_tree.nodes, m.node_tree.links
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = FONDO
    co = n.new("ShaderNodeTexCoord")
    largo = n.new("ShaderNodeVectorMath")
    largo.operation = "LENGTH"
    l.new(co.outputs["Object"], largo.inputs[0])
    rango = n.new("ShaderNodeMapRange")
    rango.interpolation_type = "SMOOTHSTEP"
    rango.inputs["From Min"].default_value = 6.0
    rango.inputs["From Max"].default_value = 16.0
    rango.inputs["To Max"].default_value = 0.9
    l.new(largo.outputs["Value"], rango.inputs["Value"])
    l.new(rango.outputs["Result"], em.inputs["Strength"])
    suma = n.new("ShaderNodeAddShader")
    l.new(b.outputs["BSDF"], suma.inputs[0])
    l.new(em.outputs["Emission"], suma.inputs[1])
    l.new(suma.outputs["Shader"], n["Material Output"].inputs["Surface"])
    me.materials.append(m)
    est.visible_shadow = False

    world = bpy.data.worlds.new("mundo")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25

    def luz(nombre, loc, energia, tam, mirar=(0, 0, 1.3)):
        d = bpy.data.lights.new(nombre, "AREA")
        d.energy, d.size = energia, tam
        o = bpy.data.objects.new(nombre, d)
        o.location = loc
        o.rotation_euler = (Vector(mirar) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        o.visible_camera = False
        scene.collection.objects.link(o)

    luz("principal", (-6.0, -3.5, 6.0), 2600, 4.0)
    luz("relleno", (5.0, -6.0, 2.5), 300, 6.0)
    luz("contra", (1.0, 5.0, 5.0), 900, 4.0)


def crear_camara(scene):
    cd = bpy.data.cameras.new("cam")
    cd.lens = 70
    cam = bpy.data.objects.new("cam", cd)
    scene.collection.objects.link(cam)
    mira = bpy.data.objects.new("mira", None)
    mira.location = (0, 0, 1.35)
    scene.collection.objects.link(mira)
    t = cam.constraints.new("TRACK_TO")
    t.target = mira
    t.track_axis, t.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam
    poner_camara(cam, -25.0, 12.5, 3.0)
    return cam, mira


def poner_camara(cam, grados, dist, alto):
    a = math.radians(grados)
    cam.location = (dist * math.sin(a), -dist * math.cos(a), alto)


def animar(scene, logo, cam, mira):
    """El logo da dos vueltas sobre su eje (con arranque y frenada suaves)
    y flota apenas; la cámara se mueve de un costado bajo al frente, más cerca."""
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, CUADROS
    z0 = logo.location.z
    for f in range(1, CUADROS + 1):
        u = suave((f - GIRO_DESDE) / (GIRO_HASTA - GIRO_DESDE))
        logo.rotation_euler.z = 2 * math.pi * VUELTAS * u
        logo.location.z = z0 + FLOTA * math.sin(2 * math.pi * f / (FPS * 3.5))
        logo.keyframe_insert("rotation_euler", index=2, frame=f)
        logo.keyframe_insert("location", index=2, frame=f)

        c = suave((f - 1) / (CUADROS - 1))
        poner_camara(cam, -38 + 50 * c, 15.0 - 3.5 * c, 1.2 + 1.8 * c)
        cam.keyframe_insert("location", frame=f)
        mira.location.z = 1.2 + 0.15 * c
        mira.keyframe_insert("location", index=2, frame=f)
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5


def usar_gpu(scene):
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
        if any(d.type == tipo for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == tipo
            scene.cycles.device = "GPU"
            return tipo
    return None


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    limpiar_escena()
    scene = bpy.context.scene
    logo, rojo, blanco = crear_logo()
    crear_estudio(scene)
    cam, mira = crear_camara(scene)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 192
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 1080
    scene.view_settings.view_transform = "Khronos PBR Neutral"  # conserva el rojo saturado
    scene.view_settings.exposure = EXPOSICION

    def arg(nombre, n=1):
        i = argv.index(nombre)
        return argv[i + 1:i + 1 + n]

    if "--animar" in argv:
        animar(scene, logo, cam, mira)
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
        if "--mp4" in argv:
            if hasattr(scene.render.image_settings, "media_type"):  # Blender 5
                scene.render.image_settings.media_type = "VIDEO"
            scene.render.image_settings.file_format = "FFMPEG"
            scene.render.ffmpeg.format = "MPEG4"
            scene.render.ffmpeg.codec = "H264"
            scene.render.filepath = arg("--mp4")[0]
        else:
            scene.render.image_settings.file_format = "PNG"
            scene.render.use_overwrite = False
            scene.render.use_placeholder = True
            scene.render.filepath = arg("--render-anim")[0].rstrip("/\\") + "/youtube_####"
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
