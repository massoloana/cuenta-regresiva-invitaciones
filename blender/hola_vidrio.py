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
VIDRIO = (1.0, 0.48, 0.63, 1.0)     # rosa del vidrio
ABSORCION = (1.0, 0.30, 0.50, 1.0)  # color que toma en las partes gruesas
DENSIDAD = 4.0                      # cuánto se tiñe en lo grueso
FONDO = (1.0, 0.96, 0.97, 1.0)      # piso/fondo blanco apenas rosado
EXPOSICION = 0.0

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
        elipse(2.15, 1.00, 0.62, 0.70),
    ],
    "L": [
        [(3.31, 1.70), (3.31, 0.30), (3.91, 0.30)],
    ],
    "A": [
        [(4.47, 0.30), (4.81, 1.36), (4.93, 1.66), (5.05, 1.72),
         (5.17, 1.66), (5.29, 1.36), (5.63, 0.30)],
        [(4.71, 0.78), (5.39, 0.78)],
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


def superficie(nombre, trazos, umbral):
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
            el.radius = GROSOR * 1.25
            el.stiffness = 2.0
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.active_object
    obj.name = nombre
    return obj


def crear_letra(nombre, trazos, mat):
    exterior = superficie(f"letra_{nombre}", trazos, UMBRAL)
    # Pared interna: la misma forma un poco más chica, con normales hacia
    # adentro. Así la letra es un casco de vidrio hueco, como un globo.
    interior = superficie(f"interior_{nombre}", trazos, UMBRAL_INTERIOR)
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
    bsdf.inputs["IOR"].default_value = 1.45
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
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
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25

    def luz(nombre, loc, energia, ancho, alto, mirar=(2.8, 0, 1)):
        data = bpy.data.lights.new(nombre, "AREA")
        data.shape = "RECTANGLE"
        data.size, data.size_y = ancho, alto
        data.energy = energia
        data.spread = math.radians(70)
        o = bpy.data.objects.new(nombre, data)
        o.location = loc
        d = Vector(mirar) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(o)
        return o

    # Luz principal arriba-izquierda-atrás: proyecta la sombra rosada hacia adelante
    key = luz("principal", (-1.0, 4.0, 6.5), 2500, 2.5, 2.5)
    key.data.cycles.is_caustics_light = True
    # Relleno frontal grande y suave
    luz("relleno", (2.9, -8.0, 3.0), 500, 8.0, 4.0)
    # Tiras laterales: bordes brillantes en el vidrio
    luz("tira_izq", (-3.5, -1.5, 2.0), 300, 0.5, 4.0)
    luz("tira_der", (9.5, -1.0, 2.0), 300, 0.5, 4.0)

    # Cáusticas: la luz atraviesa el vidrio y tiñe el piso de rosa
    piso.cycles.is_caustics_receiver = True
    for o in letras:
        o.cycles.is_caustics_caster = True

    # Cámara
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 62
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (2.8, -14.0, 2.2)
    d = Vector((2.8, 0, 1.0)) - cam.location
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
    scene.cycles.caustics_reflective = True
    scene.cycles.caustics_refractive = True
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1080
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = EXPOSICION


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    limpiar_escena()
    mat = crear_vidrio()
    letras = [crear_letra(n, t, mat) for n, t in LETRAS.items()]
    crear_escena(letras)

    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index("--save") + 1])
    if "--render" in argv:
        bpy.context.scene.render.filepath = argv[argv.index("--render") + 1]
        bpy.ops.render.render(write_still=True)


main()
