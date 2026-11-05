# Ficha técnica — Teclas QWE / ASD

Todo lo necesario para rehacer este look en otra escena o en otro chat. Las medidas están en
unidades de Blender, donde **1 tecla = 1 unidad de ancho (≈ 18 mm reales)**, así que
**1 mm ≈ 0.0556**. Motor: **Blender 4.2 + Cycles**. El script completo está en `teclas/teclas.py`.

---

## 1. Forma de la tecla

- Perfil bajo tipo OEM / Cherry: paredes en talud, un borde redondeado arriba, y un plato
  apenas hundido con un escalón suave.
- Base de **1 × 1**, alto **0.5**; las esquinas se redondean con un radio que crece de abajo
  (0.07) hacia arriba (0.13). Al final se aplica un **Subdivision Surface nivel 2**.
- **Hueca, como las teclas reales:** paredes de **1.4 mm** y techo de **1.7 mm**.
- **Encastre MX adentro** (se ve en la transparente): un barril de **5.6 mm** de diámetro con
  el agujero en cruz de **4.1 × 1.2 mm**, que cuelga del techo y termina **0.6 mm** por arriba
  del borde de abajo.
- Separación entre teclas: **0.05**.
- Letras: **JetBrains Mono Medium** (Google Fonts, OFL), de alto **0.46**, en mayúsculas, apenas
  extruidas (0.002) y apoyadas sobre el plato.

## 2. Materiales (Principled BSDF)

| Material | Color | Rugosidad | Lo especial |
|---|---|---|---|
| **PBT blanco** (W E S D) | `#E9E7E2` blanco hueso | 0.42 | Subsurface 0.15, radio 0.05. Granito: Noise escala 520 → Bump fuerza 0.16, distancia 0.002 |
| **PBT azul** (Q) | `#2D5BE3` | 0.42 | Igual que el blanco: mate, no brillante |
| **Azul transparente** (A) | superficie `#B5C8FF`, volumen `#2D5BE3` | 0.18 | Transmission 1.0, IOR 1.49 (acrílico). Volume Absorption con el azul y densidad 0.18 en la salida *Volume* |
| **Letra oscura** | `#1B1B1D` | 0.55 | — |
| **Letra clara** (sobre azul) | `#FFFFFF` | 0.55 | — |
| **Pared** | `#CFCFCF` | 0.95 | Gris mate |

**La clave del plástico transparente:** la tecla es hueca, la superficie tiene un azul claro y
el color fuerte lo da la absorción en volumen. Así se ve más azul donde el plástico es grueso
(los cantos) y más claro en las paredes finas. Una rugosidad baja (0.18) deja los reflejos
nítidos pero apenas difusos.

## 3. Escena y cámara

- Las seis teclas se arman acostadas y se paran todas juntas: el grupo se rota **90° en X**,
  así las letras miran a la cámara. La fila Q W E queda arriba.
- **Pared** de fondo lisa, a **2.6** detrás de las teclas, lo bastante cerca para recibir sus
  sombras.
- **Cámara:** lente **125 mm**, a **15** de distancia, girada **24°** hacia la derecha y un
  poco desde arriba. Con un desplazamiento del encuadre (*shift*) de **−0.05 / 0.045** el
  bloque queda centrado.
- Cuadro **1080 × 1080**.

## 4. Iluminación

Todas las luces son de área (*Area*), salvo la ventana, que es un *Sun*. Ninguna se ve en cámara.

| Luz | Energía | Tamaño | Posición → hacia dónde | Para qué |
|---|---|---|---|---|
| **Softbox** principal | 520 W | 2.5 | (−5, −6, 5) → teclas | Luz desde adelante arriba a la izquierda; sombras marcadas hacia abajo a la derecha, que caen en la pared |
| **Relleno** | 120 W | 6 | (6, −6, 0) → teclas | Abre las sombras; color levemente frío (0.96, 0.97, 1.0) |
| **Luz pared** | 70 W | 6, apertura 120° | (−2, 0.5, 3.5) → pared | Un degradé suave en la pared, más claro arriba a la izquierda |
| **Contraluz** | 60 W | 3 | (−2.5, 3, 0.5) → tecla A | Enciende la tecla transparente desde atrás. Con *light linking* **sólo ilumina esa tecla**, para no lavar la pared |
| **Ventana** (Sun) | 1.6 | ángulo 2.5° | dirección (0.55, 1, −0.45) | Luz cálida (1.0, 0.97, 0.92) que pasa por una persiana. Con *light linking* **sólo pega en la pared** |
| **Mundo** | 0.45 | — | blanco | Relleno ambiente |

**Sombras de persiana:** 42 listones de 14 × 0.05 × 0.22, separados 0.55 e inclinados −28°,
ubicados entre la luz de ventana y la pared. Tienen apagada toda la visibilidad excepto la de
sombra (*Ray Visibility*: sólo *Shadow*), así que no se ven en cámara: sólo aparecen sus
sombras rayadas sobre la pared.

## 5. Animación (loop de 6 s a 30 fps)

- Cada tecla está dentro de un "pulsador" (un Empty) que se mueve en su eje local Z, hacia la
  cámara o hacia la pared.
- **Salto inicial:** las teclas saltan **0.55** hacia adelante una tras otra, en el orden
  Q W E A S D, con 0.11 s entre cada una. Cada salto dura 0.55 s, con una leve inclinación
  (0.18 rad) y un rebotecito al aterrizar.
- **Pulsación:** baja **0.22** (≈ 4 mm, como una tecla real). Dura 0.32 s: baja rápido (18 %
  del tiempo), queda abajo (20 %) y vuelve con un rebote amortiguado.
- **Ritmo** (en segundos):
  1.45 W · 1.62 A · 1.74 S · 1.86 D · 2.35 Q+E · 2.80 W · 2.94 W · 3.40 A+D ·
  3.70 S · 3.82 E · 3.94 Q · 4.45 W · 4.55 A · 4.65 S · 4.75 D · 5.20 todas juntas
- Todo vuelve al reposo al final, así el loop empalma perfecto.

## 6. Render

- Cycles, **192 muestras**, con denoise y muestreo adaptativo.
- Rebotes: máximo **16**, transmisión **12**.
- Transformación de color **Standard** (sin AgX ni Filmic), para que el gris y el azul
  queden fieles.

---

## Prompt para otro chat

> Quiero rehacer en Blender (Cycles) un material de **plástico de tecla mecánica**, en dos
> versiones:
> 1. **PBT mate:** Principled BSDF con rugosidad 0.42, subsurface 0.15 (radio 0.05) y un granito
>    fino (Noise escala 520 conectado a un Bump de fuerza 0.16 y distancia 0.002). Blanco hueso
>    `#E9E7E2` o azul `#2D5BE3`.
> 2. **Plástico azul medio transparente:** el objeto tiene que ser **hueco**, con paredes de unos
>    1.4 mm. Principled con superficie `#B5C8FF`, transmisión 1.0, IOR 1.49 y rugosidad 0.18,
>    más un Volume Absorption azul `#2D5BE3` de densidad 0.18 en la salida Volume. Adentro se
>    ve el encastre Cherry MX: un barril de 5.6 mm con una cruz de 4.1 × 1.2 mm.
>
> Iluminación de estudio: un softbox chico arriba a la izquierda y adelante (sombras marcadas),
> un relleno frío a la derecha, y una contraluz atrás que con *light linking* sólo ilumine la
> pieza transparente. Fondo: pared gris `#CFCFCF` cerca de los objetos para que reciba sus
> sombras, con un degradé de luz suave y sombras de persiana en diagonal hechas con listones
> que sólo proyectan sombra, bajo una luz Sun cálida que con *light linking* sólo pegue en la
> pared. Transformación de color Standard.
