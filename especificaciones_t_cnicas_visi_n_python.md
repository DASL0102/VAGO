# Especificaciones Técnicas del Módulo de Visión (Python) para VAGO

**Proyecto:** Visual Actions to Geometric Output (VAGO)  
**Módulo:** Detector de Gestos y Generador de Tokens en Tiempo Real  
**Tecnologías:** Python 3.x, OpenCV, MediaPipe Hands  

---

## 1. Objetivo General
Desarrollar un script ejecutable en Python (`vision_detector.py`) que procese el flujo de la cámara web en tiempo real, reconozca la postura y movimiento de las manos inspirados en HamNoSys, y emita la secuencia de tokens correspondiente entre corchetes (ej. `[ID_QUAD_1]`, `[ZIG_ZAG_MOTION]`, `[NUM_3]`, `[DELIM_END]`) directamente a la salida estándar (`sys.stdout`) con `flush=True` para su consumo por el compilador en C++.

---

## 2. Requisitos y Dependencias (`requirements.txt`)
```text
opencv-python>=4.8.0
mediapipe>=0.10.0
numpy>=1.24.0
```

---

## 3. Arquitectura y Lógica del Sistema

### 3.1. Segmentación Espacial (Memoria por Cuadrantes)
* **División:** El frame de video de la cámara debe dividirse invisiblemente en 6 regiones ($2 \times 3$):
  * **Fila Superior:** `[ID_QUAD_1]` (izquierda), `[ID_QUAD_2]` (centro), `[ID_QUAD_3]` (derecha).
  * **Fila Inferior:** `[ID_QUAD_4]` (izquierda), `[ID_QUAD_5]` (centro), `[ID_QUAD_6]` (derecha).
* **Overlay Visual:** Dibujar líneas divisorias tenues y etiquetas de cada cuadrante en el feed de video para dar realimentación al usuario.

### 3.2. Separación Bimanual (Navegación vs. Acciones)
* **Mano No Dominante (Izquierda):**
  * Reservada **exclusivamente** para navegación espacial y selección de memoria.
  * Al apuntar o posicionarse en una región, determinar el cuadrante mapeando las coordenadas $(x, y)$ de la punta del dedo índice (`landmark[8]` de MediaPipe) y emitir el token de cuadrante (`[ID_QUAD_1]` a `[ID_QUAD_6]`).
* **Mano Dominante (Derecha):**
  * Reservada para ejecutar acciones geométricas, operadores y estructuras de control.

---

## 4. Clasificación de Gestos y Mapeo de Tokens

### 4.1. Gestos Estáticos / Posturas
* **Vértice / Punto:** Dedo índice extendido (`landmark[8]`), demás dedos flexionados $\rightarrow$ `[INDEX_EXTENDED]`
* **Agrupar / Polígono:** Manos entrelazadas o formando marco $\rightarrow$ `[FRAME_SHAPE]`
* **Círculo:** Forma de 'O' con índice y pulgar $\rightarrow$ `[DOT_CIRCLE]`
* **Inicio de Bloque:** Palma plana extendida hacia el frente $\rightarrow$ `[BLOCK_START]`
* **Fin de Bloque:** Puño cerrado orientado al frente $\rightarrow$ `[BLOCK_END]`
* **Modificadores de Orientación:**
  * Palma orientada hacia arriba $\rightarrow$ `[PALM_UP]` (Rotación Positiva / Horaria)
  * Palma orientada hacia abajo $\rightarrow$ `[PALM_DOWN]` (Rotación Negativa / Antihoraria)
* **Asignación:** Gesto de pellizco (*pinch*) uniendo yemas de los dedos $\rightarrow$ `[OP_ASSIGN]`
* **Delimitadores de Expresión:**
  * Mano en 'C' orientada a la izquierda $\rightarrow$ `[C_SHAPE_LEFT]`
  * Mano en 'C' orientada a la derecha $\rightarrow$ `[C_SHAPE_RIGHT]`
* **Separador:** Deslizamiento lateral rápido de la mano $\rightarrow$ `[SIDE_SWIPE]`
* **Fin de Instrucción:** Bajar las manos fuera del recuadro de detección $\rightarrow$ `[DELIM_END]`

### 4.2. Gestos Dinámicos (Trayectoria Histórica)
* Mantener una cola circular (`collections.deque`) de las últimas 15 a 30 posiciones $(x, y)$ del punto clave de la mano.
* **Trazar Línea (`[ZIG_ZAG_MOTION]`):** Disparar cuando la trayectoria muestre oscilaciones horizontales repetidas en el eje X.
* **Bucle (`[LOOP_CIRCULAR]`):** Disparar cuando el historial de coordenadas describa un giro circular continuo.

---

## 5. Buffer Temporal de Multidígitos
1. **Detección Base:** Contar dedos extendidos para valores del 1 al 10 (`[NUM_1]` a `[NUM_10]`).
2. **Concatenación:** Si el usuario realiza una postura numérica (ej. 4 dedos), hace una pausa breve en reposo (`[REST_STATE]`, $< 1.0$s) y realiza otra postura (ej. 5 dedos), el sistema debe concatenar las lecturas en un buffer y emitir un único token: `[NUM_45]`.

---

## 6. Antirrebote, Estado Neutro y Salida
* **Anti-rebote (Debounce):** Exigir que una postura se mantenga estable durante una ventana mínima de fotogramas (ej. 5 a 8 frames) antes de validar la emisión del token.
* **Estado de Reposo:** Interrupciones o posiciones neutras deben clasificarse como `[REST_STATE]` y ser ignoradas en la salida estándar.
* **Flujo de Salida:** Imprimir cada token o instrucción delimitada a la consola de forma limpia:
  ```bash
  [ID_QUAD_1] [ZIG_ZAG_MOTION] [ID_QUAD_2] [NUM_3] [DELIM_END]
  ```

---

## 7. Entregables Esperados
1. Código fuente completo en `vision_detector.py`.
2. Archivo `requirements.txt`.
3. Ventana interactiva de OpenCV mostrando:
   * Video en vivo procesado.
   * La cuadrícula de 6 zonas.
   * Los puntos clave (*landmarks*) de las manos trazados.
   * El token o instrucción actual en la parte superior del fotograma.