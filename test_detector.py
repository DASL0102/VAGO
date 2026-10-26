"""
=============================================================================
Suite de Pruebas Unitarias e Integración para vision_detector.py
=============================================================================
Verifica la corrección matemática y lógica de:
1. Segmentación espacial (6 cuadrantes)
2. Buffer temporal de multidígitos y concatenación
3. Clasificación de gestos estáticos y cinemáticos
4. Detección de trayectorias dinámicas ([ZIG_ZAG_MOTION] y [LOOP_CIRCULAR])
5. Delimitadores y antirrebote
=============================================================================
"""

import time
import numpy as np

from vision_detector import (
    QuadrantManager,
    MultidigitBuffer,
    GestureClassifier,
    TokenStreamEmitter,
    DetectedHand,
    WRIST, THUMB_TIP, THUMB_MCP, INDEX_TIP, INDEX_MCP, INDEX_PIP, INDEX_DIP,
    MIDDLE_TIP, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP,
    RING_TIP, RING_MCP, RING_PIP, RING_DIP,
    PINKY_TIP, PINKY_MCP, PINKY_PIP, PINKY_DIP
)


def create_synthetic_hand(
    label: str = "Right",
    wrist=(0.5, 0.7, 0.0),
    fingers_extended=(True, True, True, True, True),
    palm_normal=(0.0, 0.0, -1.0),
    custom_landmarks=None
) -> DetectedHand:
    """Genera una mano sintética con 21 landmarks calibrados para pruebas."""
    if custom_landmarks is not None:
        lms = np.array(custom_landmarks, dtype=np.float32)
        return DetectedHand(label, lms, 640, 480)

    lms = np.zeros((21, 3), dtype=np.float32)
    wx, wy, wz = wrist
    lms[WRIST] = [wx, wy, wz]

    # MCPs
    lms[INDEX_MCP] = [wx - 0.05, wy - 0.15, wz]
    lms[MIDDLE_MCP] = [wx, wy - 0.16, wz]
    lms[RING_MCP] = [wx + 0.04, wy - 0.15, wz]
    lms[PINKY_MCP] = [wx + 0.08, wy - 0.13, wz]
    lms[1] = [wx - 0.06, wy - 0.05, wz]
    lms[2] = [wx - 0.09, wy - 0.08, wz]
    lms[3] = [wx - 0.11, wy - 0.12, wz]

    thumb_ext, idx_ext, mid_ext, ring_ext, pinky_ext = fingers_extended

    # Pulgar
    if thumb_ext:
        lms[THUMB_TIP] = [wx - 0.14, wy - 0.16, wz]
    else:
        lms[THUMB_TIP] = [wx - 0.02, wy - 0.12, wz]

    # Índice
    if idx_ext:
        lms[INDEX_PIP] = [wx - 0.05, wy - 0.22, wz]
        lms[INDEX_DIP] = [wx - 0.05, wy - 0.28, wz]
        lms[INDEX_TIP] = [wx - 0.05, wy - 0.34, wz]
    else:
        lms[INDEX_PIP] = [wx - 0.05, wy - 0.18, wz]
        lms[INDEX_DIP] = [wx - 0.05, wy - 0.14, wz]
        lms[INDEX_TIP] = [wx - 0.05, wy - 0.12, wz]

    # Medio
    if mid_ext:
        lms[MIDDLE_PIP] = [wx, wy - 0.24, wz]
        lms[MIDDLE_DIP] = [wx, wy - 0.30, wz]
        lms[MIDDLE_TIP] = [wx, wy - 0.36, wz]
    else:
        lms[MIDDLE_PIP] = [wx, wy - 0.18, wz]
        lms[MIDDLE_DIP] = [wx, wy - 0.14, wz]
        lms[MIDDLE_TIP] = [wx, wy - 0.12, wz]

    # Anular
    if ring_ext:
        lms[RING_PIP] = [wx + 0.04, wy - 0.22, wz]
        lms[RING_DIP] = [wx + 0.04, wy - 0.28, wz]
        lms[RING_TIP] = [wx + 0.04, wy - 0.34, wz]
    else:
        lms[RING_PIP] = [wx + 0.04, wy - 0.18, wz]
        lms[RING_DIP] = [wx + 0.04, wy - 0.14, wz]
        lms[RING_TIP] = [wx + 0.04, wy - 0.12, wz]

    # Meñique
    if pinky_ext:
        lms[PINKY_PIP] = [wx + 0.08, wy - 0.20, wz]
        lms[PINKY_DIP] = [wx + 0.08, wy - 0.25, wz]
        lms[PINKY_TIP] = [wx + 0.08, wy - 0.30, wz]
    else:
        lms[PINKY_PIP] = [wx + 0.08, wy - 0.16, wz]
        lms[PINKY_DIP] = [wx + 0.08, wy - 0.13, wz]
        lms[PINKY_TIP] = [wx + 0.08, wy - 0.11, wz]

    hand = DetectedHand(label, lms, 640, 480)
    # Sobrescribir normal si se solicita
    hand.palm_normal = np.array(palm_normal, dtype=np.float32)
    return hand


def test_quadrant_segmentation():
    """Prueba que los 6 cuadrantes se detectan adecuadamente según posición del índice de mano izquierda."""
    qm = QuadrantManager(debounce_frames=3)

    # Cuadrante 1: Sup-Izq (x < 1/3, y < 1/2)
    h_q1 = create_synthetic_hand("Left")
    h_q1.norm_landmarks[INDEX_TIP] = [0.15, 0.20, 0.0]
    tokens = [qm.update(h_q1) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_1]"

    # Cuadrante 2: Sup-Centro (1/3 <= x < 2/3, y < 1/2)
    h_q2 = create_synthetic_hand("Left")
    h_q2.norm_landmarks[INDEX_TIP] = [0.50, 0.20, 0.0]
    tokens = [qm.update(h_q2) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_2]"

    # Cuadrante 3: Sup-Der (x >= 2/3, y < 1/2)
    h_q3 = create_synthetic_hand("Left")
    h_q3.norm_landmarks[INDEX_TIP] = [0.85, 0.20, 0.0]
    tokens = [qm.update(h_q3) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_3]"

    # Cuadrante 4: Inf-Izq (x < 1/3, y >= 1/2)
    h_q4 = create_synthetic_hand("Left")
    h_q4.norm_landmarks[INDEX_TIP] = [0.15, 0.75, 0.0]
    tokens = [qm.update(h_q4) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_4]"

    # Cuadrante 5: Inf-Centro (1/3 <= x < 2/3, y >= 1/2)
    h_q5 = create_synthetic_hand("Left")
    h_q5.norm_landmarks[INDEX_TIP] = [0.50, 0.75, 0.0]
    tokens = [qm.update(h_q5) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_5]"

    # Cuadrante 6: Inf-Der (x >= 2/3, y >= 1/2)
    h_q6 = create_synthetic_hand("Left")
    h_q6.norm_landmarks[INDEX_TIP] = [0.85, 0.75, 0.0]
    tokens = [qm.update(h_q6) for _ in range(3)]
    assert tokens[-1] == "[ID_QUAD_6]"


def test_multidigit_buffer():
    """Prueba la concatenación de dígitos: ej. 4 seguido de 5 con reposo breve -> [NUM_45]."""
    buf = MultidigitBuffer(timeout_sec=0.2)

    # 1. Ingresar dígito 4
    buf.push_digit(4)
    # Estado de reposo breve
    buf.enter_rest()
    time.sleep(0.05)  # < 0.2s
    # Ingresar dígito 5
    buf.push_digit(5)
    buf.enter_rest()

    # Antes del timeout, no debe emitir
    assert buf.check_timeout() is None

    # Esperar que expire el timeout de 0.2s
    time.sleep(0.22)
    token = buf.check_timeout()
    assert token == "[NUM_45]"

    # Probar número único
    buf.push_digit(3)
    buf.enter_rest()
    time.sleep(0.22)
    token = buf.check_timeout()
    assert token == "[NUM_3]"


def test_static_gestures_classification():
    """Prueba la clasificación de gestos estáticos clave."""
    clf = GestureClassifier()

    # 1. INDEX_EXTENDED: sólo dedo índice extendido
    h_idx = create_synthetic_hand("Right", fingers_extended=(False, True, False, False, False))
    gesture, _ = clf.classify_static_and_kinematic(h_idx, None)
    assert gesture == "[INDEX_EXTENDED]"

    # 2. BLOCK_START: los 5 dedos extendidos mirando al frente
    h_block_start = create_synthetic_hand("Right", fingers_extended=(True, True, True, True, True), palm_normal=(0, 0, -0.9))
    gesture, _ = clf.classify_static_and_kinematic(h_block_start, None)
    assert gesture == "[BLOCK_START]"

    # 3. BLOCK_END: puño cerrado (0 dedos extendidos)
    h_fist = create_synthetic_hand("Right", fingers_extended=(False, False, False, False, False))
    gesture, _ = clf.classify_static_and_kinematic(h_fist, None)
    assert gesture == "[BLOCK_END]"

    # 4. PALM_UP: normal apuntando hacia arriba (Y negativo)
    h_up = create_synthetic_hand("Right", fingers_extended=(True, True, True, True, False), palm_normal=(0, -0.85, 0.1))
    gesture, _ = clf.classify_static_and_kinematic(h_up, None)
    assert gesture == "[PALM_UP]"

    # 5. PALM_DOWN: normal apuntando hacia abajo (Y positivo)
    h_down = create_synthetic_hand("Right", fingers_extended=(True, True, True, True, False), palm_normal=(0, 0.85, 0.1))
    gesture, _ = clf.classify_static_and_kinematic(h_down, None)
    assert gesture == "[PALM_DOWN]"

    # 6. DOT_CIRCLE: pulgar e índice tocándose, demás dedos extendidos
    h_circle = create_synthetic_hand("Right", fingers_extended=(False, True, True, True, True))
    h_circle.norm_landmarks[INDEX_TIP] = [0.45, 0.50, 0.0]
    h_circle.norm_landmarks[THUMB_TIP] = [0.45, 0.51, 0.0]  # tocándose
    gesture, _ = clf.classify_static_and_kinematic(h_circle, None)
    assert gesture == "[DOT_CIRCLE]"

    # 7. OP_ASSIGN (Pinch): pulgar e índice tocándose con dedos plegados
    h_pinch = create_synthetic_hand("Right", fingers_extended=(False, False, False, False, False))
    h_pinch.norm_landmarks[INDEX_TIP] = [0.45, 0.50, 0.0]
    h_pinch.norm_landmarks[THUMB_TIP] = [0.45, 0.51, 0.0]
    h_pinch.norm_landmarks[MIDDLE_TIP] = [0.46, 0.51, 0.0]
    gesture, _ = clf.classify_static_and_kinematic(h_pinch, None)
    assert gesture == "[OP_ASSIGN]"

    # 8. FRAME_SHAPE: forma de 'L' con pulgar e índice perpendiculares
    h_frame = create_synthetic_hand("Right", fingers_extended=(True, True, False, False, False))
    # Índice vertical hacia arriba
    h_frame.norm_landmarks[INDEX_MCP] = [0.5, 0.6, 0.0]
    h_frame.norm_landmarks[INDEX_PIP] = [0.5, 0.53, 0.0]
    h_frame.norm_landmarks[INDEX_DIP] = [0.5, 0.46, 0.0]
    h_frame.norm_landmarks[INDEX_TIP] = [0.5, 0.4, 0.0]
    # Pulgar horizontal hacia la izquierda
    h_frame.norm_landmarks[THUMB_MCP] = [0.5, 0.6, 0.0]
    h_frame.norm_landmarks[THUMB_TIP] = [0.35, 0.6, 0.0]
    gesture, _ = clf.classify_static_and_kinematic(h_frame, None)
    assert gesture == "[FRAME_SHAPE]"


def test_trajectory_gestures():
    """Prueba gestos dinámicos de trayectoria: [ZIG_ZAG_MOTION] y [LOOP_CIRCULAR]."""
    clf = GestureClassifier(trajectory_len=30)
    h = create_synthetic_hand("Right")

    # 1. Simulación de Zig-Zag (oscilación en X con 4 reversas)
    t = np.linspace(0, 1, 28)
    xs = 0.5 + 0.15 * np.sin(2 * np.pi * 2.0 * t)
    ys = np.linspace(0.4, 0.6, 28)

    fired_token = None
    for x, y in zip(xs, ys):
        h.norm_landmarks[INDEX_TIP] = [x, y, 0.0]
        tok = clf.update_trajectory_gestures(h)
        if tok:
            fired_token = tok

    assert fired_token == "[ZIG_ZAG_MOTION]"

    # 2. Simulación de Loop Circular (círculo 360 grados)
    clf.trajectory.clear()
    theta = np.linspace(0, 2 * np.pi, 26)
    circ_x = 0.5 + 0.08 * np.cos(theta)
    circ_y = 0.5 + 0.08 * np.sin(theta)

    fired_circle = None
    for x, y in zip(circ_x, circ_y):
        h.norm_landmarks[INDEX_TIP] = [x, y, 0.0]
        tok = clf.update_trajectory_gestures(h)
        if tok:
            fired_circle = tok

    assert fired_circle == "[LOOP_CIRCULAR]"


def test_delim_end():
    """Prueba que bajar las manos fuera del recuadro genera [DELIM_END]."""
    clf = GestureClassifier()
    h = create_synthetic_hand("Right")

    # Manos activas
    for _ in range(3):
        clf.classify_static_and_kinematic(h, None)
    assert clf.had_hands_active is True

    # Bajar manos (y > 0.85)
    h_low = create_synthetic_hand("Right")
    h_low.norm_landmarks[:, 1] = 0.92

    fired_delim = None
    for _ in range(7):
        tok, _ = clf.classify_static_and_kinematic(h_low, None)
        if tok == "[DELIM_END]":
            fired_delim = tok

    assert fired_delim == "[DELIM_END]"


def test_token_stream():
    """Prueba que los tokens se formatean y acumulan correctamente."""
    stream = TokenStreamEmitter()
    stream.emit_token("[ID_QUAD_1]")
    stream.emit_token("[ZIG_ZAG_MOTION]")
    stream.emit_token("[NUM_3]")
    assert stream.get_current_instruction_str() == "[ID_QUAD_1] [ZIG_ZAG_MOTION] [NUM_3]"

    stream.emit_token("[DELIM_END]")
    assert len(stream.history_instructions) == 1
    assert stream.history_instructions[0] == "[ID_QUAD_1] [ZIG_ZAG_MOTION] [NUM_3] [DELIM_END]"
    assert stream.current_instruction_tokens == []


if __name__ == "__main__":
    test_quadrant_segmentation()
    test_multidigit_buffer()
    test_static_gestures_classification()
    test_trajectory_gestures()
    test_delim_end()
    test_token_stream()
    print("\n>>> TODAS LAS PRUEBAS UNITARIAS PASARON EXITOSAMENTE! <<<")
