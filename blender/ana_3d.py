"""
"ana" manuscrito en 3D, estilo tubo inflado brillante (rosa + naranja).

Uso en Blender (4.2 o superior):
  1. Abrí Blender > pestaña "Scripting" > Open > este archivo > Run Script.
  2. O desde terminal:
       blender --background --python ana_3d.py -- --render render.png --save ana.blend

Cada letra es una curva Bezier con bevel redondo: para retocar la forma,
seleccioná el objeto "ana_trazo", entrá en Edit Mode (Tab) y mové los puntos.
"""
import sys
import math
import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------
GROSOR = 0.12          # radio del tubo (altura de la "x" = 1)
INCLINACION = 0.18     # inclinación de la letra (cursiva)
NARANJA = (1.0, 0.20, 0.01, 1.0)
NARANJA_CLARO = (1.0, 0.32, 0.03, 1.0)
ROSA = (1.0, 0.08, 0.32, 1.0)
ROSA_FUCSIA = (0.85, 0.02, 0.38, 1.0)
FONDO = (1.0, 0.78, 0.88, 1.0)

# Cada letra es un trazo propio (x, y) con altura de la "x" = 1.
# Se inclinan, rotan un poco y se superponen en profundidad, como globos.
LETRA_A = [
    (0.70, 0.80), (0.50, 0.99), (0.15, 0.95), (-0.08, 0.66), (-0.10, 0.30),
    (0.05, 0.04), (0.32, 0.00), (0.55, 0.20), (0.68, 0.55), (0.74, 0.97),
    (0.71, 0.50), (0.72, 0.15), (0.82, 0.00), (0.98, 0.04), (1.08, 0.20),
]
LETRA_N = [
    (-0.08, 0.62), (0.02, 0.90), (0.15, 1.00), (0.20, 0.85), (0.17, 0.45),
    (0.14, 0.00), (0.20, 0.50), (0.36, 0.86), (0.58, 1.00), (0.78, 0.88),
    (0.83, 0.55), (0.82, 0.20), (0.90, 0.02), (1.06, 0.00), (1.20, 0.16),
]
# (puntos, desplazamiento x, desplazamiento y, profundidad, rotación en grados)
LETRAS = [
    (LETRA_A, 0.00, 0.00, 0.00, 3),
    (LETRA_N, 1.20, 0.06, -0.12, -2),
    (LETRA_A, 2.45, -0.02, 0.05, 4),
]


def ubicar(puntos, dx, dy, rot):
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    out = []
    for x, y in puntos:
        x = x + y * INCLINACION
        out.append((x * c - y * s + dx, x * s + y * c + dy))
    return out


def limpiar_escena():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def crear_material():
    mat = bpy.data.materials.new("ana_brillo")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    bsdf.inputs["Subsurface Weight"].default_value = 0.0
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.4)
    bsdf.inputs["Subsurface Scale"].default_value = 0.08
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Degradé: mezcla la posición horizontal con una onda vertical para que
    # el naranja y el rosa se alternen a lo largo del trazo, como en la referencia.
    # Coordenadas del objeto "ana_trazo" (las puntas usan las mismas).
    coord = nodes.new("ShaderNodeTexCoord")
    coord.name = "coords"
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Object"], sep.inputs["Vector"])
    rango = nodes.new("ShaderNodeMapRange")
    rango.inputs["From Min"].default_value = -0.1
    rango.inputs["From Max"].default_value = 3.9
    links.new(sep.outputs["X"], rango.inputs["Value"])

    onda = nodes.new("ShaderNodeMath")
    onda.operation = "SINE"
    mult = nodes.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    mult.inputs[1].default_value = 5.0
    links.new(sep.outputs["Z"], mult.inputs[0])
    links.new(mult.outputs["Value"], onda.inputs[0])

    mezcla = nodes.new("ShaderNodeMath")
    mezcla.operation = "MULTIPLY_ADD"
    mezcla.inputs[1].default_value = 0.15
    links.new(onda.outputs["Value"], mezcla.inputs[0])
    links.new(rango.outputs["Result"], mezcla.inputs[2])

    rampa = nodes.new("ShaderNodeValToRGB")
    cr = rampa.color_ramp
    cr.interpolation = "EASE"
    for i, (pos, color) in enumerate([
        (0.05, NARANJA), (0.32, ROSA), (0.55, NARANJA_CLARO), (0.92, ROSA_FUCSIA),
    ]):
        el = cr.elements[i] if i < 2 else cr.elements.new(pos)
        el.position = pos
        el.color = color
    links.new(mezcla.outputs["Value"], rampa.inputs["Fac"])
    links.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def crear_trazo(mat):
    curva = bpy.data.curves.new("ana_trazo", type="CURVE")
    curva.dimensions = "3D"
    curva.resolution_u = 24
    curva.bevel_mode = "ROUND"
    curva.bevel_depth = GROSOR
    curva.bevel_resolution = 10
    curva.use_fill_caps = True

    obj = bpy.data.objects.new("ana_trazo", curva)
    obj.data.materials.append(mat)
    bpy.context.collection.objects.link(obj)

    puntas = []
    for puntos, dx, dy, prof, rot in LETRAS:
        pts = ubicar(puntos, dx, dy, rot)
        spline = curva.splines.new("BEZIER")
        spline.bezier_points.add(len(pts) - 1)
        for i, (bp, (x, y)) in enumerate(zip(spline.bezier_points, pts)):
            # leve ondulación en profundidad para que se vea más orgánico
            z = prof + 0.06 * math.sin(i * 0.9) if i else prof + 0.05
            bp.co = (x, z, y)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        puntas += [spline.bezier_points[0].co.copy(), spline.bezier_points[-1].co.copy()]

    # Puntas redondeadas e infladas tipo globo
    for i, p in enumerate(puntas):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=GROSOR * 1.08, location=p, segments=48, ring_count=24
        )
        s = bpy.context.active_object
        s.name = f"ana_punta_{i}"
        s.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        s.parent = obj
    return obj


def crear_escena(obj):
    scene = bpy.context.scene

    # Centrar
    obj.location = (-1.95, 0, -0.5)
    obj.rotation_euler = (math.radians(6), 0, math.radians(-8))

    # Mundo rosado claro
    world = bpy.data.worlds.new("fondo")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = FONDO
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

    # Pared de fondo para sombras suaves
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 1.2, 0), rotation=(math.pi / 2, 0, 0))
    pared = bpy.context.active_object
    pared.name = "fondo"
    pm = bpy.data.materials.new("fondo")
    pm.use_nodes = True
    pb = pm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = FONDO
    pb.inputs["Roughness"].default_value = 1.0
    pared.data.materials.append(pm)

    # Luces de estudio (área grandes = reflejos largos y suaves)
    def luz(nombre, loc, energia, tamano, color=(1, 1, 1)):
        data = bpy.data.lights.new(nombre, "AREA")
        data.energy = energia
        data.size = tamano
        data.color = color
        o = bpy.data.objects.new(nombre, data)
        o.location = loc
        d = Vector((0, 0, 0)) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(o)

    luz("key", (-3.0, -4.0, 4.0), 500, 4.0)
    luz("fill", (4.0, -3.5, 1.0), 200, 5.0, (1.0, 0.85, 0.9))
    luz("rim", (0.0, 0.5, 4.5), 250, 3.0, (1.0, 0.9, 0.8))

    # Cámara
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 64
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (0.0, -9.0, 0.55)
    cam.rotation_euler = (math.radians(87), 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Render
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1350
    scene.render.resolution_y = 1080
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.1


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    limpiar_escena()
    mat = crear_material()
    obj = crear_trazo(mat)
    mat.node_tree.nodes["coords"].object = obj
    crear_escena(obj)

    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index("--save") + 1])
    if "--render" in argv:
        bpy.context.scene.render.filepath = argv[argv.index("--render") + 1]
        bpy.ops.render.render(write_still=True)


main()
