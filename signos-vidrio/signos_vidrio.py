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
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ PARÁMETROS
# Cada signo: color intenso arriba que se desvanece a blanco lechoso abajo
COLOR_EXCLAMACION = ("#FF5AC0", "#FFC6E6")   # magenta → rosa casi blanco, translúcido
COLOR_PREGUNTA = ("#7A45FF", "#D3C6FF")      # violeta → lavanda casi blanca, translúcida

COLOR_FONDO = "#B4D2F2"   # celeste de la cinta de vidrio
COLOR_FONDO_LUZ = "#EAF2FC"

ESMERILADO = 0.55         # 0 = vidrio transparente, 0.6 = muy lechoso
ARENADO = 0.5             # cuánto se nota el granito del arenado en la superficie
DENSIDAD_COLOR = 3.6      # cuánto color toma el vidrio según su espesor (más = más intenso)
GROSOR = 0.36             # radio del punto (lo usa el material del punto)
FONT_PATH = "fuentes/Nunito-Black.ttf"  # Google Fonts, licencia OFL; al lado del script
ESPESOR = 0.42            # espesor total de la placa (los signos son planos, extruidos)
ANGULO_CAMARA = 28        # grados de costado desde el frente (0 = de frente)
SEPARACION_PUNTO = 0.18   # aire extra entre el cuerpo y el punto
REDONDEO = 0.16           # radio del redondeo de los cantos: casi una almohadita
ALTO = 3.0                # alto de los signos

RESOLUCION = (1080, 1080) # cuadrado, como la referencia
MUESTRAS = 192
# -----------------------------------------------------------------------------


def hex_a_lineal(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


def mezclar_hex(a, b, t):
    """Color entre a y b (t = 0 → a, t = 1 → b), en hex."""
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


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


# ---------- Geometría: signos planos extruidos, con cantos redondeados ----------
def buscar_fuente():
    """Ruta absoluta a FONT_PATH: tal cual, al lado del script o al lado del .blend."""
    candidatas = [FONT_PATH, bpy.path.abspath("//" + FONT_PATH)]
    if "__file__" in globals():
        candidatas.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), FONT_PATH))
    candidatas += [os.path.join(os.path.dirname(bpy.path.abspath(t.filepath)), FONT_PATH)
                   for t in bpy.data.texts if t.filepath]
    for ruta in candidatas:
        if ruta and os.path.isfile(ruta):
            return ruta
    print("No encontré la tipografía", FONT_PATH, "- uso la de Blender")
    return None


def signo_plano(caracter, nombre):
    """El signo como placa plana extruida, con cantos muy redondeados. De pie en el plano XZ,
    apoyado en z = 0 y con ALTO de alto. Devuelve [cuerpo, punto] (dos objetos)."""
    curva = bpy.data.curves.new(nombre, type="FONT")
    curva.body = caracter
    curva.size = 4.0
    curva.align_x = "CENTER"
    fuente = buscar_fuente()
    if fuente:
        curva.font = bpy.data.fonts.load(fuente, check_existing=True)
    curva.extrude = max(ESPESOR / 2 - REDONDEO, 0.0)
    curva.bevel_mode = "ROUND"
    curva.bevel_depth = REDONDEO
    curva.bevel_resolution = 10
    curva.offset = -REDONDEO * 0.6   # el redondeo casi no engorda el signo
    curva.resolution_u = 24
    ob = bpy.data.objects.new(nombre, curva)
    bpy.context.scene.collection.objects.link(ob)
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(curva)

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # de acostado (XY) a parado (XZ), mirando a -Y, apoyado en el piso y con el alto justo
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                     matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    zs = [v.co.z for v in bm.verts]
    k = ALTO / (max(zs) - min(zs))
    bmesh.ops.scale(bm, vec=(k, 1, k), verts=bm.verts)
    xs = [v.co.x for v in bm.verts]
    z0 = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-(min(xs) + max(xs)) / 2, 0, -z0)))

    # se separa el punto (la isla más baja) del cuerpo, para darle su propio color
    islas, vistos = [], set()
    for v in bm.verts:
        if v in vistos:
            continue
        pila, isla = [v], set()
        vistos.add(v)
        while pila:
            w = pila.pop()
            isla.add(w)
            for e in w.link_edges:
                o = e.other_vert(w)
                if o not in vistos:
                    vistos.add(o)
                    pila.append(o)
        islas.append(isla)
    punto = min(islas, key=lambda isla: max(v.co.z for v in isla))
    bm.verts.index_update()
    en_punto = {v.index for v in punto}
    objetos = []
    for parte, quedarse in (("cuerpo", False), ("punto", True)):
        b2 = bm.copy()
        b2.verts.ensure_lookup_table()
        bmesh.ops.delete(b2, geom=[f for f in b2.faces
                                   if (f.verts[0].index in en_punto) != quedarse],
                         context="FACES")
        m2 = bpy.data.meshes.new(f"{nombre} {parte}")
        b2.to_mesh(m2)
        b2.free()
        for p in m2.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(f"{nombre} {parte}", m2)
        bpy.context.scene.collection.objects.link(o)
        if parte == "cuerpo":  # más aire entre el cuerpo y el punto
            o.data.transform(Matrix.Translation((0, 0, SEPARACION_PUNTO)))
        objetos.append(o)
    bm.free()
    bpy.data.meshes.remove(me)
    return objetos


def exclamacion():
    return signo_plano("!", "Exclamacion")


def pregunta():
    return signo_plano("?", "Pregunta")


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
    # 2. el color vive adentro del vidrio (absorción): más intenso donde la pieza es gruesa,
    #    más claro en los bordes finos. La superficie queda en un tono pastel.
    pastel = nt.nodes.new("ShaderNodeMix")
    pastel.data_type = "RGBA"
    pastel.inputs["Factor"].default_value = 0.32
    nt.links.new(rampa.outputs["Color"], next(i for i in pastel.inputs if i.identifier == "A_Color"))
    next(i for i in pastel.inputs if i.identifier == "B_Color").default_value = (1, 1, 1, 1)
    nt.links.new(next(o for o in pastel.outputs if o.identifier == "Result_Color"),
                 bsdf.inputs["Base Color"])
    absorcion = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorcion.inputs["Density"].default_value = DENSIDAD_COLOR
    nt.links.new(rampa.outputs["Color"], absorcion.inputs["Color"])
    nt.links.new(absorcion.outputs["Volume"], nt.nodes.get("Material Output").inputs["Volume"])

    # el grano del esmerilado: la rugosidad varía apenas de punto a punto
    grano = nt.nodes.new("ShaderNodeTexNoise")
    grano.inputs["Scale"].default_value = 600.0
    rango = nt.nodes.new("ShaderNodeMapRange")
    rango.inputs["To Min"].default_value = ESMERILADO * 0.85
    rango.inputs["To Max"].default_value = ESMERILADO * 1.15
    nt.links.new(coord.outputs["Object"], grano.inputs["Vector"])
    nt.links.new(grano.outputs["Fac"], rango.inputs["Value"])
    # de frente menos esmerilado (se ve el color de atrás a través), en los bordes más lechoso
    costado = nt.nodes.new("ShaderNodeLayerWeight")
    costado.inputs["Blend"].default_value = 0.45
    segun_angulo = nt.nodes.new("ShaderNodeMapRange")
    segun_angulo.inputs["To Min"].default_value = 0.45  # de frente menos esmerilado: se ve a través
    segun_angulo.inputs["To Max"].default_value = 1.15
    nt.links.new(costado.outputs["Facing"], segun_angulo.inputs["Value"])
    rugosidad = nt.nodes.new("ShaderNodeMath")
    rugosidad.operation = "MULTIPLY"
    nt.links.new(rango.outputs["Result"], rugosidad.inputs[0])
    nt.links.new(segun_angulo.outputs["Result"], rugosidad.inputs[1])
    nt.links.new(rugosidad.outputs["Value"], bsdf.inputs["Roughness"])

    # el esmerilado que se ve: granito en relieve que agarra la luz, y un velo lechoso en los
    # bordes (donde se mira de costado), como el vidrio arenado
    arena = nt.nodes.new("ShaderNodeTexNoise")
    arena.inputs["Scale"].default_value = 190.0
    arena.inputs["Detail"].default_value = 6.0
    relieve = nt.nodes.new("ShaderNodeBump")
    relieve.inputs["Strength"].default_value = ARENADO
    relieve.inputs["Distance"].default_value = 0.004
    nt.links.new(coord.outputs["Object"], arena.inputs["Vector"])
    nt.links.new(arena.outputs["Fac"], relieve.inputs["Height"])
    nt.links.new(relieve.outputs["Normal"], bsdf.inputs["Normal"])
    # 3. un reflejo nítido y muy sutil sólo en los bordes, como el vidrio arenado real
    if coat:
        borde = nt.nodes.new("ShaderNodeLayerWeight")
        borde.inputs["Blend"].default_value = 0.25
        peso = nt.nodes.new("ShaderNodeMapRange")
        peso.inputs["To Min"].default_value, peso.inputs["To Max"].default_value = 0.0, 0.15
        nt.links.new(borde.outputs["Fresnel"], peso.inputs["Value"])
        nt.links.new(peso.outputs["Result"], coat)
    if coat_r:
        coat_r.default_value = 0.06
    sheen = entrada(bsdf, "Sheen Weight", "Sheen")
    if sheen:
        sheen.default_value = 0.6
    sheen_r = entrada(bsdf, "Sheen Roughness")
    if sheen_r:
        sheen_r.default_value = 0.35
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
    # el vidrio no "ve" el piso al refractar: sin manchas blancas en la base de cada pieza
    ob.visible_transmission = False
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
    # el "!" adelante y un poco más chico, cruzado delante del gancho del "?" (no del tallo):
    # así se ve el violeta a través del rosa y los dos pesan parejo
    for armar, colores, pos, giro, escala in (
        (pregunta, COLOR_PREGUNTA, (-0.95, 0.55, 0), -6, 0.84),
        (exclamacion, COLOR_EXCLAMACION, (0.75, -0.45, 0), 22, 0.8),
    ):
        grupo = bpy.data.objects.new(armar.__name__.capitalize(), None)
        escena.collection.objects.link(grupo)
        mat = material_esmerilado("Vidrio " + armar.__name__, colores[0], colores[1], 0.0, ALTO)
        # el punto lleva su propio degradé corto, con el color del signo: no queda gris
        medio = mezclar_hex(colores[0], colores[1], 0.45)
        mat_punto = material_esmerilado("Vidrio punto " + armar.__name__, medio, colores[1],
                                        0.0, 2 * GROSOR)
        for ob in armar():
            ob.data.materials.append(mat_punto if "punto" in ob.name else mat)
            ob.parent = grupo
            piezas.append(ob)
        grupo.location = pos
        grupo.rotation_euler = (0, 0, math.radians(giro))
        grupo.scale = (escala, escala, escala)
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
    # toma principal a 28° de costado: el "!" se cruza delante del "?"
    a = math.radians(ANGULO_CAMARA)
    cam.location = centro + Vector((math.sin(a), -math.cos(a), 0.06)).normalized() * 12.0
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
    luz("Softbox", 300, (-4, -6, 6), 5, 5)  # adelante: la luz cae pareja, sin bordes en la pared
    # contraluz enorme y suave, a la altura de los signos: enciende el vidrio desde adentro
    # sin concentrarse en puntos (una chica o inclinada quemaba las puntas de abajo)
    luz("Contraluz", 35, (0.2, 4.2, 2.0), 10, 7, (1.0, 0.95, 0.99),
        mira=(0, -3, 1.6), abertura=60, en_reflejos=False)
    # la pared del fondo bañada desde arriba: el celeste se aclara hacia arriba
    luz("Pared", 380, (0, 2.5, 11), 18, 10, mira=(0, 7, 3.0))  # amplia: aclara arriba sin bordes
    luz("Relleno", 70, (6, -5, 3), 4, 4, (0.92, 0.95, 1.0))

    configurar_mundo()
    configurar_render()


main()
