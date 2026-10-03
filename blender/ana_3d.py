"""
"ana" manuscrito en 3D, estilo tubo inflado brillante (rosa + naranja).

Uso en Blender (4.2 o superior):
  1. Abrí Blender > pestaña "Scripting" > Open > este archivo > Run Script.
  2. O desde terminal:
       blender --background --python ana_3d.py -- --render render.png --save ana.blend

Todo el nombre es una sola curva Bezier con bevel redondo: para retocar la forma,
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

# Trazo continuo de "ana" en (x, y, profundidad), altura de la "x" = 1.
# La profundidad separa los tramos dobles para que se vean dos tubos juntos.
TRAZO = [
    # --- primera "a" (arranca escondida contra el palito)
    (0.70, 0.80, 0.05), (0.50, 0.99, 0.04), (0.15, 0.95, 0.02), (-0.08, 0.66, 0.00),
    (-0.10, 0.30, 0.00), (0.05, 0.04, 0.02), (0.32, 0.00, 0.04), (0.55, 0.20, 0.04),
    (0.68, 0.55, 0.00), (0.74, 0.97, -0.04),
    (0.71, 0.50, 0.04), (0.72, 0.15, 0.04), (0.82, 0.00, 0.03), (0.98, 0.03, 0.02),
    # --- "n" doble: subida y bajada paralelas
    (1.12, 0.18, 0.06), (1.20, 0.52, 0.08), (1.24, 0.85, 0.06), (1.32, 1.02, 0.00),
    (1.44, 0.96, -0.06), (1.50, 0.65, -0.08), (1.50, 0.30, -0.08), (1.47, 0.02, -0.06),
    (1.50, 0.42, 0.02), (1.62, 0.80, 0.04), (1.82, 1.00, 0.04), (2.04, 0.92, 0.04),
    (2.12, 0.60, 0.04), (2.12, 0.25, 0.04), (2.18, 0.04, 0.03), (2.34, 0.00, 0.00),
    # --- conector por arriba (techo doble) + segunda "a"
    (2.46, 0.25, -0.06), (2.52, 0.64, -0.10), (2.64, 1.02, -0.12), (2.88, 1.22, -0.12),
    (3.16, 1.18, -0.10), (3.31, 0.97, -0.04),
    (3.22, 0.80, 0.06), (3.00, 0.90, 0.08), (2.82, 0.85, 0.08), (2.70, 0.60, 0.06),
    (2.68, 0.30, 0.04), (2.82, 0.05, 0.03), (3.07, 0.00, 0.02), (3.27, 0.20, 0.02),
    (3.38, 0.55, 0.00), (3.42, 0.95, -0.02),
    (3.39, 0.50, 0.04), (3.40, 0.15, 0.04), (3.50, 0.00, 0.03), (3.66, 0.04, 0.02),
    (3.78, 0.22, 0.00),
]


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

    spline = curva.splines.new("BEZIER")
    spline.bezier_points.add(len(TRAZO) - 1)
    for bp, (x, y, z) in zip(spline.bezier_points, TRAZO):
        bp.co = (x + y * INCLINACION, z, y)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    puntas = [spline.bezier_points[0].co.copy(), spline.bezier_points[-1].co.copy()]

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
    obj.location = (-1.95, 0, -0.55)
    obj.rotation_euler = (math.radians(4), 0, math.radians(-6))

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
