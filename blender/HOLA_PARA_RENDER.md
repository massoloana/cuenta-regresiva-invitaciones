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

- 144 cuadros a 24 fps (6 s), 1080×1080 por defecto.
- Las letras H, O, L y A caen del cielo una tras otra, cada una 14 cuadros después de la anterior, empezando en el cuadro 10. Rebotan, se aplastan al tocar el piso y se asientan con un leve bamboleo.
- Mientras caen, la cámara da medio giro alrededor de la palabra. Empieza detrás, con las letras al revés, y termina de frente en el cuadro 112. Del 112 al 144 queda quieta.
- El estudio es redondo (piso y pared curva alrededor) para que no se vean bordes durante el giro.
- Los parámetros están arriba de todo en el script: `CUADROS`, `CAIDA_INICIO`, `CAIDA_DESFASAJE`, `ALTURA_CAIDA`, `REBOTE`, `APLASTE`, `CAMARA_DESDE/HASTA`, `CAMARA_FIN`, `CAMARA_DISTANCIA/ALTURA`.

## Comando

```
blender -b -P hola_vidrio.py -- --animar --gpu --frames 1 72 --render-anim cuadros/
```

- `--gpu` elige OptiX en las RTX y, si no hay, CUDA, HIP, Metal o oneAPI. Si no encuentra placa, usa CPU.
- `--render-anim carpeta/` guarda `hola_0001.png …`. Usa *placeholders* y no sobrescribe, así que si se corta se puede relanzar y sigue donde quedó.
- `--frames A B` define el tramo de cuadros. Por defecto renderiza 1–144.
- Otras opciones:
  - `--muestras N`: muestras de render, por defecto 256.
  - `--res W H`: resolución.
  - `--mp4 salida.mp4`: video directo en lugar de PNG.
  - `--save x.blend`: guarda la escena.
- Para formato vertical de historia: `--res 1080 1920`. Puede hacer falta acercar la cámara, porque hoy está encuadrada para cuadrado.

## Tramos sugeridos

| Tramo | Quién | Cuadros |
|---|---|---|
| `hola_a` | Juani (RTX 3080) | 1–84 |
| `hola_b` | Uge | 85–144 |

Si solo renderiza uno, `hola_completo` con 1–144. Los primeros cuadros (1–~20) son más rápidos porque todavía no hay letras en cuadro.

**Tiempos de referencia:** en la nube, con CPU de 4 núcleos, un cuadro a 1080×1080 y 256 muestras tarda unos 7–9 minutos. En una RTX 3080 con OptiX debería tardar alrededor de 30–60 s por cuadro, unos 1,5–2,5 h por los 144 cuadros. Si hace falta acelerar, `--muestras 128` se ve casi igual con el denoiser.

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
- Si quiere un final más largo con la palabra quieta, se sube `CUADROS`.
