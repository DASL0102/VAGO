# Guía de Uso e Instrucciones del Módulo de Visión (VAGO)

**Proyecto:** Visual Actions to Geometric Output (VAGO)  
**Módulo:** Detector de Gestos y Generador de Tokens en Tiempo Real  
**Archivo Principal:** `vision_detector.py`  
**Tecnologías:** Python 3.10+, OpenCV, MediaPipe Hands, NumPy  

---

## 1. Descripción General

El módulo de visión por computadora de **VAGO** procesa el flujo de video en vivo capturado desde una cámara web (o archivo de video), reconoce posturas y movimientos dinámicos de las manos inspirados en la notación **HamNoSys**, y emite una secuencia continua de tokens delimitados entre corchetes (ej. `[ID_QUAD_1]`, `[ZIG_ZAG_MOTION]`, `[NUM_45]`, `[DELIM_END]`) directamente a la salida estándar (`sys.stdout`) con vaciado inmediato (`flush=True`).

Esta salida está optimizada para ser consumida mediante tuberías (pipes) o redirección por el compilador e intérprete geométrico en C++.

---

## 2. Requisitos Previos e Instalación

### 2.1. Activar el Entorno Virtual
Desde la raíz del proyecto `/home/dazai/VAGO`:

```bash
source venv/bin/activate
```

### 2.2. Dependencias (`requirements.txt`)
Las dependencias requeridas son:
```text
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
```

Para instalarlas o actualizarlas en el entorno:
```bash
pip install -r requirements.txt
```

> **Nota sobre MediaPipe:** El script incorpora la clase `HandTracker`, compatible tanto con la **MediaPipe Tasks API** (`HandLandmarker`) como con la API heredada (`mp.solutions.hands`). Si el archivo de modelo `hand_landmarker.task` no está presente, se descargará automáticamente desde el repositorio oficial de Google.

---

## 3. Ejecución del Detector

### 3.1. Modo Estándar con Cámara Web
Inicia la detección interactiva con la cámara predeterminada:
```bash
python vision_detector.py
```
O de forma directa como ejecutable:
```bash
./vision_detector.py
```

### 3.2. Parámetros de Línea de Comandos
El script soporta múltiples opciones configurables:

| Parámetro | Tipo | Por Defecto | Descripción |
| :--- | :---: | :---: | :--- |
| `--camera` | `int` | `0` | Índice del dispositivo de video (ej. `0`, `1`). |
| `--video` | `str` | `None` | Ruta a un video pregrabado para procesamiento fuera de línea. |
| `--width` | `int` | `1280` | Ancho de resolución para la captura. |
| `--height` | `int` | `720` | Alto de resolución para la captura. |
| `--debounce` | `int` | `6` | Fotogramas mínimos consecutivos para confirmar un gesto (antirrebote). |
| `--mirror` | `flag` | `True` | Invierte el feed horizontalmente (comportamiento natural de espejo). |
| `--no-mirror` | `flag` | — | Desactiva el modo espejo. |
| `--headless` | `flag` | `False` | Ejecuta sin abrir interfaz gráfica OpenCV (servidores/CI/pipes). |

#### Ejemplos de Ejecución Avanzada:
```bash
# Ejecutar en segundo plano consumiendo datos en una tubería hacia el compilador en C++:
python vision_detector.py --headless | ./vago_compiler

# Procesar un archivo de video con resolución específica:
python vision_detector.py --video grabacion_gestos.mp4 --width 1920 --height 1080

# Incrementar la estabilidad del antirrebote a 8 frames:
python vision_detector.py --debounce 8
```

---

## 4. Controles y Atajos en la Ventana Interactiva

Al ejecutar en modo gráfico, la ventana de OpenCV responde a los siguientes comandos de teclado:

* **`Q` o `ESC`:** Finalizar la ejecución y liberar la cámara limpiamente.
* **`C`:** Limpiar la línea de instrucción actual y vaciar el buffer numérico.
* **`M`:** Alternar el modo espejo (*mirroring*) entre activado y desactivado.

---

## 5. Arquitectura del Sistema de Visión

### 5.1. Separación Bimanual
* **Mano No Dominante (Izquierda):**
  * Reservada **exclusivamente** para navegación espacial y memoria de cuadrantes.
  * Mapea la posición de la punta del dedo índice (`landmark[8]`).
* **Mano Dominante (Derecha):**
  * Reservada para acciones geométricas, primitivas, operadores y delimitadores.

### 5.2. Segmentación Espacial por Cuadrantes (2 Filas $\times$ 3 Columnas)
El plano de la cámara se subdivide en 6 regiones de memoria:

```
+-------------------+-------------------+-------------------+
|   [ID_QUAD_1]     |   [ID_QUAD_2]     |   [ID_QUAD_3]     |
|   (Fila Sup-Izq)  |   (Fila Sup-Cen)  |   (Fila Sup-Der)  |
+-------------------+-------------------+-------------------+
|   [ID_QUAD_4]     |   [ID_QUAD_5]     |   [ID_QUAD_6]     |
|   (Fila Inf-Izq)  |   (Fila Inf-Cen)  |   (Fila Inf-Der)  |
+-------------------+-------------------+-------------------+
```

---

## 6. Catálogo Completo de Gestos y Mapeo de Tokens

### 6.1. Gestos Estáticos y Posturas (Mano Derecha)

| Token | Nombre del Gesto | Descripción Anatómica |
| :--- | :--- | :--- |
| `[INDEX_EXTENDED]` | Vértice / Punto | Dedo índice extendido hacia arriba; pulgar, medio, anular y meñique flexionados. |
| `[FRAME_SHAPE]` | Agrupar / Polígono | Forma de marco 'L' con pulgar e índice a 90° (unimanual) o manos entrelazadas formando marco rectangular (bimanual). |
| `[DOT_CIRCLE]` | Círculo | Forma de 'O' uniendo la yema del pulgar y el índice, manteniendo los dedos restantes abiertos (*OK sign*). |
| `[BLOCK_START]` | Inicio de Bloque | Palma completamente plana con los 5 dedos extendidos mirando hacia el frente (cámara). |
| `[BLOCK_END]` | Fin de Bloque | Puño cerrado orientado hacia el frente (0 dedos extendidos). |
| `[PALM_UP]` | Modificador (Rotación +) | Palma orientada hacia el techo (normal del plano en eje Y negativo). |
| `[PALM_DOWN]` | Modificador (Rotación -) | Palma orientada hacia el suelo (normal del plano en eje Y positivo). |
| `[OP_ASSIGN]` | Asignación (*Pinch*) | Pellizco uniendo las yemas de los dedos pulgar e índice/medio hacia el frente. |
| `[C_SHAPE_LEFT]` | Delimitador Izquierdo | Dedos y pulgar arqueados en forma de 'C' con la abertura hacia la izquierda. |
| `[C_SHAPE_RIGHT]` | Delimitador Derecho | Dedos y pulgar arqueados en forma de 'C' con la abertura hacia la derecha. |
| `[SIDE_SWIPE]` | Separador | Movimiento o deslizamiento horizontal rápido lateral de la mano. |
| `[DELIM_END]` | Fin de Instrucción | Bajar las manos por debajo del límite de encuadre ($y > 0.85$) o retirarlas del campo de visión tras emitir tokens. |

### 6.2. Gestos Dinámicos de Trayectoria Histórica

El sistema rastrea las últimas 25 a 30 posiciones $(x, y)$ de la punta del dedo índice en una cola circular:

| Token | Nombre | Criterio de Activación |
| :--- | :--- | :--- |
| `[ZIG_ZAG_MOTION]` | Trazar Línea | Al menos 3 cambios de signo consecutivos en la velocidad horizontal ($dx/dt$) con oscilación en el eje X. |
| `[LOOP_CIRCULAR]` | Bucle | Trayectoria circular continua cerrada alrededor del centroide acumulando $\approx \pm 2\pi$ radianes (~360°). |

---

## 7. Buffer Temporal de Multidígitos

1. **Detección Base (1 al 10):**
   * **1 a 5:** Dedos extendidos en una mano (`[NUM_1]` a `[NUM_5]`).
   * **6 a 10:** Suma de dedos extendidos con ambas manos en el encuadre (`[NUM_6]` a `[NUM_10]`).
2. **Concatenación:**
   * Al sostener una postura numérica se registra el dígito.
   * Si el usuario realiza una breve pausa de reposo (`[REST_STATE]`, $< 1.0\text{s}$) y realiza otra postura numérica, los valores se concatenan (ej. postura de `4` dedos, reposo breve, y luego `5` dedos genera `[NUM_45]`).
   * Si la pausa en reposo supera $1.0\text{s}$ o se ejecuta un gesto de acción no numérico, el buffer se vacía emitiendo el token consolidado.

---

## 8. Flujo de Salida y Protocolo de Salida

Cada token se emite con un espacio posterior a `sys.stdout` con vaciado inmediato. Al detectarse el fin de instrucción (`[DELIM_END]`), se imprime un salto de línea (`\n`), dejando la sentencia delimitada completa:

```bash
[ID_QUAD_1] [ZIG_ZAG_MOTION] [ID_QUAD_2] [NUM_45] [DELIM_END]
```

---

## 9. Pruebas Automatizadas

Se incluye la suite de pruebas unitarias en `test_detector.py` que evalúa:
* La correcta segmentación espacial de los 6 cuadrantes.
* El buffer de multidígitos y el temporizador de concatenación.
* La clasificación geométrica de cada postura estática.
* Los algoritmos de detección de trayectoria ([ZIG_ZAG_MOTION] y [LOOP_CIRCULAR]).
* El disparo de delimitadores y flujo de salida.

Para ejecutar las pruebas:
```bash
python test_detector.py
```
Salida esperada:
```text
>>> TODAS LAS PRUEBAS UNITARIAS PASARON EXITOSAMENTE! <<<
```
