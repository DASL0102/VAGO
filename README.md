# VAGO — Analizador léxico

**Primera entrega de Compiladores**
**Proyecto:** *Visual Actions to Geometric Output (VAGO)*
**Tecnología:** C++17, CMake/CTest y biblioteca **DeSiGNAR 4.0.0**

## 1. Descripción y alcance

VAGO es un lenguaje de dominio específico que representa instrucciones geométricas mediante **etiquetas simbólicas de gestos**. El objetivo del módulo actual es convertir una secuencia de estas etiquetas en tokens que puedan utilizarse en las siguientes fases del compilador.

Por ejemplo, la entrada:

```text
[ID_QUAD_1] [REST_STATE] [ZIG_ZAG_MOTION] [ID_QUAD_2] [NUM_3] [DELIM_END]
```

produce, sin incluir el gesto de reposo:

```text
TK_ID      | [ID_QUAD_1]      | 0
TK_KW_LINE | [ZIG_ZAG_MOTION] | 25
TK_ID      | [ID_QUAD_2]      | 42
TK_NUM     | [NUM_3]         | 54
TK_DELIM   | [DELIM_END]     | 62
```

Cada token conserva su **nombre**, **lexema original** y **posición inicial** (desplazamiento en bytes desde el principio de la cadena de entrada).

**Alcance de esta entrega:** reconocimiento léxico, reclasificación de palabras reservadas, descarte de espacios/pausas/comentarios, detección de errores léxicos y pruebas automatizadas. **No** se incluyen el analizador sintáctico, la tabla de símbolos semántica, la traducción a QML ni la captura de cámara con MediaPipe.

## 2. Organización del módulo

La estructura del componente C++ se mantiene separada del módulo de visión escrito en Python:

```text
lexer/
├── CMakeLists.txt
├── CMakePresets.json
├── CMakeUserPresets.json
├── vcpkg.json
├── include/
│   └── vago/
│       └── lexer.hpp
├── src/
│   ├── lexer.cpp
│   └── main.cpp
├── tests/
│   └── lexer_tests.cpp
├── examples/
│   ├── line.vago
│   ├── polygon.vago
│   ├── full_example2.vago
│   ├── full_example3.vago
│   └── semantic_error_example4.vago
README.md
```

Los ejemplos `line.vago` y `polygon.vago` provienen de pruebas anteriores. Los otros tres se suministran con el suit de pruebas. Los directorios de compilación (`build/`) no forman parte del código fuente.

## 3. Uso de DeSiGNAR

El reconocimiento léxico **no se implementa mediante un escáner propio**. Se utiliza la biblioteca exigida por la asignatura:

- `Designar::Lexer`: registra expresiones regulares mediante `add_token()` y reconoce lexemas con `tokenize()`. Internamente utiliza autómatas finitos (AFN/AFD), selecciona la coincidencia más larga y resuelve empates según el orden de registro.
- `Designar::Token`: conserva `name`, `lexeme` y `position`.
- `Designar::HashMap`: reclasifica etiquetas genéricas (`TK_SYMBOL`) como palabras reservadas o identificadores de cuadrante.
- `Designar::DynArray<Designar::Token>`: contiene la secuencia de tokens resultante.

`vago::VagoLexer` **coordina** estos elementos, pero no reemplaza ninguna de sus implementaciones. Configura las reglas y la tabla hash una vez por instancia. También se mantiene la función `vago::tokenize()` como interfaz de conveniencia.

El flujo general es:

```text
Etiquetas de gestos
       |
       v
Designar::Lexer (expresiones regulares / AFD)
       |
       v
Reclasificación con Designar::HashMap
       |
       v
Filtrado de reposo, espacios y comentarios
       |
       v
DynArray<Designar::Token>
```

## 4. Reglas léxicas y decisiones aplicadas

Se preserva el vocabulario de la entrega realiza anteriormente (Grupo2_Semana7_Compiladores) y se adaptan las expresiones regulares a la sintaxis admitida por DeSiGNAR. En particular, se sustituyeron las clases `[A-Z]` y `[0-9]` por alternativas explícitas porque el motor no admite directamente esas clases ni la expresión no codiciosa `.*?`.

| Categoría | Ejemplos de lexemas | Tokens |
|---|---|---|
| Identificadores espaciales | `[ID_QUAD_1]` … `[ID_QUAD_6]` | `TK_ID` |
| Palabras reservadas | `[LOOP_CIRCULAR]`, `[FRAME_SHAPE]`, `[DOT_CIRCLE]` | `TK_KW_WHILE`, `TK_KW_GROUP`, `TK_KW_CIRCLE` (y las demás definidas en la tabla) |
| Constantes numéricas | `[NUM_3]`, `[NUM_45]` | `TK_NUM` |
| Caracteres | `[FINGER_SPELL_R]` | `TK_CHAR` |
| Cadenas | `[QUOTE][FINGER_SPELL_H][FINGER_SPELL_I][QUOTE]` | `TK_STRING` |
| Operadores | `[OP_ASSIGN]`, `[OP_MATH_ADD]`, `[POINT_LEFT_EQ]`, `[OP_LOGIC_AND]` | `TK_OP_ASSIGN`, `TK_OP_MATH`, `TK_OP_LESS_EQ`, `TK_OP_AND` |
| Delimitadores | `[DELIM_END]`, `[BLOCK_START]`, `[C_SHAPE_LEFT]`, `[SIDE_SWIPE]` | `TK_DELIM`, `TK_BLOCK_START`, `TK_PAREN_OPEN`, `TK_COMMA` |
| Fin explícito | `[EOF]`, `[REST_STATE_FINAL]` | `TK_EOF` |

**Palabras reservadas.** Los gestos de acción, control y modificadores se reconocen inicialmente mediante `TK_SYMBOL` y se reclasifican con `Designar::HashMap`. Si la etiqueta tiene formato válido pero no existe en el vocabulario, se informa un error léxico.

**Cadenas.** Una cadena contiene al menos un gesto `[FINGER_SPELL_A]` … `[FINGER_SPELL_Z]` entre dos `[QUOTE]`. Entre las letras se admiten espacios de entrada y `[REST_STATE]`. El token resultante mantiene la secuencia simbólica; **todavía no se decodifica** a texto legible. Ejemplo válido: `[QUOTE][FINGER_SPELL_H][FINGER_SPELL_I][QUOTE]`. La forma `[QUOTE]HI[QUOTE]` no está admitida.

**Comentarios.** Se ignora el contenido entre `[CROSS_ARMS]` y `[UNCROSS]`. Se detectan comentarios anidados, comentarios sin cierre y cierres sueltos. Los marcadores internos no se entregan al analizador sintáctico. Solo pueden contener caracteres que el lexer de DeSiGNAR pueda reconocer; por ejemplo, `@hello` provoca un error incluso dentro de un comentario.

**Tres conceptos distintos de finalización:**

| Evento | Tratamiento actual |
|---|---|
| `[DELIM_END]` | Finaliza una instrucción; genera `TK_DELIM` |
| `[REST_STATE]` | Pausa ordinaria; se ignora |
| `[EOF]` o `[REST_STATE_FINAL]` | Final explícito de programa; genera `TK_EOF` |
| Fin físico del archivo/cadena | Termina la lectura, **sin crear automáticamente** `TK_EOF` |

Actualmente el lexer **no rechaza** por sí mismo los tokens que aparezcan después de `TK_EOF`: esa validación corresponderá a una etapa posterior de control de entrada o análisis sintáctico.

## 5. Requisitos y compilación

- Compilador compatible con **C++17**.
- CMake 3.28 o posterior.
- Biblioteca **DeSiGNAR 4.0.0** compilada e instalada para la arquitectura y compilador correspondientes.
- El módulo incorpora **CTest**, incluido con CMake, para las pruebas automatizadas. No se requiere un framework de pruebas adicional.

### Ejemplo en Windows con MSVC x64

Abrir un terminal de desarrollo y situarse dentro de `lexer/`:

```cmd
cmake --preset cl -DCMAKE_PREFIX_PATH="C:/path/to/installed_designar"
cmake --build --preset cl-release
ctest --test-dir build/cl -C Release --output-on-failure
```

Para analizar archivos de ejemplo:

```cmd
.\build\cl\Release\vago_lexer.exe .\examples\line.vago
.\build\cl\Release\vago_lexer.exe .\examples\full_example2.vago
.\build\cl\Release\vago_lexer.exe .\examples\semantic_error_example4.vago
```

La ruta de instalación de DeSiGNAR es un **ejemplo local**, no un requisito del repositorio: debe sustituirse si la biblioteca está instalada en otra ubicación.

**Nota sobre Debug/Release en Windows:** la instalación local disponible de DeSiGNAR fue compilada con el runtime Release (`/MD`). Por ello se utiliza `cl-release`. Para compilar VAGO con un runtime Debug (`/MDd`) es necesario disponer de una variante compatible de DeSiGNAR; la configuración incorrecta produce el error de enlazado `LNK2038`.

## 6. Pruebas automatizadas

El proyecto registra **28 casos de CTest**: Comprueban nombre del token, lexema, posición, errores esperados y reutilización de una instancia de `VagoLexer`.

| Grupo | Pruebas importantes |
|---|---|
| Vocabulario | `line`, `polygon`, `keywords`, `operators`, `char` |
| Finalización | `eof_explicit`, `eof_final_rest`, `eof_natural`, `after_eof` |
| Cadenas y comentarios | `string_simple`, `string_pauses`, `comment`, `repeated_lexemes` |
| Errores | `error_unknown`, `error_raw_text`, `error_quote`, `error_comment_nested`, `unknown_quad_7` y otras |
| Casos de la propuesta | `example2_full`, `example3_full`, `example4_full` |
| Casos límite | `empty_input`, `spaces_only`, `leading_zero_number`, `reused_instance` |

El **Ejemplo 3** valida el reconocimiento de asignaciones, condicionales, bucles, comparaciones, bloques anidados y EOF. El **Ejemplo 4** debe aprobar el análisis léxico, aunque su uso de un círculo como vértice sea **semánticamente inválido**. Esta diferencia es intencional y demuestra la separación entre fases del compilador.

**Estado de verificación:** los 28 casos pasaron en una compilación independiente con **GCC/C++17 y el código fuente de DeSiGNAR proporcionado**. 

## 7. Limitaciones conocidas y trabajo futuro

- El lexer recibe **etiquetas de texto**, no imágenes ni eventos directos de MediaPipe. La etapa de visión generará posteriormente los símbolos y, cuando sea necesario, metadatos espaciales.
- Los valores numéricos aceptan de momento `0`, ceros iniciales y cantidades extensas. Validar rangos y usos geométricos es una tarea posterior.
- No se aceptan texto libre (`@hello`), literales como `[QUOTE]HELLO[QUOTE]`, cadenas vacías ni espacios semánticos dentro de los nombres.
- Los archivos `.vago` deberían guardarse como **UTF-8 sin BOM** o ASCII compatible con los lexemas definidos. No se ha implementado normalización del BOM.
- Los errores léxicos existentes funcionan, pero aún pueden unificarse en un formato estructurado común.
- La verificación del fin de programa y los errores **sintácticos o semánticos** no están implementados en este módulo.
- La tabla de tipos geométricos, la generación QML y la integración de cámara se consideran etapas posteriores.

Las decisiones e inconsistencias adicionales de VAGO (memoria por cuadrantes, selección de vértices, propiedad geométrica, comparaciones y terminación de bucles) se documentan en el registro de diseño del proyecto y **no se resuelven artificialmente dentro del lexer**.

## 8. Referencia de la especificación

El desarrollo se basa en la propuesta *Visual Actions to Geometric Output (VAGO)*, **Grupo 2, Semana 7 — Compiladores**, Universidad de Los Andes (octubre de 2026): sección 3 (reglas léxicas), tabla de palabras reservadas y los cuatro ejemplos de las páginas 12 a 19. Las diferencias de representación respecto a las expresiones regulares originales se explicitan en este README.
