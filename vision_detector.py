#!/usr/bin/env python3
"""
=============================================================================
PROYECTO: Visual Actions to Geometric Output (VAGO)
MÓDULO: Detector de Gestos y Generador de Tokens en Tiempo Real
ARCHIVO: vision_detector.py
TECNOLOGÍAS: Python 3.x, OpenCV, MediaPipe Hands, NumPy
=============================================================================
Este script procesa el flujo de la cámara web en tiempo real, reconoce la postura
y movimiento de las manos inspirados en HamNoSys, y emite la secuencia de tokens
correspondiente entre corchetes (ej. [ID_QUAD_1], [ZIG_ZAG_MOTION], [NUM_45], [DELIM_END])
directamente a sys.stdout con flush=True para su consumo por el compilador en C++.
"""

import os
import sys
import time
import math
import argparse
import urllib.request
from collections import deque
from typing import List, Tuple, Optional, Dict, Any

# Suprimir logs verbosos de TensorFlow / MediaPipe C++ en stderr
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import cv2
import numpy as np
import mediapipe as mp

# URL oficial del modelo de HandLandmarker de Google MediaPipe (Tasks API)
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_FILENAME = "hand_landmarker.task"

# =============================================================================
# CONSTANTES DE LANDMARKS DE MEDIAPIPE HANDS
# =============================================================================
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4

INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8

MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12

RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16

PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# Conexiones estándar del esqueleto de la mano (21 puntos)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Pulgar
    (0, 5), (5, 6), (6, 7), (7, 8),        # Índice
    (5, 9), (9, 10), (10, 11), (11, 12),   # Medio
    (9, 13), (13, 14), (14, 15), (15, 16), # Anular
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20) # Meñique y Palma
]

# Nombres de Cuadrantes (2 filas x 3 columnas)
QUADRANT_TOKENS = {
    (0, 0): "[ID_QUAD_1]",  # Fila superior, izquierda
    (0, 1): "[ID_QUAD_2]",  # Fila superior, centro
    (0, 2): "[ID_QUAD_3]",  # Fila superior, derecha
    (1, 0): "[ID_QUAD_4]",  # Fila inferior, izquierda
    (1, 1): "[ID_QUAD_5]",  # Fila inferior, centro
    (1, 2): "[ID_QUAD_6]",  # Fila inferior, derecha
}


# =============================================================================
# ESTRUCTURA DE DATOS PARA UNA MANO DETECTADA
# =============================================================================
class DetectedHand:
    """Encapsula los landmarks, etiquetas y propiedades calculadas de una mano."""
    def __init__(self, label: str, landmarks: np.ndarray, frame_w: int, frame_h: int):
        self.label = label  # 'Left' (No dominante) o 'Right' (Dominante)
        self.norm_landmarks = landmarks  # Matriz (21, 3) normalizada [0, 1]
        self.pixel_landmarks = np.zeros((21, 2), dtype=np.int32)
        self.pixel_landmarks[:, 0] = np.clip(landmarks[:, 0] * frame_w, 0, frame_w - 1).astype(np.int32)
        self.pixel_landmarks[:, 1] = np.clip(landmarks[:, 1] * frame_h, 0, frame_h - 1).astype(np.int32)

        # Escala de la palma (2D para inmunidad al ruido de profundidad Z)
        self.palm_scale = max(float(np.linalg.norm(landmarks[WRIST, :2] - landmarks[MIDDLE_MCP, :2])), 0.001)

        # Vector normal a la palma 3D (orientado hacia afuera de la palma en vista espejo)
        v1 = landmarks[INDEX_MCP] - landmarks[WRIST]
        v2 = landmarks[PINKY_MCP] - landmarks[WRIST]
        normal = np.cross(v2, v1) if label == "Right" else np.cross(v1, v2)
        norm_mag = np.linalg.norm(normal)
        self.palm_normal = normal / (norm_mag + 1e-7)


# =============================================================================
# ENCAPSULADOR DE MEDIAPIPE (Tasks API y Legacy API) CON SUAVIZADO TEMPORAL
# =============================================================================
class HandTracker:
    """
    Rastreador de manos compatible de forma transparente con:
    1) MediaPipe Tasks HandLandmarker (MediaPipe >= 0.10.14+)
    2) MediaPipe Solutions Hands (MediaPipe legacy)
    Incluye filtrado exponencial adaptativo (EMA) para reducir el temblor de landmarks
    y asignación espacial/anatómica estable de mano izquierda y derecha.
    """
    def __init__(self, max_hands: int = 2, min_detection_conf: float = 0.5, min_track_conf: float = 0.5):
        self.max_hands = max_hands
        self.min_detection_conf = min_detection_conf
        self.min_track_conf = min_track_conf
        self.use_tasks = False
        self.detector = None
        self._prev_smoothed: Dict[str, np.ndarray] = {}
        self._prev_wrist_pos: Dict[str, np.ndarray] = {}

        if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
            # Usar API clásica si está disponible
            self.mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=max_hands,
                min_detection_confidence=min_detection_conf,
                min_tracking_confidence=min_track_conf
            )
            self.use_tasks = False
        else:
            # Usar MediaPipe Tasks API
            self._init_tasks_api()
            self.use_tasks = True

    def _init_tasks_api(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, MODEL_FILENAME)

        if not os.path.exists(model_path):
            sys.stderr.write(f"[INFO] Descargando modelo MediaPipe HandLandmarker a {model_path}...\n")
            sys.stderr.flush()
            try:
                urllib.request.urlretrieve(MODEL_URL, model_path)
                sys.stderr.write("[INFO] Descarga completada con éxito.\n")
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"[ERROR] Error al descargar modelo MediaPipe: {e}\n")
                sys.stderr.flush()
                raise

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=self.max_hands,
            min_hand_detection_confidence=self.min_detection_conf,
            min_tracking_confidence=self.min_track_conf
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

    def _smooth_landmarks(self, label: str, lms: np.ndarray) -> np.ndarray:
        """Aplica suavizado exponencial adaptativo (EMA) para eliminar jitter sin añadir latencia."""
        wrist_xy = lms[WRIST, :2]
        if label in self._prev_smoothed and label in self._prev_wrist_pos:
            dist = float(np.linalg.norm(wrist_xy - self._prev_wrist_pos[label]))
            if dist < 0.18:
                # Si se mueve rápido (ej. swipe o zig-zag), responder rápido (alpha alto);
                # si está quieta haciendo una postura, suavizar más (alpha moderado).
                alpha = 0.82 if dist > 0.025 else 0.50
                smoothed = alpha * lms + (1.0 - alpha) * self._prev_smoothed[label]
                self._prev_smoothed[label] = smoothed
                self._prev_wrist_pos[label] = wrist_xy
                return smoothed

        self._prev_smoothed[label] = lms.copy()
        self._prev_wrist_pos[label] = wrist_xy.copy()
        return lms

    def process(self, rgb_frame: np.ndarray, is_mirrored: bool = True) -> List[DetectedHand]:
        """Procesa un fotograma RGB y retorna lista de DetectedHand con roles estabilizados."""
        h, w, _ = rgb_frame.shape
        raw_detections: List[Tuple[str, float, np.ndarray]] = []

        if not self.use_tasks:
            results = self.mp_hands.process(rgb_frame)
            if results and results.multi_hand_landmarks:
                for idx, hand_lms in enumerate(results.multi_hand_landmarks):
                    label = "Right"
                    score = 0.8
                    if results.multi_handedness and idx < len(results.multi_handedness):
                        cls_info = results.multi_handedness[idx].classification[0]
                        raw_label = cls_info.label
                        score = float(cls_info.score)
                        label = ("Left" if raw_label == "Right" else "Right") if is_mirrored else raw_label

                    lms_array = np.array([[lm.x, lm.y, lm.z] for lm in hand_lms.landmark], dtype=np.float32)
                    raw_detections.append((label, score, lms_array))
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.detector.detect(mp_image)
            if results and results.hand_landmarks:
                for idx, hand_lms in enumerate(results.hand_landmarks):
                    label = "Right"
                    score = 0.8
                    if results.handedness and idx < len(results.handedness):
                        cat = results.handedness[idx][0]
                        raw_label = cat.category_name
                        score = float(cat.score)
                        label = ("Left" if raw_label == "Right" else "Right") if is_mirrored else raw_label

                    lms_array = np.array([[lm.x, lm.y, lm.z] for lm in hand_lms], dtype=np.float32)
                    raw_detections.append((label, score, lms_array))

        if not raw_detections:
            self._prev_smoothed.clear()
            self._prev_wrist_pos.clear()
            return []

        detected_hands: List[DetectedHand] = []

        # Si hay 2 manos presentes, asignarlas por posición horizontal relativa (izquierda vs derecha)
        # para evitar que al rotar la muñeca MediaPipe invierta o duplique la etiqueta de ambas manos.
        if len(raw_detections) >= 2:
            sorted_dets = sorted(raw_detections[:2], key=lambda item: float(item[2][WRIST, 0]))
            left_role = "Left" if is_mirrored else "Right"
            right_role = "Right" if is_mirrored else "Left"
            lms_left = self._smooth_landmarks(left_role, sorted_dets[0][2])
            lms_right = self._smooth_landmarks(right_role, sorted_dets[1][2])
            detected_hands.append(DetectedHand(left_role, lms_left, w, h))
            detected_hands.append(DetectedHand(right_role, lms_right, w, h))
        else:
            label, score, lms = raw_detections[0]
            wrist_xy = lms[WRIST, :2]
            # Continuidad temporal: si la mano estaba rastreada muy cerca en el frame previo
            # y MediaPipe duda al rotar la muñeca, mantener la identidad previa.
            for prev_label, prev_pos in self._prev_wrist_pos.items():
                if float(np.linalg.norm(wrist_xy - prev_pos)) < 0.12 and score < 0.88:
                    label = prev_label
                    break
            # Dejar solo la mano activa en el historial para no confundir futuros frames
            other_label = "Left" if label == "Right" else "Right"
            self._prev_smoothed.pop(other_label, None)
            self._prev_wrist_pos.pop(other_label, None)
            lms_smooth = self._smooth_landmarks(label, lms)
            detected_hands.append(DetectedHand(label, lms_smooth, w, h))

        return detected_hands

    def close(self):
        """Cierra el detector de forma segura y limpia recursos."""
        try:
            if self.use_tasks and self.detector is not None:
                self.detector.close()
                self.detector = None
            elif hasattr(self, "mp_hands") and self.mp_hands is not None:
                self.mp_hands.close()
                self.mp_hands = None
        except Exception:
            pass


# =============================================================================
# GESTOR DE SEGMENTACIÓN ESPACIAL (CUADRANTES)
# =============================================================================
class QuadrantManager:
    """
    Gestiona la división espacial en 6 cuadrantes (2 filas x 3 columnas)
    y el reconocimiento de la posición de la mano no dominante (izquierda).
    """
    def __init__(self, debounce_frames: int = 6):
        self.debounce_frames = debounce_frames
        self.candidate_quad: Optional[str] = None
        self.candidate_counter: int = 0
        self.current_quad: Optional[str] = None
        self.active_grid_pos: Optional[Tuple[int, int]] = None

    def update(self, left_hand: Optional[DetectedHand]) -> Optional[str]:
        """
        Determina el cuadrante en base al landmark[8] (índice) de la mano izquierda.
        Retorna el token [ID_QUAD_X] únicamente cuando un nuevo cuadrante se estabiliza.
        """
        if left_hand is None:
            self.candidate_quad = None
            self.candidate_counter = 0
            self.active_grid_pos = None
            return None

        # Coordenadas normalizadas del dedo índice
        idx_tip = left_hand.norm_landmarks[INDEX_TIP]
        x, y = idx_tip[0], idx_tip[1]

        # Determinar fila (0: superior, 1: inferior)
        row = 0 if y < 0.5 else 1
        # Determinar columna (0: izquierda, 1: centro, 2: derecha)
        col = 0 if x < (1.0 / 3.0) else (1 if x < (2.0 / 3.0) else 2)

        self.active_grid_pos = (row, col)
        quad_token = QUADRANT_TOKENS.get((row, col), None)

        if quad_token == self.candidate_quad:
            self.candidate_counter += 1
        else:
            self.candidate_quad = quad_token
            self.candidate_counter = 1

        if self.candidate_counter >= self.debounce_frames:
            if self.candidate_quad != self.current_quad:
                self.current_quad = self.candidate_quad
                return self.current_quad

        return None


# =============================================================================
# BUFFER TEMPORAL DE MULTIDÍGITOS
# =============================================================================
class MultidigitBuffer:
    """
    Maneja la detección y concatenación de dígitos del 1 al 10.
    Si se realiza un número, luego reposo ([REST_STATE]) por < 1.0s,
    y otro número, los concatena (ej. 4 y luego 5 -> [NUM_45]).
    Si transcurre más de 1.0s en reposo, o llega un token no numérico,
    emite el token consolidado.
    """
    def __init__(self, timeout_sec: float = 1.0):
        self.timeout_sec = timeout_sec
        self.digits: List[int] = []
        self.last_digit_time: float = 0.0
        self.in_rest_window: bool = False

    def push_digit(self, digit: int):
        """Agrega un dígito detectado al buffer."""
        self.digits.append(digit)
        self.last_digit_time = time.time()
        self.in_rest_window = False

    def enter_rest(self):
        """Notifica que el sistema entró en estado de reposo."""
        if self.digits:
            self.in_rest_window = True

    def check_timeout(self) -> Optional[str]:
        """Verifica si expiró el tiempo de concatenación de dígitos."""
        if self.digits and self.in_rest_window:
            if time.time() - self.last_digit_time >= self.timeout_sec:
                return self.flush()
        return None

    def flush(self) -> Optional[str]:
        """Consolida y vacía el buffer, retornando el token de número."""
        if not self.digits:
            return None
        concatenated_str = "".join(str(d) for d in self.digits)
        token = f"[NUM_{concatenated_str}]"
        self.digits.clear()
        self.in_rest_window = False
        return token

    def is_active(self) -> bool:
        return len(self.digits) > 0

    def get_preview(self) -> str:
        if not self.digits:
            return ""
        elapsed = time.time() - self.last_digit_time if self.in_rest_window else 0.0
        remaining = max(0.0, self.timeout_sec - elapsed)
        digits_str = "".join(str(d) for d in self.digits)
        return f"NUM_{digits_str} ({remaining:.1f}s)"


# =============================================================================
# CLASIFICADOR DE GESTOS Y TRAYECTORIAS DINÁMICAS
# =============================================================================
class GestureClassifier:
    """
    Clasificador de gestos estáticos, cinemáticos y de trayectoria
    basado en las especificaciones del sistema VAGO.
    """
    def __init__(self, trajectory_len: int = 25):
        # Cola circular de posiciones históricas del índice para gestos dinámicos
        self.trajectory: deque = deque(maxlen=trajectory_len)
        self.timestamps: deque = deque(maxlen=trajectory_len)

        # Historial de velocidad lateral para [SIDE_SWIPE]
        self.swipe_history: deque = deque(maxlen=8)

        # Anti-rebote para gestos
        self.debounce_frames = 6
        self.candidate_gesture: str = "[REST_STATE]"
        self.candidate_counter: int = 0
        self.last_emitted_gesture: str = "[REST_STATE]"

        # Seguimiento de manos presentes para [DELIM_END]
        self.had_hands_active: bool = False
        self.hands_absent_counter: int = 0

    @staticmethod
    def _is_finger_extended(lms: np.ndarray, tip_idx: int, pip_idx: int, mcp_idx: int, palm_scale: float) -> bool:
        """Determina si un dedo (índice, medio, anular o meñique) está extendido con tolerancias naturales."""
        d_tip_wrist = np.linalg.norm(lms[tip_idx] - lms[WRIST])
        d_pip_wrist = np.linalg.norm(lms[pip_idx] - lms[WRIST])
        d_tip_mcp = np.linalg.norm(lms[tip_idx] - lms[mcp_idx])

        # Vector MCP -> PIP y PIP -> TIP para evaluar alineación/rectitud
        v1 = lms[pip_idx] - lms[mcp_idx]
        v2 = lms[tip_idx] - lms[pip_idx]
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)

        # Criterio más flexible y robusto ante ligeras flexiones o perspectiva oblicua
        return bool(d_tip_wrist > d_pip_wrist * 1.05 and d_tip_mcp > 0.60 * palm_scale and cos_angle > 0.40)

    @staticmethod
    def _is_thumb_extended(lms: np.ndarray, palm_scale: float) -> bool:
        """Determina si el pulgar está extendido y separado de la palma."""
        d_tip_pinky_mcp = np.linalg.norm(lms[THUMB_TIP] - lms[PINKY_MCP])
        d_tip_index_mcp = np.linalg.norm(lms[THUMB_TIP] - lms[INDEX_MCP])
        d_tip_wrist = np.linalg.norm(lms[THUMB_TIP] - lms[WRIST])
        d_cmc_wrist = np.linalg.norm(lms[THUMB_CMC] - lms[WRIST])
        return bool(d_tip_pinky_mcp > 0.85 * palm_scale and d_tip_index_mcp > 0.38 * palm_scale and d_tip_wrist > d_cmc_wrist * 1.10)

    def count_extended_fingers(self, hand: DetectedHand) -> Tuple[int, List[bool]]:
        """Cuenta el número de dedos extendidos en una mano dada."""
        lms = hand.norm_landmarks
        ps = hand.palm_scale
        thumb = self._is_thumb_extended(lms, ps)
        index = self._is_finger_extended(lms, INDEX_TIP, INDEX_PIP, INDEX_MCP, ps)
        middle = self._is_finger_extended(lms, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP, ps)
        ring = self._is_finger_extended(lms, RING_TIP, RING_PIP, RING_MCP, ps)
        pinky = self._is_finger_extended(lms, PINKY_TIP, PINKY_PIP, PINKY_MCP, ps)

        states = [thumb, index, middle, ring, pinky]
        return sum(states), states

    def classify_static_and_kinematic(
        self,
        right_hand: Optional[DetectedHand],
        left_hand: Optional[DetectedHand]
    ) -> Tuple[str, Optional[int]]:
        """
        Clasifica la postura estática actual o gesto cinemático de acción.
        Retorna (token_gesture, digit_value_if_numeric).
        """
        # Si ambas manos bajaron por debajo de 0.82 o no hay manos activas tras actividad
        all_hands_low = True
        present_hands = [h for h in (right_hand, left_hand) if h is not None]

        if present_hands:
            for h in present_hands:
                if np.mean(h.norm_landmarks[:, 1]) < 0.82:
                    all_hands_low = False
                    break
        else:
            all_hands_low = True

        if all_hands_low and self.had_hands_active:
            self.hands_absent_counter += 1
            if self.hands_absent_counter >= 5:
                self.had_hands_active = False
                self.hands_absent_counter = 0
                return "[DELIM_END]", None
            return "[REST_STATE]", None

        if present_hands:
            self.had_hands_active = True
            self.hands_absent_counter = 0

        # Verificación de gesto de Marco Bimanual ([FRAME_SHAPE])
        if right_hand is not None and left_hand is not None:
            r_lms = right_hand.norm_landmarks
            l_lms = left_hand.norm_landmarks
            # Si el pulgar de una mano está cerca del índice de la otra mano y viceversa
            dist_cross1 = np.linalg.norm(r_lms[INDEX_TIP] - l_lms[THUMB_TIP])
            dist_cross2 = np.linalg.norm(l_lms[INDEX_TIP] - r_lms[THUMB_TIP])
            avg_ps = (right_hand.palm_scale + left_hand.palm_scale) / 2.0
            if dist_cross1 < 0.9 * avg_ps and dist_cross2 < 0.9 * avg_ps:
                return "[FRAME_SHAPE]", None

            # Conteo bimanual para números de 6 a 10
            r_count, r_states = self.count_extended_fingers(right_hand)
            l_count, l_states = self.count_extended_fingers(left_hand)
            total_fingers = r_count + l_count
            if 6 <= total_fingers <= 10:
                return f"[NUM_{total_fingers}]", total_fingers

        # Si no hay mano derecha activa, estamos en reposo para acciones
        if right_hand is None:
            return "[REST_STATE]", None

        # Análisis de la Mano Dominante (Derecha)
        lms = right_hand.norm_landmarks
        ps = right_hand.palm_scale
        ext_count, states = self.count_extended_fingers(right_hand)
        thumb_ext, idx_ext, mid_ext, ring_ext, pinky_ext = states

        # 1. Separador: Deslizamiento lateral rápido ([SIDE_SWIPE])
        curr_x = lms[INDEX_MCP, 0]
        curr_y = lms[INDEX_MCP, 1]
        self.swipe_history.append((curr_x, curr_y, time.time()))
        if len(self.swipe_history) >= 4:
            dx = self.swipe_history[-1][0] - self.swipe_history[0][0]
            dy = self.swipe_history[-1][1] - self.swipe_history[0][1]
            dt = max(self.swipe_history[-1][2] - self.swipe_history[0][2], 0.001)
            vx = abs(dx) / dt
            if abs(dx) > 0.16 and abs(dx) > 1.6 * abs(dy) and vx > 0.6:
                self.swipe_history.clear()
                return "[SIDE_SWIPE]", None

        # 2. Fin de Bloque: Puño cerrado orientado al frente [BLOCK_END]
        if ext_count == 0:
            tips_to_wrist = [
                np.linalg.norm(lms[idx] - lms[WRIST])
                for idx in (INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)
            ]
            if max(tips_to_wrist) < 1.25 * ps:
                return "[BLOCK_END]", None

        # Distancias clave para interacción pulgar-índice
        d_thumb_idx = np.linalg.norm(lms[THUMB_TIP] - lms[INDEX_TIP])
        d_thumb_mid = np.linalg.norm(lms[THUMB_TIP] - lms[MIDDLE_TIP])
        d_idx_wrist = np.linalg.norm(lms[INDEX_TIP] - lms[WRIST])

        # 3. Círculo: Forma de 'O' con índice y pulgar [DOT_CIRCLE] (OK sign)
        # Índice y pulgar se tocan, y al menos 2 dedos restantes bien extendidos
        other_extended_count = sum([mid_ext, ring_ext, pinky_ext])
        if d_thumb_idx < 0.40 * ps and other_extended_count >= 2:
            return "[DOT_CIRCLE]", None

        # 4. Asignación: Pellizco (pinch) [OP_ASSIGN]
        # Yemas de pulgar e índice juntas hacia el frente, con dedos restantes plegados
        if d_thumb_idx < 0.38 * ps and other_extended_count <= 1:
            return "[OP_ASSIGN]", None

        # 5. Agrupar / Polígono: Marco 'L' unimanual [FRAME_SHAPE]
        if idx_ext and thumb_ext and not mid_ext and not ring_ext and not pinky_ext:
            v_thumb = lms[THUMB_TIP] - lms[THUMB_MCP]
            v_idx = lms[INDEX_TIP] - lms[INDEX_MCP]
            cos_th_idx = np.dot(v_thumb, v_idx) / (np.linalg.norm(v_thumb) * np.linalg.norm(v_idx) + 1e-7)
            angle_deg = np.degrees(np.arccos(np.clip(cos_th_idx, -1.0, 1.0)))
            if 55.0 <= angle_deg <= 125.0:
                return "[FRAME_SHAPE]", None

        # 6. Vértice / Punto: Dedo índice extendido, demás flexionados [INDEX_EXTENDED]
        if idx_ext and not mid_ext and not ring_ext and not pinky_ext and not thumb_ext:
            return "[INDEX_EXTENDED]", None

        # 7. Inicio de Bloque: Palma plana extendida hacia el frente [BLOCK_START]
        # 5 dedos extendidos apuntando hacia arriba/frente
        if ext_count == 5:
            # Si las puntas de los dedos están claramente por encima de los MCPs (mano abierta vertical)
            fingers_upward = (
                lms[INDEX_TIP, 1] < lms[INDEX_MCP, 1] and
                lms[MIDDLE_TIP, 1] < lms[MIDDLE_MCP, 1] and
                lms[RING_TIP, 1] < lms[RING_MCP, 1]
            )
            if fingers_upward:
                return "[BLOCK_START]", None

        # 8. Modificadores de Orientación: [PALM_UP] y [PALM_DOWN]
        # Evalúa el vector normal de la palma en el eje Y cuando la mano tiene al menos 3 dedos extendidos
        if ext_count >= 3:
            normal_y = right_hand.palm_normal[1]
            # Palma hacia arriba (Y negativo)
            if normal_y < -0.42:
                return "[PALM_UP]", None
            # Palma hacia abajo (Y positivo)
            elif normal_y > 0.42:
                return "[PALM_DOWN]", None

        # 9. Delimitadores de Expresión: Mano en 'C' ([C_SHAPE_LEFT] y [C_SHAPE_RIGHT])
        # Curvatura explícita: ni el pulgar ni los demás dedos están completamente estirados
        # (ext_count == 0 porque los dedos están arqueados formando una media luna/C)
        if ext_count == 0 and not thumb_ext and not idx_ext:
            if 0.50 * ps < d_thumb_idx < 1.35 * ps:
                c_mid_x = (lms[THUMB_TIP, 0] + lms[INDEX_TIP, 0]) / 2.0
                wrist_x = lms[WRIST, 0]
                if c_mid_x < wrist_x - 0.06 * ps:
                    return "[C_SHAPE_LEFT]", None
                elif c_mid_x > wrist_x + 0.06 * ps:
                    return "[C_SHAPE_RIGHT]", None

        # 10. Dígitos 1 al 5 en mano dominante (Reconocimiento Natural y Robusto)
        # Si ext_count está entre 1 y 5, asignamos directamente el número según la cantidad de dedos extendidos.
        if 1 <= ext_count <= 5:
            # Caso 1 dedo: si solo el pulgar está extendido -> [NUM_1]
            # (si solo el índice estaba extendido ya fue capturado arriba como [INDEX_EXTENDED])
            if ext_count == 1:
                return "[NUM_1]", 1

            # Caso 2 dedos: cualquier combinación de 2 dedos (ej. índice+medio, o pulgar+índice no perpendicular)
            elif ext_count == 2:
                return "[NUM_2]", 2

            # Caso 3 dedos: reconoce tanto (índice+medio+anular) como (pulgar+índice+medio)
            elif ext_count == 3:
                return "[NUM_3]", 3

            # Caso 4 dedos: 4 dedos extendidos cualquiera sea la variación
            elif ext_count == 4:
                return "[NUM_4]", 4

            # Caso 5 dedos: los 5 dedos extendidos como valor 5
            elif ext_count == 5:
                return "[NUM_5]", 5

        return "[REST_STATE]", None

    def update_trajectory_gestures(self, right_hand: Optional[DetectedHand]) -> Optional[str]:
        """
        Analiza el historial de la trayectoria de la punta del índice para detectar:
        - [ZIG_ZAG_MOTION]: Oscilaciones horizontales repetidas en X.
        - [LOOP_CIRCULAR]: Giro circular continuo en el plano.
        """
        if right_hand is None:
            self.trajectory.clear()
            self.timestamps.clear()
            return None

        # Registrar la posición de la punta del índice
        idx_tip = right_hand.norm_landmarks[INDEX_TIP]
        now = time.time()
        self.trajectory.append((idx_tip[0], idx_tip[1]))
        self.timestamps.append(now)

        if len(self.trajectory) < 14:
            return None

        pts = np.array(self.trajectory)
        xs = pts[:, 0]
        ys = pts[:, 1]

        # 1. Detección de Zig-Zag en eje X
        # Suavizar levemente X
        kernel = np.array([0.25, 0.5, 0.25])
        smooth_x = np.convolve(xs, kernel, mode="valid")
        dx = np.diff(smooth_x)
        # Filtrar micro-ruido
        dx_filtered = np.where(np.abs(dx) > 0.004, dx, 0.0)
        signs = np.sign(dx_filtered)
        nonzero_signs = signs[signs != 0]

        if len(nonzero_signs) >= 3:
            sign_changes = np.sum(np.diff(nonzero_signs) != 0)
            total_x_span = np.max(xs) - np.min(xs)
            if sign_changes >= 2 and total_x_span > 0.10:
                self.trajectory.clear()
                return "[ZIG_ZAG_MOTION]"

        # 2. Detección de Bucle Circular [LOOP_CIRCULAR]
        centroid_x = np.mean(xs)
        centroid_y = np.mean(ys)
        radii = np.hypot(xs - centroid_x, ys - centroid_y)
        mean_radius = np.mean(radii)

        if mean_radius > 0.035 and (np.max(radii) - np.min(radii)) < 0.14:
            # Calcular ángulo acumulado respecto al centroide
            angles = np.arctan2(ys - centroid_y, xs - centroid_x)
            dtheta = np.diff(angles)
            # Desenrollar ángulo (-pi a pi)
            dtheta = (dtheta + np.pi) % (2.0 * np.pi) - np.pi
            cumulative_angle = np.sum(dtheta)

            if abs(cumulative_angle) >= 1.50 * np.pi:  # ~ 270° a 360°
                self.trajectory.clear()
                return "[LOOP_CIRCULAR]"

        return None


# =============================================================================
# FLUJO DE SALIDA Y ENSAMBLADOR DE TOKENS
# =============================================================================
class TokenStreamEmitter:
    """
    Gestiona la emisión limpia de tokens y líneas de instrucción a sys.stdout.
    Mantiene la historia de tokens para visualización en el HUD interactivo.
    """
    def __init__(self):
        self.current_instruction_tokens: List[str] = []
        self.history_instructions: deque = deque(maxlen=4)

    def emit_token(self, token: str):
        """Emite un token individual a la salida estándar y lo agrega a la instrucción activa."""
        if not token or token == "[REST_STATE]":
            return

        self.current_instruction_tokens.append(token)
        # Imprimir token con espacio directo a stdout con flush=True
        sys.stdout.write(f"{token} ")
        sys.stdout.flush()

        if token == "[DELIM_END]":
            # Fin de la instrucción actual: emitir salto de línea limpio
            sys.stdout.write("\n")
            sys.stdout.flush()
            instruction_line = " ".join(self.current_instruction_tokens)
            self.history_instructions.append(instruction_line)
            self.current_instruction_tokens.clear()

    def get_current_instruction_str(self) -> str:
        if not self.current_instruction_tokens:
            return "Esperando gestos..."
        return " ".join(self.current_instruction_tokens)


# =============================================================================
# INTERFAZ GRÁFICA Y VISUALIZADOR DE ALTA ESTÉTICA
# =============================================================================
class ModernVisualizer:
    """
    Renderiza la ventana interactiva de OpenCV con estética moderna:
    - Cuadrícula espacial de 6 zonas con realimentación visual translúcida.
    - Landmarks trazados con estética limpia (verde esmeralda / dorado).
    - Rastro luminoso de trayectoria para el dedo índice.
    - Barra HUD superior moderna con instrucción actual, gesto y buffer de dígitos.
    - Barra inferior de estado con FPS y atajos de teclado.
    """
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.fps_queue: deque = deque(maxlen=20)
        self.last_time = time.time()

    def update_fps(self) -> float:
        now = time.time()
        dt = max(now - self.last_time, 0.001)
        self.last_time = now
        self.fps_queue.append(1.0 / dt)
        return float(np.mean(self.fps_queue))

    def draw_quadrants(
        self,
        frame: np.ndarray,
        quad_manager: QuadrantManager,
        active_pos: Optional[Tuple[int, int]]
    ):
        """Dibuja las líneas divisorias tenues y etiquetas de cada cuadrante (2x3)."""
        h, w, _ = frame.shape
        x1 = w // 3
        x2 = 2 * (w // 3)
        y_mid = h // 2

        # Capa translúcida para cuadrícula y resaltado
        overlay = frame.copy()

        # Resaltar cuadrante activo
        if active_pos is not None:
            r, c = active_pos
            qx_start = 0 if c == 0 else (x1 if c == 1 else x2)
            qx_end = x1 if c == 0 else (x2 if c == 1 else w)
            qy_start = 0 if r == 0 else y_mid
            qy_end = y_mid if r == 0 else h

            # Relleno cian/esmeralda suave
            cv2.rectangle(overlay, (qx_start, qy_start), (qx_end, qy_end), (40, 180, 120), -1)

        # Mezclar capa
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

        # Líneas divisorias tenues
        grid_color = (180, 180, 180)
        cv2.line(frame, (x1, 0), (x1, h), grid_color, 1, cv2.LINE_AA)
        cv2.line(frame, (x2, 0), (x2, h), grid_color, 1, cv2.LINE_AA)
        cv2.line(frame, (0, y_mid), (w, y_mid), grid_color, 1, cv2.LINE_AA)

        # Etiquetas de cuadrantes
        labels = [
            ((0, 0), "[ID_QUAD_1]", (20, 110)),
            ((0, 1), "[ID_QUAD_2]", (x1 + 20, 110)),
            ((0, 2), "[ID_QUAD_3]", (x2 + 20, 110)),
            ((1, 0), "[ID_QUAD_4]", (20, y_mid + 40)),
            ((1, 1), "[ID_QUAD_5]", (x1 + 20, y_mid + 40)),
            ((1, 2), "[ID_QUAD_6]", (x2 + 20, y_mid + 40)),
        ]

        for pos, text, coords in labels:
            is_active = (active_pos == pos)
            color = (50, 255, 180) if is_active else (140, 160, 170)
            thickness = 2 if is_active else 1
            cv2.putText(frame, text, coords, self.font, 0.55, color, thickness, cv2.LINE_AA)

    def draw_hand_skeleton(self, frame: np.ndarray, hands: List[DetectedHand]):
        """Dibuja landmarks y conexiones con estética visual diferenciada para cada mano."""
        for hand in hands:
            pts = hand.pixel_landmarks
            is_left = (hand.label == "Left")

            # Izquierda (Navegación): Esmeralda | Derecha (Acciones): Dorado brillante
            bone_color = (220, 160, 40) if not is_left else (60, 200, 140)
            joint_color = (255, 230, 120) if not is_left else (120, 255, 200)

            # Dibujar conexiones óseas
            for p1_idx, p2_idx in HAND_CONNECTIONS:
                p1 = tuple(pts[p1_idx])
                p2 = tuple(pts[p2_idx])
                cv2.line(frame, p1, p2, bone_color, 2, cv2.LINE_AA)

            # Dibujar articulaciones
            for idx, pt in enumerate(pts):
                radius = 5 if idx in (INDEX_TIP, THUMB_TIP, WRIST) else 3
                cv2.circle(frame, tuple(pt), radius, joint_color, -1, cv2.LINE_AA)
                cv2.circle(frame, tuple(pt), radius + 1, (20, 20, 20), 1, cv2.LINE_AA)

            # Etiqueta de la mano
            wrist_pt = pts[WRIST]
            tag = "Mano Izq (Nav)" if is_left else "Mano Der (Accion)"
            tag_color = (60, 240, 160) if is_left else (240, 180, 50)
            cv2.putText(frame, tag, (wrist_pt[0] - 40, wrist_pt[1] + 25), self.font, 0.45, tag_color, 1, cv2.LINE_AA)

    def draw_motion_trail(self, frame: np.ndarray, trajectory: deque):
        """Dibuja un rastro de luz cian degradado para la trayectoria del índice."""
        if len(trajectory) < 2:
            return

        h, w, _ = frame.shape
        n_pts = len(trajectory)

        for i in range(1, n_pts):
            p1_norm = trajectory[i - 1]
            p2_norm = trajectory[i]
            pt1 = (int(p1_norm[0] * w), int(p1_norm[1] * h))
            pt2 = (int(p2_norm[0] * w), int(p2_norm[1] * h))

            alpha = i / float(n_pts)
            thickness = max(1, int(alpha * 4))
            color = (int(255 * alpha), int(200 * alpha), int(40 * (1 - alpha)))
            cv2.line(frame, pt1, pt2, color, thickness, cv2.LINE_AA)

    def draw_hud(
        self,
        frame: np.ndarray,
        instruction_str: str,
        active_gesture: str,
        debounce_progress: float,
        buffer_preview: str,
        fps: float
    ):
        """Dibuja el banner HUD superior y la barra de información con diseño moderno."""
        h, w, _ = frame.shape
        hud_h = 80

        # Franja superior translúcida oscura
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_h), (18, 22, 28), -1)
        # Franja inferior para controles y estado
        cv2.rectangle(overlay, (0, h - 30), (w, h), (18, 22, 28), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Línea divisoria de acento cian
        cv2.line(frame, (0, hud_h), (w, hud_h), (60, 180, 240), 2, cv2.LINE_AA)

        # Título y FPS
        cv2.putText(frame, "VAGO VISION DETECTOR", (18, 26), self.font, 0.58, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"FPS: {fps:.1f}", (w - 110, 26), self.font, 0.50, (140, 220, 160), 1, cv2.LINE_AA)

        # Línea de Instrucción Activa
        inst_label = f"Instruccion: {instruction_str}"
        cv2.putText(frame, inst_label, (18, 54), self.font, 0.55, (80, 230, 255), 2, cv2.LINE_AA)

        # Gesto Activo y Barra de Estabilidad (Anti-rebote)
        gesture_text = f"Gesto: {active_gesture}"
        cv2.putText(frame, gesture_text, (w - 380, 54), self.font, 0.52, (255, 210, 80), 1, cv2.LINE_AA)

        # Barra de progreso anti-rebote
        bar_w = 80
        bar_x = w - 120
        bar_y = 44
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 12), (50, 60, 70), -1)
        fill_w = int(bar_w * np.clip(debounce_progress, 0.0, 1.0))
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + 12), (60, 240, 140), -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 12), (180, 190, 200), 1)

        # Buffer Numérico Multidígitos
        if buffer_preview:
            buf_tag = f"Buffer: [{buffer_preview}]"
            cv2.putText(frame, buf_tag, (18, 73), self.font, 0.40, (255, 140, 80), 1, cv2.LINE_AA)

        # Barra inferior de controles
        controls_text = "[Q] Salir  |  [C] Limpiar Instruccion  |  [M] Modo Espejo  |  Mano Izq: Cuadrante  |  Mano Der: Accion"
        cv2.putText(frame, controls_text, (18, h - 10), self.font, 0.42, (180, 190, 200), 1, cv2.LINE_AA)


# =============================================================================
# BUCLE PRINCIPAL DE EJECUCIÓN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="VAGO - Detector de Gestos y Generador de Tokens en Tiempo Real")
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara web (default: 0)")
    parser.add_argument("--video", type=str, default=None, help="Ruta a archivo de video para análisis offline")
    parser.add_argument("--width", type=int, default=1280, help="Ancho de captura de video (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Alto de captura de video (default: 720)")
    parser.add_argument("--mirror", action="store_true", default=True, help="Activar modo espejo para cámara web (default: True)")
    parser.add_argument("--no-mirror", dest="mirror", action="store_false", help="Desactivar modo espejo")
    parser.add_argument("--headless", action="store_true", default=False, help="Ejecutar sin ventana interactiva OpenCV (útil en servidores/CI)")
    parser.add_argument("--debounce", type=int, default=4, help="Número de fotogramas mínimos para anti-rebote (default: 4)")
    args = parser.parse_args()

    # Inicializar captura de video
    video_source = args.video if args.video is not None else args.camera
    cap = cv2.VideoCapture(video_source)

    if not cap.isOpened():
        sys.stderr.write(f"[ERROR] No se pudo abrir la fuente de video: {video_source}\n")
        sys.stderr.flush()
        sys.exit(1)

    if args.video is None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    # Inicializar componentes modulares del sistema
    tracker = HandTracker(max_hands=2, min_detection_conf=0.55, min_track_conf=0.55)
    quad_manager = QuadrantManager(debounce_frames=args.debounce)
    classifier = GestureClassifier(trajectory_len=26)
    multidigit_buffer = MultidigitBuffer(timeout_sec=1.0)
    token_emitter = TokenStreamEmitter()
    visualizer = ModernVisualizer()

    # Variables de control del bucle
    debounce_frames = args.debounce
    candidate_gesture = "[REST_STATE]"
    gesture_counter = 0
    active_stable_gesture = "[REST_STATE]"
    last_emitted_token = ""
    is_mirrored = args.mirror

    window_name = "VAGO - Modulo de Vision en Tiempo Real"
    if not args.headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, args.width, args.height)

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                # Si es un archivo de video y llegó al final, salir
                if args.video is not None:
                    break
                continue

            # Inversión horizontal para modo espejo (comportamiento natural de webcam)
            if is_mirrored:
                frame = cv2.flip(frame, 1)

            # Conversión BGR a RGB para MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            detected_hands = tracker.process(rgb_frame, is_mirrored=is_mirrored)

            # Separar mano izquierda (No dominante) y derecha (Dominante)
            left_hand: Optional[DetectedHand] = None
            right_hand: Optional[DetectedHand] = None

            for hand in detected_hands:
                if hand.label == "Left" and left_hand is None:
                    left_hand = hand
                elif hand.label == "Right" and right_hand is None:
                    right_hand = hand

            # Si sólo hay una mano detectada pero está en el lado izquierdo del feed, clasificarla según contexto
            if len(detected_hands) == 1:
                single_hand = detected_hands[0]
                # Si la mano está claramente en el lado izquierdo y apuntando, verificar si es de navegación
                if single_hand.norm_landmarks[INDEX_TIP, 0] < 0.45 and single_hand.label == "Left":
                    left_hand = single_hand
                else:
                    right_hand = single_hand

            # -------------------------------------------------------------
            # 1. ACTUALIZAR CUADRANTE ESPACIAL (Mano No Dominante - Izquierda)
            # -------------------------------------------------------------
            new_quad_token = quad_manager.update(left_hand)
            if new_quad_token:
                # Si hay dígitos pendientes en el buffer multidígitos, vaciarlos antes del cuadrante
                flushed_num = multidigit_buffer.flush()
                if flushed_num:
                    token_emitter.emit_token(flushed_num)
                token_emitter.emit_token(new_quad_token)

            # -------------------------------------------------------------
            # 2. EVALUAR BUFFER MULTIDÍGITOS POR TIMEOUT
            # -------------------------------------------------------------
            flushed_num = multidigit_buffer.check_timeout()
            if flushed_num:
                token_emitter.emit_token(flushed_num)

            # -------------------------------------------------------------
            # 3. EVALUAR GESTOS DINÁMICOS DE TRAYECTORIA ([ZIG_ZAG_MOTION], [LOOP_CIRCULAR])
            # -------------------------------------------------------------
            dyn_token = classifier.update_trajectory_gestures(right_hand)
            if dyn_token:
                flushed_num = multidigit_buffer.flush()
                if flushed_num:
                    token_emitter.emit_token(flushed_num)
                token_emitter.emit_token(dyn_token)
                candidate_gesture = dyn_token
                gesture_counter = debounce_frames
                active_stable_gesture = dyn_token
            else:
                # ---------------------------------------------------------
                # 4. EVALUAR GESTOS ESTÁTICOS / CINEMÁTICOS DE ACCIÓN
                # ---------------------------------------------------------
                detected_gesture, detected_num = classifier.classify_static_and_kinematic(right_hand, left_hand)

                # Máquina de estados anti-rebote (debounce)
                if detected_gesture == candidate_gesture:
                    gesture_counter += 1
                else:
                    candidate_gesture = detected_gesture
                    gesture_counter = 1

                if gesture_counter >= debounce_frames:
                    if candidate_gesture != active_stable_gesture:
                        active_stable_gesture = candidate_gesture

                        if active_stable_gesture == "[REST_STATE]":
                            multidigit_buffer.enter_rest()
                            last_emitted_token = ""
                        elif active_stable_gesture == "[DELIM_END]":
                            flushed_num = multidigit_buffer.flush()
                            if flushed_num:
                                token_emitter.emit_token(flushed_num)
                            token_emitter.emit_token("[DELIM_END]")
                            last_emitted_token = "[DELIM_END]"
                        elif detected_num is not None:
                            # Dígito detectado: encolar en el buffer multidígitos
                            multidigit_buffer.push_digit(detected_num)
                            last_emitted_token = f"[NUM_{detected_num}]"
                        else:
                            # Token de acción no numérico
                            flushed_num = multidigit_buffer.flush()
                            if flushed_num:
                                token_emitter.emit_token(flushed_num)

                            if active_stable_gesture != last_emitted_token:
                                token_emitter.emit_token(active_stable_gesture)
                                last_emitted_token = active_stable_gesture

            # -------------------------------------------------------------
            # 5. RENDERIZADO VISUAL EN LA VENTANA DE OPENCV
            # -------------------------------------------------------------
            if not args.headless:
                fps = visualizer.update_fps()
                progress = min(1.0, gesture_counter / float(debounce_frames))

                # Dibujar cuadrícula de cuadrantes y resaltado
                visualizer.draw_quadrants(frame, quad_manager, quad_manager.active_grid_pos)
                # Dibujar rastro luminoso de trayectoria
                visualizer.draw_motion_trail(frame, classifier.trajectory)
                # Dibujar esqueleto de manos y articulaciones
                visualizer.draw_hand_skeleton(frame, detected_hands)
                # Dibujar HUD superior e inferior
                visualizer.draw_hud(
                    frame=frame,
                    instruction_str=token_emitter.get_current_instruction_str(),
                    active_gesture=active_stable_gesture,
                    debounce_progress=progress,
                    buffer_preview=multidigit_buffer.get_preview(),
                    fps=fps
                )

                cv2.imshow(window_name, frame)

                # Manejo de atajos de teclado
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # 'q' o ESC para salir
                    break
                elif key == ord('c') or key == ord('C'):
                    # Limpiar instrucción actual
                    token_emitter.current_instruction_tokens.clear()
                    multidigit_buffer.digits.clear()
                elif key == ord('m') or key == ord('M'):
                    # Alternar modo espejo
                    is_mirrored = not is_mirrored

    except KeyboardInterrupt:
        pass
    finally:
        # Limpieza ordenada de recursos
        cap.release()
        tracker.close()
        if not args.headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
