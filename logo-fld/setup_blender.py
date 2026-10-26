"""Arma la escena del logo FDL en Blender: importa logo-fld.glb, crea el material
metálico azul -> violeta, la iluminación de estudio, la cámara isométrica y el render.

Uso:
  - Desde Blender: abrir la pestaña Scripting, abrir este archivo y pulsar Run Script.
    (logo-fld.glb tiene que estar en la misma carpeta que este script.)
  - Por consola: blender -b -P setup_blender.py -- [--render salida.png] [--save escena.blend]
                                                  [--samples 256] [--res 2048] [--fondo blanco|transparente]
                                                  [--frame N] [--video salida.mp4] [--frames carpeta]
"""
import math
import os
import sys

import bpy
import bmesh  # después de bpy: fuera de Blender solo existe una vez cargado bpy
from mathutils import Vector

# ---------------------------------------------------------------- parámetros
COLOR_STOPS = [  # degradado en pantalla: arriba-izquierda -> abajo-derecha
    (0.00, "#2C9FE0"),
    (0.45, "#2B4CC0"),
    (1.00, "#6A2DBE"),
]
ROUGHNESS = 0.14     # más bajo = más espejado
COAT = 0.3           # capa de barniz que da el brillo "pulido"
SMOOTH_ANGLE = 40    # grados: los biseles se ven lisos, las caras planas quedan con aristas definidas
RESOLUTION = 2048
SAMPLES = 256
FONDO = "blanco"     # "blanco" (infinito blanco) o "transparente"
FONDO_EMISION = 2.2 # cuánto "brilla" el blanco del fondo (más alto = más blanco, sombras más suaves)
FLOTA = 2.5          # distancia entre las letras y el piso (la sombra se separa del logo)
ANIM_FRAMES = 150    # 5 s a 30 fps: entrada ~2,5 s + logo quieto
ANIM_MOTION_END = 76 # último cuadro con movimiento (el giro del logo termina en el 75)


def script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass
    for t in bpy.data.texts:
        if t.filepath:
            return os.path.dirname(bpy.path.abspath(t.filepath))
    return os.getcwd()


def hex_rgba(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


# ---------------------------------------------------------------- escena
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_letters(path):
    bpy.ops.import_scene.gltf(filepath=path)
    letters = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in letters:
        for attr in list(o.data.color_attributes):  # el degradado lo hace el material
            o.data.color_attributes.remove(attr)
        o.data.materials.clear()
        # three.js exporta cada triángulo suelto: se sueldan los vértices para poder suavizar
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bm.to_mesh(o.data); bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    for o in letters:
        o.select_set(True)
    bpy.context.view_layer.objects.active = letters[0]
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(SMOOTH_ANGLE))
    return letters


def make_material():
    mat = bpy.data.materials.new("Metal FDL")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (600, 0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = ROUGHNESS
    bsdf.inputs["Coat Weight"].default_value = COAT
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    # Película fina: un leve tornasol en los reflejos, como el cromo anodizado
    bsdf.inputs["Thin Film Thickness"].default_value = 260
    bsdf.inputs["Thin Film IOR"].default_value = 1.4
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Degradado en diagonal de pantalla usando coordenadas de cámara (x - y)
    tc = nodes.new("ShaderNodeTexCoord"); tc.location = (-800, 0)
    sep = nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-600, 0)
    sub = nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.location = (-400, 0)
    rng = nodes.new("ShaderNodeMapRange"); rng.location = (-200, 0)
    rng.inputs["From Min"].default_value = -8.0
    rng.inputs["From Max"].default_value = 8.0
    ramp = nodes.new("ShaderNodeValToRGB"); ramp.location = (50, 0)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = COLOR_STOPS[0][0], hex_rgba(COLOR_STOPS[0][1])
    els[1].position, els[1].color = COLOR_STOPS[-1][0], hex_rgba(COLOR_STOPS[-1][1])
    for pos, col in COLOR_STOPS[1:-1]:
        e = els.new(pos); e.color = hex_rgba(col)
    links.new(tc.outputs["Camera"], sep.inputs["Vector"])
    links.new(sep.outputs["X"], sub.inputs[0])
    links.new(sep.outputs["Y"], sub.inputs[1])
    links.new(sub.outputs["Value"], rng.inputs["Value"])
    links.new(rng.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    # El barniz toma un poco del color para que los reflejos no queden grises
    links.new(ramp.outputs["Color"], bsdf.inputs["Coat Tint"])
    return mat


def make_world():
    """Estudio procedural: cielo claro arriba, horizonte gris, piso oscuro.
    Es lo que el metal refleja; el fondo del render sale transparente."""
    world = bpy.data.worlds.new("Estudio")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld"); out.location = (600, 0)
    bg = nodes.new("ShaderNodeBackground"); bg.location = (400, 0)
    bg.inputs["Strength"].default_value = 0.7
    tc = nodes.new("ShaderNodeTexCoord"); tc.location = (-400, 0)
    sep = nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-200, 0)
    ramp = nodes.new("ShaderNodeValToRGB"); ramp.location = (0, 0)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.30, 0.30, 0.34, 1)   # piso
    els[1].position, els[1].color = 1.0, (1.0, 1.0, 1.0, 1)      # cenit
    e = els.new(0.47); e.color = (0.12, 0.12, 0.15, 1)           # banda oscura bajo el horizonte
    e = els.new(0.53); e.color = (0.85, 0.85, 0.9, 1)            # horizonte claro: brillo en las caras
    e = els.new(0.75); e.color = (0.45, 0.45, 0.5, 1)
    rng = nodes.new("ShaderNodeMapRange"); rng.location = (-100, -200)
    rng.inputs["From Min"].default_value = -1.0
    rng.inputs["From Max"].default_value = 1.0
    links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], rng.inputs["Value"])
    links.new(rng.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_area(name, loc, target, size, energy, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size, data.size_y = size
    data.energy = energy
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_softbox(name, loc, target, size, strength, color=(1, 1, 1)):
    """Panel emisor que el metal refleja como una franja de luz; la cámara no lo ve."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], 1)
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("Z", "Y").to_euler()
    obj.visible_camera = False
    obj.visible_shadow = False
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi, pts


def setup_camera(objs):
    lo, hi, pts = bounds(objs)
    center = (lo + hi) / 2
    cam_data = bpy.data.cameras.new("Camara iso")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("Camara iso", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    # Vista isométrica: mirando desde (+X, -Y, +Z), igual que el render de three.js
    cam.rotation_euler = (math.radians(54.7356), 0, math.radians(45))
    view_dir = cam.rotation_euler.to_matrix() @ Vector((0, 0, 1))
    cam.location = center + view_dir * 60
    cam_data.clip_end = 500
    bpy.context.view_layer.update()
    # Encuadre: centra las letras en pantalla y deja ~12% de margen
    inv = cam.matrix_world.inverted()
    local = [inv @ p for p in pts]
    xs, ys = [p.x for p in local], [p.y for p in local]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    cam.location = cam.matrix_world @ Vector((cx, cy, 0))
    cam_data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.12
    bpy.context.scene.camera = cam
    return cam, center


def make_cyclorama(center, floor_z):
    """Infinito blanco: piso + curva + pared, una sola pieza sin aristas.
    La pared queda del lado opuesto a la cámara, así el fondo nunca muestra un corte."""
    R, FLOOR, WALL, WIDTH, BACK = 25.0, 120.0, 120.0, 300.0, 40.0
    profile = [(-FLOOR, 0.0)]
    for i in range(0, 25):  # cuarto de círculo
        a = math.radians(90 * i / 24)
        profile.append((BACK + R * math.sin(a), R * (1 - math.cos(a))))
    profile.append((BACK + R, WALL))
    verts, faces = [], []
    for u, z in profile:
        verts += [(-WIDTH / 2, u, z), (WIDTH / 2, u, z)]
    for i in range(len(profile) - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    mesh = bpy.data.meshes.new("Infinito")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Infinito blanco", mesh)
    bpy.context.scene.collection.objects.link(obj)
    # local +Y = "hacia el fondo": se orienta en la dirección horizontal opuesta a la cámara (-X, +Y)
    obj.rotation_euler = (0, 0, math.radians(45))
    obj.location = (center.x, center.y, floor_z)
    for p in obj.data.polygons:
        p.use_smooth = True
    # El piso recibe sombra pero el metal no lo refleja (si no, las caras se lavan de blanco)
    obj.visible_glossy = False
    obj.visible_shadow = False

    mat = bpy.data.materials.new("Infinito blanco")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.92, 0.92, 0.93, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    # Un poco de emisión propia: el blanco se mantiene blanco y las sombras quedan suaves
    bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Emission Strength"].default_value = FONDO_EMISION
    obj.data.materials.append(mat)
    return obj


def animate_entrance(letters, center):
    """Entrada para redes: cada letra llega desde su lado girando, el logo completo
    gira 70° hasta quedar en la vista del logo y se queda quieto para que se lea."""
    sc = bpy.context.scene
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, ANIM_FRAMES

    pivot = bpy.data.objects.new("Logo (pivote)", None)
    sc.collection.objects.link(pivot)
    pivot.location = center
    bpy.context.view_layer.update()
    for o in letters:
        mw = o.matrix_world.copy()
        o.rotation_mode = "XYZ"  # el importador de glTF deja cuaterniones; se anima en Euler
        o.parent = pivot
        o.matrix_world = mw

    def key(obj, path, frame, value, interp="BEZIER", easing="AUTO"):
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=frame)
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    if kp.co.x == frame:
                        kp.interpolation, kp.easing = interp, easing

    by_name = {o.name: o for o in letters}
    # (letra, desde dónde llega, eje de giro, cuadro de inicio)
    entries = [("D", Vector((0, -18, 0)), 2, 1), ("L", Vector((18, 0, 0)), 2, 9), ("F", Vector((0, 0, 18)), 2, 17)]
    for name, offset, axis, start in entries:
        o = by_name.get(name)
        if o is None:
            continue
        end = start + 34
        home_loc, home_rot = o.location.copy(), o.rotation_euler.copy()
        o.location = home_loc + offset
        r = home_rot.copy(); r[axis] -= math.radians(120)
        o.rotation_euler = r
        o.keyframe_insert("location", frame=start)
        o.keyframe_insert("rotation_euler", frame=start)
        o.location, o.rotation_euler = home_loc, home_rot
        o.keyframe_insert("location", frame=end)
        o.keyframe_insert("rotation_euler", frame=end)
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                if kp.co.x == start:
                    kp.interpolation, kp.easing = "BACK", "EASE_OUT"
                    kp.back = 1.2

    key(pivot, "rotation_euler", 1, (0, 0, math.radians(-70)), "EXPO", "EASE_OUT")
    key(pivot, "rotation_euler", 75, (0, 0, 0))


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.render.film_transparent = FONDO == "transparente"
    sc.render.resolution_x = sc.render.resolution_y = RESOLUTION
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    render_path = argv[argv.index("--render") + 1] if "--render" in argv else None
    save_path = argv[argv.index("--save") + 1] if "--save" in argv else None
    video_path = argv[argv.index("--video") + 1] if "--video" in argv else None
    global SAMPLES, RESOLUTION, FONDO
    if "--samples" in argv: SAMPLES = int(argv[argv.index("--samples") + 1])
    if "--res" in argv: RESOLUTION = int(argv[argv.index("--res") + 1])
    if "--fondo" in argv: FONDO = argv[argv.index("--fondo") + 1]

    reset_scene()
    letters = import_letters(os.path.join(script_dir(), "logo-fld.glb"))
    mat = make_material()
    for o in letters:
        o.data.materials.append(mat)

    make_world()
    cam, c = setup_camera(letters)
    lo, _, _ = bounds(letters)
    if FONDO == "blanco":
        make_cyclorama(c, lo.z - FLOTA)
    # Luces: key arriba-izquierda y contraluz violeta
    add_area("Key", c + Vector((-14, -6, 22)), c, (14, 6), 1100)
    add_area("Contra violeta", c + Vector((22, 10, 6)), c, (6, 16), 750, (0.72, 0.6, 1.0))
    # Softboxes: lo que el metal refleja (franjas de brillo en caras y biseles)
    add_softbox("Softbox cenital", c + Vector((0, 0, 30)), c, (40, 40), 1.0)
    add_softbox("Strip izquierda", c + Vector((-6, -30, 14)), c, (4, 40), 4.0)
    add_softbox("Strip derecha", c + Vector((30, 6, 14)), c, (4, 40), 2.6, (0.85, 0.8, 1.0))
    # Con cámara ortográfica cada cara plana refleja una sola dirección; se pone un panel justo ahí
    # para que las caras grandes se vean brillantes como metal pulido.
    # (El infinito blanco no aparece en reflejos, así que estos paneles se ven aunque queden bajo el piso.)
    k = 32 / math.sqrt(3)
    add_softbox("Reflejo cara D", c + Vector((-k, -k, -k)), c, (24, 24), 0.45)
    add_softbox("Reflejo cara L", c + Vector((k, k, -k)), c, (24, 24), 0.35, (0.9, 0.85, 1.0))
    add_softbox("Reflejo cara F", c + Vector((-k, k, k)), c, (24, 24), 0.55)
    setup_render()
    animate_entrance(letters, c)
    frame = int(argv[argv.index("--frame") + 1]) if "--frame" in argv else ANIM_FRAMES
    bpy.context.scene.frame_set(frame)  # por defecto el render fijo muestra la pose final

    frames_dir = argv[argv.index("--frames") + 1] if "--frames" in argv else None
    if frames_dir:
        # Solo los cuadros con movimiento (1..ANIM_MOTION_END); el resto es el logo quieto
        # y se completa repitiendo el último cuadro al armar el video.
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = 1, ANIM_MOTION_END
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.filepath = os.path.join(os.path.abspath(frames_dir), "cuadro_####")
        bpy.ops.render.render(animation=True)
        return

    if video_path:
        sc = bpy.context.scene
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
        sc.render.ffmpeg.ffmpeg_preset = "GOOD"
        sc.render.filepath = os.path.abspath(video_path)
        bpy.ops.render.render(animation=True)
        return

    if save_path:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save_path))
    if render_path:
        bpy.context.scene.render.filepath = os.path.abspath(render_path)
        bpy.ops.render.render(write_still=True)


main()
