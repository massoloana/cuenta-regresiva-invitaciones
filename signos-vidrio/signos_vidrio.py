"""
Signos de vidrio — escena para Blender (3.6 o 4.x).

Un "!" y un "?" de vidrio esmerilado grueso, con el color que se desvanece a blanco lechoso
de una punta a la otra, apoyados sobre un piso celeste que los refleja, vistos a 45 grados.
Paleta y fondo de la cinta de vidrio de Tregua.

Cómo usarlo:
  1. Abrí Blender, andá a la pestaña "Scripting".
  2. Text > Open… y elegí este archivo.
  3. Apretá "Run Script". Borra la escena actual y arma todo de cero.
  4. F12 para la imagen (Render > Render Image).

Todo lo ajustable está en PARÁMETROS.
"""

import math

import bmesh
import bpy
from mathutils import Vector

# ------------------------------------------------------------------ PARÁMETROS
# Cada signo: color intenso arriba que se desvanece a blanco lechoso abajo
COLOR_EXCLAMACION = ("#F0409F", "#FFDDF0")   # magenta → rosa casi blanco, translúcido
COLOR_PREGUNTA = ("#7A45FF", "#E4DCFF")      # violeta → lavanda casi blanca, translúcida

COLOR_FONDO = "#B4D2F2"   # celeste de la cinta de vidrio
COLOR_FONDO_LUZ = "#EAF2FC"

ESMERILADO = 0.5          # 0 = vidrio transparente, 0.6 = muy lechoso
GROSOR = 0.36             # radio del trazo de los signos
ALTO = 3.0                # alto de los signos

RESOLUCION = (1080, 1080) # cuadrado, como la referencia
MUESTRAS = 192
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


# ---------- Geometría: un tubo con puntas redondas, de una sola pieza ----------
def tubo(nombre, camino, radio, segmentos=48, anillos_punta=14):
    """Barre un círculo a lo largo de `camino` (lista de Vector) y cierra las dos puntas con
    media esfera. `radio(t)` da el radio en cada punto (t de 0 a 1). Devuelve un objeto
    cerrado y sin piezas superpuestas (el vidrio no muestra costuras por dentro)."""
    n = len(camino)
    tangentes = []
    for i in range(n):
        a, b = camino[max(i - 1, 0)], camino[min(i + 1, n - 1)]
        tangentes.append((b - a).normalized())
    # marcos por transporte paralelo: el tubo no se retuerce
    t0 = tangentes[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    u = t0.cross(ref).normalized()
    marcos = []
    for i in range(n):
        t = tangentes[i]
        u = (u - t * u.dot(t)).normalized()
        marcos.append((u, t.cross(u).normalized()))

    bm = bmesh.new()
    anillos = []

    def anillo(centro, u, v, r):
        return [bm.verts.new(centro + (u * math.cos(2 * math.pi * k / segmentos) +
                                       v * math.sin(2 * math.pi * k / segmentos)) * r)
                for k in range(segmentos)]

    # punta inicial (media esfera hacia atrás)
    r0 = radio(0.0)
    u0, v0 = marcos[0]
    polo_ini = bm.verts.new(camino[0] - tangentes[0] * r0)
    for k in range(1, anillos_punta):
        fi = math.pi / 2 * k / anillos_punta
        anillos.append(anillo(camino[0] - tangentes[0] * r0 * math.cos(fi), u0, v0, r0 * math.sin(fi)))
    for i in range(n):
        u, v = marcos[i]
        anillos.append(anillo(camino[i], u, v, radio(i / (n - 1))))
    r1 = radio(1.0)
    u1, v1 = marcos[-1]
    for k in range(anillos_punta - 1, 0, -1):
        fi = math.pi / 2 * k / anillos_punta
        anillos.append(anillo(camino[-1] + tangentes[-1] * r1 * math.cos(fi), u1, v1, r1 * math.sin(fi)))
    polo_fin = bm.verts.new(camino[-1] + tangentes[-1] * r1)

    for a, b in zip(anillos, anillos[1:]):
        for k in range(segmentos):
            bm.faces.new((a[k], a[(k + 1) % segmentos], b[(k + 1) % segmentos], b[k]))
    for k in range(segmentos):
        bm.faces.new((polo_ini, anillos[0][(k + 1) % segmentos], anillos[0][k]))
        bm.faces.new((polo_fin, anillos[-1][k], anillos[-1][(k + 1) % segmentos]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def esfera(nombre, centro, radio):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=radio)
    # la malla ya queda en su lugar (origen en el piso): el degradé mide la altura real
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(centro))
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def exclamacion():
    """Palo que se afina hacia abajo + punto. En el plano XZ, apoyado en z = 0."""
    r = GROSOR
    punto = esfera("Exclamacion punto", (0, 0, r), r)
    abajo, arriba = 2 * r + 0.45 + r * 0.8, ALTO - r * 1.15
    camino = [Vector((0, 0, arriba + (abajo - arriba) * i / 60)) for i in range(61)]
    suave = lambda t: t * t * (3 - 2 * t)  # sin pendiente en las puntas: no marca un aro
    palo = tubo("Exclamacion palo", camino, lambda t: r * (1.15 - 0.35 * suave(t)))
    return [palo, punto]


def curva_suave(puntos, por_tramo=24):
    """Catmull-Rom por los puntos dados: un trazo continuo, sin quiebres."""
    p = [Vector(x) for x in puntos]
    p = [p[0] * 2 - p[1]] + p + [p[-1] * 2 - p[-2]]
    salida = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(por_tramo):
            t = k / por_tramo
            salida.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                                 (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    salida.append(p[-2])
    return salida


def pregunta():
    """Gancho que baja a un tallo corto + punto. En el plano XZ, apoyado en z = 0."""
    r = GROSOR
    punto = esfera("Pregunta punto", (0, 0, r), r)
    e = ALTO / 3.0  # escala del dibujo (hecho para 3 de alto)
    dibujo = [(-0.64, 2.18), (-0.56, 2.56), (-0.24, 2.80), (0.18, 2.80), (0.56, 2.58),
              (0.66, 2.20), (0.48, 1.88), (0.16, 1.66), (0.03, 1.46), (0.02, 1.28)]
    camino = [Vector((x * e, 0, z * e)) for x, _, z in
              ((v.x, 0, v.y) for v in curva_suave(dibujo))]
    gancho = tubo("Pregunta gancho", camino,
                  lambda t: r * (1.05 - 0.15 * t * t * (3 - 2 * t)))
    return [gancho, punto]


# ---------- Material: vidrio esmerilado grueso con degradé vertical ----------
def material_esmerilado(nombre, color_arriba, color_abajo, z_min, z_max):
    mat = bpy.data.materials.new(nombre)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    entrada(bsdf, "Transmission Weight", "Transmission").default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.45
    bsdf.inputs["Roughness"].default_value = ESMERILADO
    coat = entrada(bsdf, "Coat Weight", "Clearcoat")
    if coat:  # una capa de brillo muy suave encima, como el vidrio arenado y luego pulido
        coat.default_value = 0.0  # sin laca: mate y suave, como el vidrio arenado
    coat_r = entrada(bsdf, "Coat Roughness", "Clearcoat Roughness")
    if coat_r:
        coat_r.default_value = 0.2

    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    alto = nt.nodes.new("ShaderNodeMapRange")
    alto.inputs["From Min"].default_value = z_min
    alto.inputs["From Max"].default_value = z_max
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    els = rampa.color_ramp.elements
    # degradé marcado: la mitad de abajo se desvanece casi a blanco translúcido
    els[0].position, els[0].color = 0.12, hex_a_lineal(color_abajo)
    els[1].position, els[1].color = 0.85, hex_a_lineal(color_arriba)
    rampa.color_ramp.interpolation = "EASE"
    nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], alto.inputs["Value"])
    nt.links.new(alto.outputs["Result"], rampa.inputs["Fac"])
    nt.links.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])

    # el grano del esmerilado: la rugosidad varía apenas de punto a punto
    grano = nt.nodes.new("ShaderNodeTexNoise")
    grano.inputs["Scale"].default_value = 600.0
    rango = nt.nodes.new("ShaderNodeMapRange")
    rango.inputs["To Min"].default_value = ESMERILADO * 0.85
    rango.inputs["To Max"].default_value = ESMERILADO * 1.15
    nt.links.new(coord.outputs["Object"], grano.inputs["Vector"])
    nt.links.new(grano.outputs["Fac"], rango.inputs["Value"])
    nt.links.new(rango.outputs["Result"], bsdf.inputs["Roughness"])
    mat.diffuse_color = hex_a_lineal(color_arriba)
    return mat


# ---------- Estudio: piso celeste que refleja y sube en curva hasta la pared ----------
def crear_estudio():
    piso_z, pared_y, radio, ancho = 0.0, 7.0, 4.0, 60.0
    perfil = [(y, piso_z) for y in (-20.0, -5.0, pared_y - radio)]
    for i in range(1, 32):
        a = i / 32 * math.pi / 2
        perfil.append((pared_y - radio + radio * math.sin(a), piso_z + radio - radio * math.cos(a)))
    perfil += [(pared_y, piso_z + radio + h) for h in (0.0, 20.0)]
    bm = bmesh.new()
    filas = [[bm.verts.new((x, y, z)) for x in (-ancho / 2, 0.0, ancho / 2)] for y, z in perfil]
    for a, b in zip(filas, filas[1:]):
        for j in range(2):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.z < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Estudio")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Estudio", me)
    bpy.context.scene.collection.objects.link(ob)

    mat = bpy.data.materials.new("Piso celeste")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_a_lineal(COLOR_FONDO)
    bsdf.inputs["Roughness"].default_value = 0.6
    # una capa brillante encima: el piso refleja los signos, suave, como en la referencia
    coat = entrada(bsdf, "Coat Weight", "Clearcoat")
    if coat:
        coat.default_value = 0.6
    coat_r = entrada(bsdf, "Coat Roughness", "Clearcoat Roughness")
    if coat_r:
        coat_r.default_value = 0.12
    me.materials.append(mat)
    return ob


def configurar_mundo():
    mundo = bpy.data.worlds.get("Estudio") or bpy.data.worlds.new("Estudio")
    bpy.context.scene.world = mundo
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes.get("Background")
    fondo.inputs["Color"].default_value = hex_a_lineal(COLOR_FONDO_LUZ)
    fondo.inputs["Strength"].default_value = 0.45


def configurar_render():
    escena = bpy.context.scene
    escena.render.resolution_x, escena.render.resolution_y = RESOLUCION
    escena.render.engine = "CYCLES"
    escena.cycles.samples = MUESTRAS
    escena.cycles.use_denoising = True
    escena.cycles.use_adaptive_sampling = True
    escena.cycles.max_bounces = 24
    escena.cycles.transmission_bounces = 20
    escena.cycles.glossy_bounces = 8
    escena.cycles.caustics_reflective = False
    escena.cycles.caustics_refractive = False
    escena.view_settings.view_transform = "Standard"
    escena.view_settings.look = "None"
    escena.render.image_settings.file_format = "PNG"
    escena.render.filepath = "//signos_vidrio"


def main():
    limpiar_escena()
    escena = bpy.context.scene

    # signos: el "?" atrás a la izquierda, el "!" adelante a la derecha, apenas encimados
    piezas = []
    for armar, colores, pos, giro in (
        (pregunta, COLOR_PREGUNTA, (-0.55, 0.75, 0), -16),
        (exclamacion, COLOR_EXCLAMACION, (0.5, -0.35, 0), 12),
    ):
        grupo = bpy.data.objects.new(armar.__name__.capitalize(), None)
        escena.collection.objects.link(grupo)
        mat = material_esmerilado("Vidrio " + armar.__name__, colores[0], colores[1], 0.0, ALTO)
        for ob in armar():
            ob.data.materials.append(mat)
            ob.parent = grupo
            piezas.append(ob)
        grupo.location = pos
        grupo.rotation_euler = (0, 0, math.radians(giro))
    crear_estudio()

    # Cámara a 45 grados, lente normal
    cam_data = bpy.data.cameras.new("Camara")
    cam_data.lens = 95
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 12.0
    cam_data.dof.aperture_fstop = 4.0
    cam = bpy.data.objects.new("Camara", cam_data)
    escena.collection.objects.link(cam)
    # a la altura de los signos, mirando de frente (apenas por encima del centro)
    centro = Vector((0, 0, 1.45))
    cam.location = centro + Vector((0, -1, 0.06)).normalized() * 12.0
    cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = cam

    def luz(nombre, energia, pos, tam_x, tam_y, color=(1, 1, 1), mira=None, abertura=180,
            en_reflejos=True):
        datos = bpy.data.lights.new(nombre, "AREA")
        datos.energy = energia
        datos.color = color
        datos.shape = "RECTANGLE"
        datos.size, datos.size_y = tam_x, tam_y
        ob = bpy.data.objects.new(nombre, datos)
        escena.collection.objects.link(ob)
        datos.spread = math.radians(abertura)  # menos abertura = un haz más dirigido
        ob.visible_camera = False  # la cámara ve su efecto, no el panel de luz
        ob.visible_glossy = en_reflejos
        ob.location = pos
        destino = Vector(mira) if mira else centro
        ob.rotation_euler = (destino - Vector(pos)).to_track_quat("-Z", "Y").to_euler()

    # softbox grande arriba a la izquierda, contraluz que enciende el vidrio desde atrás
    luz("Softbox", 300, (-5, -3, 7), 6, 6)
    # contraluz baja, entre los signos y la pared: la luz atraviesa el vidrio y lo enciende
    # desde adentro (emite sólo hacia adelante, así no mancha la pared)
    luz("Contraluz", 110, (0.3, 3.8, 3.2), 7, 4, (1.0, 0.96, 0.98),
        mira=(0, -3, 0.8), abertura=40,   # grande: brillo interno suave, sin puntos quemados
        en_reflejos=False)                # el piso no refleja el panel, sólo los signos
    # la pared del fondo bañada desde arriba: el celeste se aclara hacia arriba
    luz("Pared", 220, (0, 2.5, 10), 14, 8, mira=(0, 7, 2.0))
    luz("Relleno", 70, (6, -5, 3), 4, 4, (0.92, 0.95, 1.0))

    configurar_mundo()
    configurar_render()


main()
