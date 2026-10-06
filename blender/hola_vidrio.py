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
ABSORCION = (1.0, 0.40, 0.68, 1.0)  # color que toma en las partes gruesas
DENSIDAD = 2.2                      # cuánto se tiñe en lo grueso
FONDO = (0.86, 0.58, 0.66, 1.0)      # piso/fondo: rosa empolvado (deja ver el cristal)
EXPOSICION = -0.5
LUZ_FONDO = 0.30         # brillo propio del estudio (pared lejana)
SOL_SOMBRAS = 9.0        # fuerza de la luz que marca las sombras
GIRO_PALABRA = 0.0       # 0 = de frente; 45 = diagonal; 90 = de perfil

# Grosor propio para alguna letra (si no está, usa GROSOR)
GROSOR_LETRA = {}
SOMBRA = (1.0, 0.22, 0.42, 1.0)    # tinte de la luz que atraviesa el vidrio
REFLEJO_NARANJA = (1.0, 0.45, 0.08, 1.0)
REFLEJO_MAGENTA = (1.0, 0.20, 0.75, 1.0)
REFLEJO_AMARILLO = (1.0, 0.82, 0.15, 1.0)
INTENSIDAD_REFLEJOS = 45.0
PELICULA_NM = 250.0          # espesor de la película iridiscente (nm); 0 = sin efecto

# Transformación a cristal tornasolado (como las A cursivas de referencia)
CRISTAL = (0.97, 0.97, 1.0, 1.0)             # casi incoloro
CRISTAL_ABSORCION = (1.0, 0.85, 0.95, 1.0)   # apenas rosado en lo grueso
CRISTAL_DENSIDAD = 0.04
CRISTAL_PELICULA = (320.0, 760.0)            # nm: rosa, dorado y celeste
SOMBRA_CRISTAL = [          # sombra del cristal: semitransparente y teñida
    (0.0, (0.55, 0.36, 0.55, 1.0)),          # (1 = sin sombra, 0 = sombra negra)
    (0.4, (0.58, 0.50, 0.32, 1.0)),
    (0.7, (0.36, 0.50, 0.58, 1.0)),
    (1.0, (0.58, 0.38, 0.48, 1.0)),
]
CORTE_INICIAL = -1.0       # altura del corte: -1 = todo rosa, 3 = todo cristal

# Animación (a 24 cuadros por segundo): las letras de vidrio caen del cielo
# mientras la cámara da medio giro alrededor de la palabra; al final se
# transforman de rosa a cristal tornasolado, subiendo desde el piso.
FPS = 24
CUADROS = 300              # 12,5 segundos
# cuadro en que se suelta cada letra (ritmo irregular: H… O.L… A)
SUELTA = {"H": 10, "O": 28, "L": 37, "A": 56}
ALTURA_CAIDA = {"H": 9.0, "O": 9.0, "L": 9.0, "A": 12.0}   # la A cae con más fuerza
GIRO_CAIDA = {             # giro inicial (x, y, z en grados): se endereza al caer
    "H": (18, -22, 10), "O": (-15, 25, -12), "L": (20, 18, 8), "A": (-22, -28, -15)}
GRAVEDAD = 9.8
REBOTE = 0.12              # vidrio pesado: rebota poco
APLASTE = 0.09             # y se aplasta apenas
EMPUJON = 0.05             # cuánto empuja cada letra a la anterior al caer
GOTITAS = 6                # gotitas de vidrio que saltan en cada impacto
CAMARA_DESDE = 180.0       # ángulo inicial (180 = detrás de la palabra)
CAMARA_HASTA = 0.0         # ángulo final (0 = de frente)
CAMARA_FRENTE = 116        # cuadro en que la cámara pasa por el frente
# después del frente sigue girando cada vez más lento (~30° más) durante la transformación
CAMARA_DISTANCIA = 15.5    # durante el giro
CAMARA_DISTANCIA_FINAL = 13.2  # se acerca al terminar
CAMARA_ALTURA = 3.6
CAMARA_SIGUE = 0.35        # cuánto acompaña la cámara a la letra que cae
TRANSFORMA_DESDE = 116     # la transformación a cristal sube desde el piso
TRANSFORMA_HASTA = 164
CIERRE_DESDE = 160         # la cámara se acerca y recorre el cristal de cerca
CIERRE_ANGULO = -40.0      # ángulo final de la cámara (0 = de frente)
CIERRE_DISTANCIA = 8.5     # distancia en el primer plano final
CIERRE_ALTURA = 1.9        # altura de la cámara en el primer plano (desde el piso)
CIERRE_RECORRE = 0.9       # cuánto se desplaza la mirada de la H hacia la A
DESENFOQUE_MOVIMIENTO = 0.5   # 0 = sin desenfoque de movimiento

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
        elipse(2.15, 1.02, 0.50, 0.66),  # mismo trazo que el resto; agujero chico
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
    exterior.data.materials.append(mat)
    interior.data.materials.append(material_interior(mat))
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


def suave(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def caida(t, h0):
    """Altura, aplaste e impactos de una letra que cae desde h0 y rebota.

    t en segundos desde que se suelta. aplaste > 0 = aplastada, < 0 = estirada.
    impactos = [(segundo, velocidad)].
    """
    altura, v, tt = h0, 0.0, 0.0
    impactos = []
    paso = 1.0 / (FPS * 8)
    while tt < t:
        v -= GRAVEDAD * paso
        altura += v * paso
        if altura <= 0 and v < 0:
            impactos.append((tt, -v))
            altura = 0.0
            v = -v * REBOTE
            if v < 0.6:
                v = 0.0
        tt += paso
    altura = max(0.0, altura)
    aplaste = 0.0
    for ti, vel in impactos:
        dt = t - ti
        fuerza = APLASTE * min(1.3, vel / 12.0)
        aplaste += fuerza * math.exp(-dt / 0.07) * math.cos(2 * math.pi * dt / 0.22)
    if not impactos:  # mientras cae, se estira un poquito según la velocidad
        aplaste -= min(0.05, abs(v) / 250.0)
    return altura, aplaste, impactos


def animar(letras, scene, mat):
    """Caída de las letras, cámara en semicírculo y transformación a cristal."""
    import random
    azar = random.Random(7)
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, CUADROS
    if DESENFOQUE_MOVIMIENTO:
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = DESENFOQUE_MOVIMIENTO

    nombres = [o.name.replace("letra_", "") for o in letras]
    datos = {}
    for n in nombres:
        h0 = ALTURA_CAIDA[n]
        _, _, imp = caida(10.0, h0)
        datos[n] = {"h0": h0, "suelta": SUELTA[n], "impactos": imp,
                    "llega": SUELTA[n] + imp[0][0] * FPS}

    # empujones: cuando cae una letra, la anterior se corre un poquito y vuelve
    def empujon(i, t_abs):
        dx = 0.0
        if i + 1 < len(nombres):
            sig = datos[nombres[i + 1]]
            dt = t_abs - sig["llega"] / FPS
            if dt > 0:
                fuerza = EMPUJON * min(1.4, sig["impactos"][0][1] / 13.0)
                dx = -fuerza * math.exp(-dt / 0.12) * math.sin(2 * math.pi * dt / 0.32)
        return dx

    for i, (o, n) in enumerate(zip(letras, nombres)):
        d = datos[n]
        x0, z0 = o.location.x, o.location.z
        rx, ry, rz = (math.radians(a) for a in GIRO_CAIDA[n])
        t_vuelo = d["impactos"][0][0]
        for f in range(1, CUADROS + 1):
            t = (f - d["suelta"]) / FPS
            if t < 0:
                altura, ap = d["h0"], 0.0
            else:
                altura, ap, _ = caida(t, d["h0"])
            # gira mientras cae y se endereza justo al tocar el piso;
            # después, un bamboleo chiquito que se apaga
            if t < t_vuelo:
                k = (1 - suave(max(0.0, t) / t_vuelo)) if t >= 0 else 1.0
                bam = 0.0
            else:
                k = 0.0
                dt = t - t_vuelo
                bam = math.radians(3) * math.exp(-dt / 0.2) * math.sin(2 * math.pi * dt / 0.35)
            o.rotation_euler = (rx * k, ry * k + bam, rz * k)
            o.location.z = z0 + altura
            o.location.x = x0 + empujon(i, f / FPS)
            o.scale = (1 + 0.5 * ap, 1 + 0.5 * ap, 1 - ap)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
            o.keyframe_insert("scale", frame=f)

        # gotitas de vidrio que saltan al tocar el piso
        base = o.matrix_world.translation.copy()
        base.z = 0.0
        ancho = o.dimensions.x * 0.45
        t_imp = d["llega"] / FPS
        vel_imp = d["impactos"][0][1]
        for g in range(GOTITAS):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=azar.uniform(0.035, 0.08),
                                                 segments=16, ring_count=8)
            gota = bpy.context.active_object
            gota.name = f"gotita_{n}_{g}"
            bpy.ops.object.shade_smooth()
            gota.data.materials.append(mat)
            ang = azar.uniform(0, 2 * math.pi)
            vh = azar.uniform(0.8, 2.0) * vel_imp / 12.0
            vz = azar.uniform(1.8, 3.2) * vel_imp / 12.0
            p0 = base + Vector((azar.uniform(-ancho, ancho), azar.uniform(-0.2, 0.2), 0.08))
            vida = azar.uniform(0.45, 0.7)
            for f in range(1, CUADROS + 1):
                t = f / FPS - t_imp
                if t < 0 or t > vida + 0.1:
                    gota.scale = (0.0, 0.0, 0.0)
                    gota.location = p0
                else:
                    z = max(0.04, vz * t - 0.5 * GRAVEDAD * t * t + 0.08)
                    gota.location = p0 + Vector((vh * math.cos(ang) * t, vh * math.sin(ang) * t, z - 0.08))
                    s = 1.0 - suave((t - vida * 0.6) / (vida * 0.4))
                    gota.scale = (s, s, s)
                gota.keyframe_insert("location", frame=f)
                gota.keyframe_insert("scale", frame=f)

    # Cámara: medio círculo alrededor del centro, acompañando la caída
    cam = scene.camera
    centro = bpy.data.objects["centro"].location.copy()
    mira = bpy.data.objects["mira"]
    llega_a = datos[nombres[-1]]["llega"]
    objetivos = []
    for f in range(1, CUADROS + 1):
        # la letra que está cayendo (la más reciente en el aire)
        dx = dz = 0.0
        for o, n in zip(letras, nombres):
            d = datos[n]
            t = (f - d["suelta"]) / FPS
            if 0 <= t < d["impactos"][0][0]:
                altura, _, _ = caida(t, d["h0"])
                peso = suave(t / 0.35)
                dz = CAMARA_SIGUE * min(altura, 4.5) * peso
                dx = CAMARA_SIGUE * (o.matrix_world.translation.x - centro.x) * peso
        objetivos.append(Vector((dx, 0.0, dz)))
    # Ángulo de la cámara: acelera al principio, pasa por el frente en
    # CAMARA_FRENTE y sigue girando cada vez más lento mientras las letras se
    # transforman (velocidad continua, sin frenadas bruscas).
    def velocidad(f):
        if f <= CAMARA_FRENTE:
            return suave((f - 1) / 30) * (1 - 0.6 * suave((f - 60) / (CAMARA_FRENTE - 60)))
        # sigue girando y va frenando de a poco hasta CIERRE_ANGULO
        return 0.4 * (1 - suave((f - CAMARA_FRENTE) / largo_frenada))
    previo = [0.0]
    for f in range(2, CAMARA_FRENTE + 1):
        previo.append(previo[-1] + velocidad(f) if f <= CAMARA_FRENTE else 0)
    k0 = (CAMARA_DESDE - CAMARA_HASTA) / previo[-1]
    # largo de la frenada para terminar justo en CIERRE_ANGULO (área = 0.4·L/2)
    largo_frenada = max(10.0, 2 * (CAMARA_HASTA - CIERRE_ANGULO) / (k0 * 0.4))
    acum = [0.0]
    for f in range(2, CUADROS + 1):
        acum.append(acum[-1] + velocidad(f))
    k = (CAMARA_DESDE - CAMARA_HASTA) / acum[CAMARA_FRENTE - 1]
    angulos = [CAMARA_DESDE - k * c for c in acum]
    print("cámara: ángulo final %.1f°" % angulos[-1])

    # suavizado para que la cámara no dé tirones
    suavizados = []
    for i in range(len(objetivos)):
        ventana = objetivos[max(0, i - 6):i + 7]
        suavizados.append(sum(ventana, Vector()) / len(ventana))
    for f in range(1, CUADROS + 1):
        ang = math.radians(angulos[f - 1])
        dist = CAMARA_DISTANCIA + (CAMARA_DISTANCIA_FINAL - CAMARA_DISTANCIA) * suave((f - 80) / 50)
        # primer plano final: se acerca, baja y la mirada recorre la palabra
        c = suave((f - CIERRE_DESDE) / 70)
        dist += (CIERRE_DISTANCIA - dist) * c
        alto = (CAMARA_ALTURA - 0.9) + (CIERRE_ALTURA - 0.9 - (CAMARA_ALTURA - 0.9)) * c
        recorre = CIERRE_RECORRE * (2 * suave((f - CIERRE_DESDE) / (CUADROS - CIERRE_DESDE)) - 1) * c
        sacudon = Vector()
        dt = (f - llega_a) / FPS
        if 0 <= dt < 0.3:  # la A cae fuerte: la cámara tiembla apenas
            sacudon = Vector((0, 0, 0.05 * math.exp(-dt / 0.08) * math.sin(dt * 60)))
        cam.location = centro + Vector((dist * math.sin(ang) + recorre * 0.6,
                                        -dist * math.cos(ang), alto)) + sacudon
        cam.keyframe_insert("location", frame=f)
        mira.location = centro + suavizados[f - 1] + Vector((recorre, 0.0, -0.15 * c))
        mira.keyframe_insert("location", frame=f)

    # Transformación de rosa a cristal: el corte sube desde abajo del piso
    for m in (mat, bpy.data.materials["vidrio_interior"]):
        valor = m.node_tree.nodes["corte"].outputs[0]
        for f, v in ((TRANSFORMA_DESDE, -1.0), (TRANSFORMA_HASTA, 3.0)):
            valor.default_value = v
            valor.keyframe_insert("default_value", frame=f)

    for o in letras + [cam, mira]:
        for fc in iter_fcurves(o.animation_data.action):
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"


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
    """Vidrio que puede pasar de rosa a cristal tornasolado.

    El valor "corte" (altura en metros) separa las dos versiones: por debajo
    del corte la letra ya es cristal, por encima sigue rosa. Animando el corte
    de abajo hacia arriba, la transformación sube desde el piso.
    """
    mat = bpy.data.materials.new("vidrio_rosa")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")

    # --- factor de transformación: 0 = rosa, 1 = cristal
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Position"], sep.inputs["Vector"])
    corte = nodes.new("ShaderNodeValue")
    corte.name = "corte"
    corte.outputs[0].default_value = CORTE_INICIAL
    fac = nodes.new("ShaderNodeMapRange")  # suave en una franja de 0.5 m
    links.new(sep.outputs["Z"], fac.inputs["Value"])
    resta = nodes.new("ShaderNodeMath")
    resta.operation = "SUBTRACT"
    links.new(corte.outputs[0], resta.inputs[0])
    resta.inputs[1].default_value = 0.5
    links.new(resta.outputs[0], fac.inputs["From Max"])
    links.new(corte.outputs[0], fac.inputs["From Min"])
    fac.clamp = True
    fac.name = "factor_cristal"
    f = fac.outputs["Result"]

    def mezclar(a, b, tipo="FLOAT"):
        m = nodes.new("ShaderNodeMix")
        m.data_type = tipo
        links.new(f, m.inputs["Factor"])
        entrada_a = m.inputs[6] if tipo == "RGBA" else m.inputs[2]
        entrada_b = m.inputs[7] if tipo == "RGBA" else m.inputs[3]
        for entrada, v in ((entrada_a, a), (entrada_b, b)):
            if hasattr(v, "links"):
                links.new(v, entrada)
            else:
                entrada.default_value = v
        return m.outputs[2] if tipo == "RGBA" else m.outputs[0]

    # --- arcoíris: película más gruesa y variable en el cristal
    coords = nodes.new("ShaderNodeTexCoord")
    ruido = nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 1.6
    ruido.inputs["Detail"].default_value = 2.0
    links.new(coords.outputs["Object"], ruido.inputs["Vector"])
    espesor = nodes.new("ShaderNodeMapRange")
    espesor.inputs["To Min"].default_value = CRISTAL_PELICULA[0]
    espesor.inputs["To Max"].default_value = CRISTAL_PELICULA[1]
    links.new(ruido.outputs["Fac"], espesor.inputs["Value"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.5
    links.new(mezclar(VIDRIO, CRISTAL, "RGBA"), bsdf.inputs["Base Color"])
    links.new(mezclar(PELICULA_NM, espesor.outputs["Result"]), bsdf.inputs["Thin Film Thickness"])
    # índice de la película: suave en el rosa, alto (colores intensos) en el cristal
    links.new(mezclar(1.33, 1.8), bsdf.inputs["Thin Film IOR"])

    # --- sombra: rosa antes, sombras de colores pastel en el cristal
    paleta = nodes.new("ShaderNodeValToRGB")
    cr = paleta.color_ramp
    for i, (pos, col) in enumerate(SOMBRA_CRISTAL):
        el = cr.elements[i] if i < 2 else cr.elements.new(pos)
        el.position, el.color = pos, col
    links.new(ruido.outputs["Fac"], paleta.inputs["Fac"])
    camino = nodes.new("ShaderNodeLightPath")
    trans = nodes.new("ShaderNodeBsdfTransparent")
    links.new(mezclar(SOMBRA, paleta.outputs["Color"], "RGBA"), trans.inputs["Color"])
    mezcla = nodes.new("ShaderNodeMixShader")
    links.new(camino.outputs["Is Shadow Ray"], mezcla.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mezcla.inputs[1])
    links.new(trans.outputs["BSDF"], mezcla.inputs[2])
    links.new(mezcla.outputs["Shader"], out.inputs["Surface"])

    # --- absorción: rosa en lo grueso antes; casi nada en el cristal.
    # En el volumen la posición no sirve para el corte, así que el tinte
    # interno se apaga apenas arranca el corte (de -1 a 0.3 m), así la
    # letra no se oscurece cuando por dentro pasa de hueca a maciza.
    fac_vol = nodes.new("ShaderNodeMapRange")
    fac_vol.inputs["From Min"].default_value = -1.0
    fac_vol.inputs["From Max"].default_value = 0.3
    links.new(corte.outputs[0], fac_vol.inputs["Value"])
    f = fac_vol.outputs["Result"]
    vol = nodes.new("ShaderNodeVolumeAbsorption")
    links.new(mezclar(ABSORCION, CRISTAL_ABSORCION, "RGBA"), vol.inputs["Color"])
    links.new(mezclar(DENSIDAD, CRISTAL_DENSIDAD), vol.inputs["Density"])
    links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def material_interior(mat):
    """Pared interna: igual al vidrio mientras es rosa (letra hueca), y se
    vuelve invisible al pasar a cristal (la letra se ve maciza)."""
    if "vidrio_interior" in bpy.data.materials:
        return bpy.data.materials["vidrio_interior"]
    m = mat.copy()
    m.name = "vidrio_interior"
    nodes, links = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    superficie_actual = out.inputs["Surface"].links[0].from_socket
    trans = nodes.new("ShaderNodeBsdfTransparent")
    mezcla = nodes.new("ShaderNodeMixShader")
    links.new(nodes["factor_cristal"].outputs["Result"], mezcla.inputs["Fac"])
    links.new(superficie_actual, mezcla.inputs[1])
    links.new(trans.outputs["BSDF"], mezcla.inputs[2])
    links.new(mezcla.outputs["Shader"], out.inputs["Surface"])
    # sin volumen propio: si no, Blender tiñe también el aire de adentro
    for l in list(out.inputs["Volume"].links):
        links.remove(l)
    return m


def crear_escena(letras):
    scene = bpy.context.scene

    # Estudio redondo: piso + pared curva alrededor, así la cámara puede girar
    # sin ver bordes ni horizonte.
    import bmesh
    xs = [(o.matrix_world @ o.data.vertices[i].co).x for o in letras
          for i in range(0, len(o.data.vertices), 50)]
    cx = (min(xs) + max(xs)) / 2
    me = bpy.data.meshes.new("ciclorama")
    piso = bpy.data.objects.new("ciclorama", me)
    scene.collection.objects.link(piso)
    bm = bmesh.new()
    radio_piso, curva, alto, lados = 18.0, 5.0, 30.0, 96
    perfil = [(0.0, 0.0), (radio_piso * 0.5, 0.0), (radio_piso, 0.0)]
    for i in range(1, 17):
        a = (math.pi / 2) * i / 16
        perfil.append((radio_piso + curva * math.sin(a), curva - curva * math.cos(a)))
    perfil.append((radio_piso + curva, alto))
    anillos = []
    for r, z in perfil[1:]:
        anillos.append([bm.verts.new((r * math.cos(2 * math.pi * k / lados),
                                      r * math.sin(2 * math.pi * k / lados), z))
                        for k in range(lados)])
    centro_v = bm.verts.new((0.0, 0.0, 0.0))
    for k in range(lados):
        bm.faces.new((centro_v, anillos[0][k], anillos[0][(k + 1) % lados]))
    for a0, a1 in zip(anillos, anillos[1:]):
        for k in range(lados):
            k2 = (k + 1) % lados
            bm.faces.new((a0[k], a1[k], a1[k2], a0[k2]))
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.objects.active = piso
    pm = bpy.data.materials.new("piso")
    pm.use_nodes = True
    pb = pm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = FONDO
    pb.inputs["Roughness"].default_value = 0.6
    pb.inputs["Specular IOR Level"].default_value = 0.0  # mate: no refleja las tarjetas de color
    # Un poco de luz propia para que la pared lejana no se vea gris
    pn, pl = pm.node_tree.nodes, pm.node_tree.links
    em = pn.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = FONDO
    # solo lejos de las letras (no donde caen las sombras)
    coords = pn.new("ShaderNodeTexCoord")
    largo = pn.new("ShaderNodeVectorMath")
    largo.operation = "LENGTH"
    pl.new(coords.outputs["Object"], largo.inputs[0])
    lejos = pn.new("ShaderNodeMapRange")
    lejos.inputs["From Min"].default_value = 6.0
    lejos.inputs["From Max"].default_value = 16.0
    lejos.inputs["To Max"].default_value = LUZ_FONDO
    lejos.interpolation_type = "SMOOTHSTEP"
    pl.new(largo.outputs["Value"], lejos.inputs["Value"])
    pl.new(lejos.outputs["Result"], em.inputs["Strength"])
    suma = pn.new("ShaderNodeAddShader")
    pl.new(pb.outputs["BSDF"], suma.inputs[0])
    pl.new(em.outputs["Emission"], suma.inputs[1])
    pl.new(suma.outputs["Shader"], pn["Material Output"].inputs["Surface"])
    me.materials.append(pm)
    piso.location = (cx, 0.0, 0.0)
    piso.visible_shadow = False  # la pared alta no tapa las luces (si no, no hay sombras en el piso)

    # Mundo blanco suave
    world = bpy.data.worlds.new("mundo")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.06

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
        o.visible_camera = False
        scene.collection.objects.link(o)
        return o

    # Luz principal arriba-izquierda-adelante: la sombra rosada cae atrás a la derecha
    key = luz("principal", (-4.0, -2.5, 4.5), 1200, 3.0, 3.0, apertura=180)
    # Sol suave: da la sombra definida de las letras en el piso (rosa o de colores)
    sol = bpy.data.lights.new("sol_sombras", "SUN")
    sol.energy = SOL_SOMBRAS
    sol.angle = math.radians(6)
    so = bpy.data.objects.new("sol_sombras", sol)
    # viene de atrás a la izquierda: la sombra cae hacia adelante y a la derecha
    so.rotation_euler = Vector((0.55, -0.75, -0.75)).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(so)
    # Relleno frontal grande y suave
    luz("relleno", (2.8, -8.0, 3.0), 120, 8.0, 4.0)
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
        ("tarjeta_magenta", REFLEJO_MAGENTA, (-3.5, -7.0, 3.0), (math.radians(80), 0, math.radians(-35)), (1.2, 3.0, 1)),
        ("tarjeta_magenta_2", REFLEJO_MAGENTA, (9.0, -6.0, 1.2), (math.pi / 2, 0, math.radians(45)), (1.0, 2.5, 1)),
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
    cam_data.lens = 62 if GIRO_PALABRA < 30 else 80
    cam = bpy.data.objects.new("cam", cam_data)
    # Centro de la palabra y cámara girada CAMARA_ANGULO grados alrededor de ella
    xs = [(o.matrix_world @ o.data.vertices[i].co).x for o in letras
          for i in range(0, len(o.data.vertices), 50)]
    centro = Vector(((min(xs) + max(xs)) / 2, 0.0, 0.9))
    cam.location = centro + Vector((0.0, -CAMARA_DISTANCIA, CAMARA_ALTURA - 0.9))
    objetivo = bpy.data.objects.new("centro", None)
    objetivo.location = centro
    scene.collection.objects.link(objetivo)
    punto = bpy.data.objects.new("mira", None)  # adonde mira la cámara
    punto.location = centro
    scene.collection.objects.link(punto)
    mira = cam.constraints.new("TRACK_TO")
    mira.target = punto
    mira.track_axis = "TRACK_NEGATIVE_Z"
    mira.up_axis = "UP_Y"
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
        animar(letras, scene, mat)
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
