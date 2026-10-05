"""
"HOLA" en letras infladas de vidrio rosa, apoyadas en un piso blanco.

Uso en Blender (4.2 o superior):
  1. Abrí Blender > pestaña "Scripting" > Open > este archivo > Run Script.
  2. O desde terminal:
       blender --background --python hola_vidrio.py -- --render hola_vidrio.png --save hola_vidrio.blend

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
GROSOR = 0.30            # radio del trazo inflado (alto de letra = 2)
APLASTADO = 0.72         # profundidad relativa: <1 = más "almohadón"
UMBRAL = 0.6             # superficie exterior del metaball
UMBRAL_INTERIOR = 3.2    # pared interna (más alto = vidrio más grueso)
VIDRIO = (1.0, 0.50, 0.70, 1.0)     # rosa del vidrio
ABSORCION = (1.0, 0.30, 0.50, 1.0)  # color que toma en las partes gruesas
DENSIDAD = 4.0                      # cuánto se tiñe en lo grueso
FONDO = (0.80, 0.77, 0.78, 1.0)      # piso/fondo: gris claro (se ve casi blanco)
EXPOSICION = -0.5

# Grosor propio para alguna letra (si no está, usa GROSOR)
GROSOR_LETRA = {"O": 0.34}
SOMBRA = (1.0, 0.22, 0.42, 1.0)    # tinte de la luz que atraviesa el vidrio
REFLEJO_NARANJA = (1.0, 0.45, 0.08, 1.0)
REFLEJO_AMARILLO = (1.0, 0.82, 0.15, 1.0)
INTENSIDAD_REFLEJOS = 45.0
PELICULA_NM = 250.0          # espesor de la película iridiscente (nm); 0 = sin efecto

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
        elipse(2.15, 1.02, 0.58, 0.70),
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
    cam_data.lens = 62
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (2.8, -14.0, 4.2)
    d = Vector((2.8, 0.6, 0.8)) - cam.location
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
    crear_escena(letras)

    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index("--save") + 1])
    if "--render" in argv:
        bpy.context.scene.render.filepath = argv[argv.index("--render") + 1]
        bpy.ops.render.render(write_still=True)


main()
