# HOLA de vidrio: traspaso para el sistema de render (render_ana)

Nota para la sesión de Claude que maneja `render_ana` en la compu de Ana.
Está pensada para sumar esta animación como tramos nuevos para Juani y Uge.

## Archivos (rama `ccr-84dc791d-bu8bbp` del repo `cuenta-regresiva-invitaciones`)

| Archivo | Para qué |
|---|---|
| `blender/hola_vidrio.py` | **Único archivo necesario.** Arma toda la escena (letras, vidrio, luces, cámara) y la animación. No usa fuentes, texturas ni archivos externos. |
| `blender/hola_vidrio.blend` | Escena fija ya armada, solo para mirar o abrir en Blender. Para renderizar conviene usar el script. |
| `blender/hola_vidrio*.png` | Renders fijos de referencia. |

Está probado en Blender 4.2.23 y 5.0.1 en modo background. Los nodos usan 5.2.1. La única diferencia entre versiones (cómo se guardan las curvas de animación) ya está resuelta en `iter_fcurves`.

## Animación

- 300 cuadros a 24 fps (12,5 s), 1080×1080 por defecto. Fondo rosa empolvado.
- Las letras son de vidrio pesado y caen del cielo con un ritmo irregular (H… O.L… A). La A cae desde más alto, como remate.
  - Mientras caen giran un poco y se enderezan justo al tocar el piso. Rebotan poco, se aplastan apenas y le dan un empujoncito a la letra anterior.
  - En cada impacto saltan gotitas de vidrio.
- Mientras caen, la cámara da medio giro alrededor de la palabra, de atrás hacia el frente. Acompaña a la letra que cae y se acerca al final del giro. Tiembla apenas cuando cae la A.
- Del cuadro 116 al 164, las letras se transforman de vidrio rosa a cristal tornasolado, subiendo desde el piso. La cámara no frena: pasa por el frente y sigue girando.
- Desde el 160, cierre: la cámara se acerca, baja y recorre el cristal de cerca. Termina a unos 40° del frente, en el cuadro 300.
- Lleva desenfoque de movimiento y estudio redondo, para que no se vean bordes durante el giro.
- Parámetros arriba de todo en el script: `SUELTA`, `ALTURA_CAIDA`, `GIRO_CAIDA`, `REBOTE`, `APLASTE`, `EMPUJON`, `GOTITAS`, `CAMARA_*`, `TRANSFORMA_DESDE/HASTA`, `CIERRE_*`, `DESENFOQUE_MOVIMIENTO`, `CRISTAL_*`.

## Comando

```
blender -b -P hola_vidrio.py -- --animar --gpu --frames 1 150 --render-anim cuadros/
```

- `--gpu` elige OptiX en las RTX y, si no hay, CUDA, HIP, Metal o oneAPI. Si no encuentra placa, usa CPU.
- `--render-anim carpeta/` guarda `hola_0001.png …`. Usa *placeholders* y no sobrescribe, así que si se corta se puede relanzar y sigue donde quedó.
- `--frames A B` define el tramo de cuadros. Por defecto renderiza 1–300.
- Otras opciones:
  - `--muestras N`: muestras de render, por defecto 256.
  - `--res W H`: resolución.
  - `--mp4 salida.mp4`: video directo en lugar de PNG.
  - `--save x.blend`: guarda la escena.
- Para formato vertical de historia: `--res 1080 1920`. Puede hacer falta acercar la cámara, porque hoy está encuadrada para cuadrado.

## Tramos sugeridos

| Tramo | Quién | Cuadros |
|---|---|---|
| `hola_a` | Juani (RTX 3080) | 1–170 |
| `hola_b` | Uge | 171–300 |

Si solo renderiza uno, `hola_completo` con 1–300. Los cuadros del cristal (desde el 116) tardan alrededor de 40 % más que los del rosa. Los primeros cuadros (1–~20) son más rápidos porque todavía no hay letras en cuadro.

**Tiempos de referencia:** en la nube, con CPU de 4 núcleos, un cuadro a 1080×1080 y 256 muestras tarda unos 7–9 minutos. En una RTX 3080 con OptiX debería tardar alrededor de 30–60 s por cuadro, unos 3,5–5,5 h por los 300 cuadros. Si hace falta acelerar, `--muestras 128` se ve casi igual con el denoiser.

## Unir el resultado

Con los PNG de todos los tramos en una misma carpeta:

```
ffmpeg -framerate 24 -i hola_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 16 hola_vidrio.mp4
```

Si cada nodo sube su tramo en MP4:

```
ffmpeg -f concat -safe 0 -i lista.txt -c copy hola_vidrio.mp4
```

donde `lista.txt` tiene `file 'hola_a.mp4'` y `file 'hola_b.mp4'`, una por línea.

## Pendiente o a decidir con Ana

- Formato final: cuadrado (actual) o vertical para historia.
