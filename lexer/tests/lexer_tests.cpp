#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <vago/lexer.hpp>

struct ExpectedToken {
    std::string name;
    std::string lexeme;
    std::size_t position;
};

struct TestCase {
    std::string name;
    std::string input;
    std::vector<ExpectedToken> expected;
    std::string expected_error;
};

const std::vector<TestCase> cases = {
    // line
    {
        "line",
        "[ID_QUAD_1] [REST_STATE] [ZIG_ZAG_MOTION] [ID_QUAD_2] [NUM_3] [DELIM_END]",
        {
            {"TK_ID", "[ID_QUAD_1]", 0},
            {"TK_KW_LINE", "[ZIG_ZAG_MOTION]", 25},
            {"TK_ID", "[ID_QUAD_2]", 42},
            {"TK_NUM", "[NUM_3]", 54},
            {"TK_DELIM", "[DELIM_END]", 62},
        },
        ""
    },
    // polygon
    {
        "polygon",
        "[ID_QUAD_1] [OP_ASSIGN] [FRAME_SHAPE] [C_SHAPE_LEFT] [NUM_5] [SIDE_SWIPE] [NUM_40] [C_SHAPE_RIGHT] [DELIM_END]",
        {
            {"TK_ID", "[ID_QUAD_1]", 0},
            {"TK_OP_ASSIGN", "[OP_ASSIGN]", 12},
            {"TK_KW_GROUP", "[FRAME_SHAPE]", 24},
            {"TK_PAREN_OPEN", "[C_SHAPE_LEFT]", 38},
            {"TK_NUM", "[NUM_5]", 53},
            {"TK_COMMA", "[SIDE_SWIPE]", 61},
            {"TK_NUM", "[NUM_40]", 74},
            {"TK_PAREN_CLOSE", "[C_SHAPE_RIGHT]", 83},
            {"TK_DELIM", "[DELIM_END]", 99},
        },
        ""
    },
    // operators
    {
        "operators",
        "[OP_MATH_ADD] [OP_MATH_SUB] [OP_REL_EQ] [OP_REL_NEQ] [POINT_LEFT_EQ] [POINT_RIGHT_EQ] [POINT_LEFT] "
        "[POINT_RIGHT] [OP_LOGIC_AND] [OP_LOGIC_OR] [BLOCK_START] [BLOCK_END]",
        {
            {"TK_OP_MATH", "[OP_MATH_ADD]", 0},
            {"TK_OP_MATH", "[OP_MATH_SUB]", 14},
            {"TK_OP_REL", "[OP_REL_EQ]", 28},
            {"TK_OP_REL", "[OP_REL_NEQ]", 40},
            {"TK_OP_LESS_EQ", "[POINT_LEFT_EQ]", 53},
            {"TK_OP_GREATER_EQ", "[POINT_RIGHT_EQ]", 69},
            {"TK_OP_LESS", "[POINT_LEFT]", 86},
            {"TK_OP_GREATER", "[POINT_RIGHT]", 99},
            {"TK_OP_AND", "[OP_LOGIC_AND]", 113},
            {"TK_OP_OR", "[OP_LOGIC_OR]", 128},
            {"TK_BLOCK_START", "[BLOCK_START]", 142},
            {"TK_BLOCK_END", "[BLOCK_END]", 156},
        },
        ""
    },
    // keywords
    {
        "keywords",
        "[LOOP_CIRCULAR] [ARMS_CROSSED_IF] [PALM_FLIP] [INDEX_EXTENDED] [FRAME_SHAPE] [ZIG_ZAG_MOTION] "
        "[DOT_CIRCLE] [PALM_UP] [PALM_DOWN] [ID_QUAD_1] [ID_QUAD_2] [ID_QUAD_3] [ID_QUAD_4] [ID_QUAD_5] "
        "[ID_QUAD_6]",
        {
            {"TK_KW_WHILE", "[LOOP_CIRCULAR]", 0},
            {"TK_KW_IF", "[ARMS_CROSSED_IF]", 16},
            {"TK_KW_ELSE", "[PALM_FLIP]", 34},
            {"TK_KW_POINT", "[INDEX_EXTENDED]", 46},
            {"TK_KW_GROUP", "[FRAME_SHAPE]", 63},
            {"TK_KW_LINE", "[ZIG_ZAG_MOTION]", 77},
            {"TK_KW_CIRCLE", "[DOT_CIRCLE]", 94},
            {"TK_KW_POS", "[PALM_UP]", 107},
            {"TK_KW_NEG", "[PALM_DOWN]", 117},
            {"TK_ID", "[ID_QUAD_1]", 129},
            {"TK_ID", "[ID_QUAD_2]", 141},
            {"TK_ID", "[ID_QUAD_3]", 153},
            {"TK_ID", "[ID_QUAD_4]", 165},
            {"TK_ID", "[ID_QUAD_5]", 177},
            {"TK_ID", "[ID_QUAD_6]", 189},
        },
        ""
    },
    // char
    {
        "char",
        "[FINGER_SPELL_R] [FINGER_SPELL_G]",
        {
            {"TK_CHAR", "[FINGER_SPELL_R]", 0},
            {"TK_CHAR", "[FINGER_SPELL_G]", 17},
        },
        ""
    },
    // eof_explicit
    {
        "eof_explicit",
        "[FINGER_SPELL_R] [REST_STATE] [FINGER_SPELL_G] [EOF]",
        {
            {"TK_CHAR", "[FINGER_SPELL_R]", 0},
            {"TK_CHAR", "[FINGER_SPELL_G]", 30},
            {"TK_EOF", "[EOF]", 47},
        },
        ""
    },
    // eof_final_rest
    {
        "eof_final_rest",
        "[FINGER_SPELL_B] [REST_STATE_FINAL]",
        {
            {"TK_CHAR", "[FINGER_SPELL_B]", 0},
            {"TK_EOF", "[REST_STATE_FINAL]", 17},
        },
        ""
    },
    // eof_natural
    {
        "eof_natural",
        "[FINGER_SPELL_R]",
        {
            {"TK_CHAR", "[FINGER_SPELL_R]", 0},
        },
        ""
    },
    // string_simple
    {
        "string_simple",
        "[QUOTE][FINGER_SPELL_H][FINGER_SPELL_I][QUOTE] [EOF]",
        {
            {"TK_STRING", "[QUOTE][FINGER_SPELL_H][FINGER_SPELL_I][QUOTE]", 0},
            {"TK_EOF", "[EOF]", 47},
        },
        ""
    },
    // string_pauses
    {
        "string_pauses",
        "[QUOTE] [FINGER_SPELL_H] [REST_STATE] [FINGER_SPELL_I] [QUOTE]",
        {
            {"TK_STRING", "[QUOTE] [FINGER_SPELL_H] [REST_STATE] [FINGER_SPELL_I] [QUOTE]", 0},
        },
        ""
    },
    // comment
    {
        "comment",
        "[ID_QUAD_1] [CROSS_ARMS] [UNKNOWN_GESTURE] [UNCROSS] [NUM_5]",
        {
            {"TK_ID", "[ID_QUAD_1]", 0},
            {"TK_NUM", "[NUM_5]", 53},
        },
        ""
    },
    // error_unknown
    {
        "error_unknown",
        "[UNKNOWN_GESTURE]",
        {},
        "Unknown VAGO gesture"
    },
    // error_raw_text
    {
        "error_raw_text",
        "[CROSS_ARMS] @hello [UNCROSS]",
        {},
        "no rule matches"
    },
    // error_raw_string
    {
        "error_raw_string",
        "[QUOTE]HELLO[QUOTE]",
        {},
        "no rule matches"
    },
    // error_quote
    {
        "error_quote",
        "[QUOTE][FINGER_SPELL_H]",
        {},
        "Malformed or unterminated"
    },
    // error_comment_unterminated
    {
        "error_comment_unterminated",
        "[CROSS_ARMS][NUM_3]",
        {},
        "Unterminated VAGO comment"
    },
    // error_comment_nested
    {
        "error_comment_nested",
        "[CROSS_ARMS][CROSS_ARMS][UNCROSS]",
        {},
        "Nested VAGO comment"
    },
    // error_comment_closer
    {
        "error_comment_closer",
        "[UNCROSS]",
        {},
        "Unexpected [UNCROSS]"
    },
    // example2_full
    {
        "example2_full",
        "[ID_QUAD_1] [OP_ASSIGN] [FRAME_SHAPE] [C_SHAPE_LEFT] [NUM_5] [SIDE_SWIPE] [NUM_40] [C_SHAPE_RIGHT] "
        "[DELIM_END]\n[ID_QUAD_1] [PALM_UP] [NUM_45] [DELIM_END]\n[ID_QUAD_1] [OP_MATH_ADD] [NUM_2] [DELIM_END]",
        {
            {"TK_ID", "[ID_QUAD_1]", 0},
            {"TK_OP_ASSIGN", "[OP_ASSIGN]", 12},
            {"TK_KW_GROUP", "[FRAME_SHAPE]", 24},
            {"TK_PAREN_OPEN", "[C_SHAPE_LEFT]", 38},
            {"TK_NUM", "[NUM_5]", 53},
            {"TK_COMMA", "[SIDE_SWIPE]", 61},
            {"TK_NUM", "[NUM_40]", 74},
            {"TK_PAREN_CLOSE", "[C_SHAPE_RIGHT]", 83},
            {"TK_DELIM", "[DELIM_END]", 99},
            {"TK_ID", "[ID_QUAD_1]", 111},
            {"TK_KW_POS", "[PALM_UP]", 123},
            {"TK_NUM", "[NUM_45]", 133},
            {"TK_DELIM", "[DELIM_END]", 142},
            {"TK_ID", "[ID_QUAD_1]", 154},
            {"TK_OP_MATH", "[OP_MATH_ADD]", 166},
            {"TK_NUM", "[NUM_2]", 180},
            {"TK_DELIM", "[DELIM_END]", 188},
        },
        ""
    },
    // example3_full
    {
        "example3_full",
        "[ID_QUAD_2] [OP_ASSIGN] [ID_QUAD_1] [DELIM_END]\n[ARMS_CROSSED_IF] [C_SHAPE_LEFT] [ID_QUAD_1] "
        "[OP_REL_EQ] [ID_QUAD_2] [C_SHAPE_RIGHT]\n[BLOCK_START] [LOOP_CIRCULAR] [C_SHAPE_LEFT] [ID_QUAD_1] "
        "[PALM_UP] [POINT_LEFT_EQ] [NUM_180] [C_SHAPE_RIGHT] [BLOCK_START]\n[ID_QUAD_1] [PALM_DOWN] [NUM_15] "
        "[DELIM_END] [BLOCK_END] [BLOCK_END] [EOF]",
        {
            {"TK_ID", "[ID_QUAD_2]", 0},
            {"TK_OP_ASSIGN", "[OP_ASSIGN]", 12},
            {"TK_ID", "[ID_QUAD_1]", 24},
            {"TK_DELIM", "[DELIM_END]", 36},
            {"TK_KW_IF", "[ARMS_CROSSED_IF]", 48},
            {"TK_PAREN_OPEN", "[C_SHAPE_LEFT]", 66},
            {"TK_ID", "[ID_QUAD_1]", 81},
            {"TK_OP_REL", "[OP_REL_EQ]", 93},
            {"TK_ID", "[ID_QUAD_2]", 105},
            {"TK_PAREN_CLOSE", "[C_SHAPE_RIGHT]", 117},
            {"TK_BLOCK_START", "[BLOCK_START]", 133},
            {"TK_KW_WHILE", "[LOOP_CIRCULAR]", 147},
            {"TK_PAREN_OPEN", "[C_SHAPE_LEFT]", 163},
            {"TK_ID", "[ID_QUAD_1]", 178},
            {"TK_KW_POS", "[PALM_UP]", 190},
            {"TK_OP_LESS_EQ", "[POINT_LEFT_EQ]", 200},
            {"TK_NUM", "[NUM_180]", 216},
            {"TK_PAREN_CLOSE", "[C_SHAPE_RIGHT]", 226},
            {"TK_BLOCK_START", "[BLOCK_START]", 242},
            {"TK_ID", "[ID_QUAD_1]", 256},
            {"TK_KW_NEG", "[PALM_DOWN]", 268},
            {"TK_NUM", "[NUM_15]", 280},
            {"TK_DELIM", "[DELIM_END]", 289},
            {"TK_BLOCK_END", "[BLOCK_END]", 301},
            {"TK_BLOCK_END", "[BLOCK_END]", 313},
            {"TK_EOF", "[EOF]", 325},
        },
        ""
    },
    // example4_full
    {
        "example4_full",
        "[ID_QUAD_3] [OP_ASSIGN] [DOT_CIRCLE] [NUM_25] [DELIM_END]\n[FRAME_SHAPE] [C_SHAPE_LEFT] [ID_QUAD_1] "
        "[SIDE_SWIPE] [ID_QUAD_2] [SIDE_SWIPE] [ID_QUAD_3] [C_SHAPE_RIGHT] [DELIM_END]",
        {
            {"TK_ID", "[ID_QUAD_3]", 0},
            {"TK_OP_ASSIGN", "[OP_ASSIGN]", 12},
            {"TK_KW_CIRCLE", "[DOT_CIRCLE]", 24},
            {"TK_NUM", "[NUM_25]", 37},
            {"TK_DELIM", "[DELIM_END]", 46},
            {"TK_KW_GROUP", "[FRAME_SHAPE]", 58},
            {"TK_PAREN_OPEN", "[C_SHAPE_LEFT]", 72},
            {"TK_ID", "[ID_QUAD_1]", 87},
            {"TK_COMMA", "[SIDE_SWIPE]", 99},
            {"TK_ID", "[ID_QUAD_2]", 112},
            {"TK_COMMA", "[SIDE_SWIPE]", 124},
            {"TK_ID", "[ID_QUAD_3]", 137},
            {"TK_PAREN_CLOSE", "[C_SHAPE_RIGHT]", 149},
            {"TK_DELIM", "[DELIM_END]", 165},
        },
        ""
    },
    // empty_input
    {
        "empty_input",
        "",
        {},
        ""
    },
    // spaces_only
    {
        "spaces_only",
        "  \t\n[REST_STATE] \r\n",
        {},
        ""
    },
    // repeated_lexemes
    {
        "repeated_lexemes",
        "[NUM_5] [CROSS_ARMS] [NUM_5] [UNCROSS] [NUM_5]",
        {
            {"TK_NUM", "[NUM_5]", 0},
            {"TK_NUM", "[NUM_5]", 39},
        },
        ""
    },
    // after_eof
    {
        "after_eof",
        "[EOF] [NUM_9]",
        {
            {"TK_EOF", "[EOF]", 0},
            {"TK_NUM", "[NUM_9]", 6},
        },
        ""
    },
    // unknown_quad_7
    {
        "unknown_quad_7",
        "[ID_QUAD_7]",
        {},
        "Unknown VAGO gesture"
    },
    // leading_zero_number
    {
        "leading_zero_number",
        "[NUM_00045]",
        {
            {"TK_NUM", "[NUM_00045]", 0},
        },
        ""
    },
};

void verify_tokens(const Designar::DynArray<Designar::Token>& actual,
                   const std::vector<ExpectedToken>& expected) {
    if (actual.size() != expected.size()) {
        throw std::runtime_error(
            "Wrong token count: expected " + std::to_string(expected.size()) +
            ", received " + std::to_string(actual.size()));
    }
    for (std::size_t i = 0; i < expected.size(); ++i) {
        const auto& got = actual[i];
        const auto& want = expected[i];
        if (got.name != want.name ||
            got.lexeme != want.lexeme ||
            got.position != want.position) {
            throw std::runtime_error(
                "Mismatch at token " + std::to_string(i) +
                ": expected " + want.name + " / " + want.lexeme +
                " / " + std::to_string(want.position) +
                ", received " + got.name + " / " + got.lexeme +
                " / " + std::to_string(got.position));
        }
    }
}

void check(const TestCase& test) {
    if (test.expected_error.empty()) {
        verify_tokens(vago::tokenize(test.input), test.expected);
        return;
    }
    try {
        (void)vago::tokenize(test.input);
    } catch (const std::exception& error) {
        if (std::string(error.what()).find(test.expected_error) == std::string::npos) {
            throw std::runtime_error(
                "Unexpected error message: " + std::string(error.what()));
        }
        return;
    }
    throw std::runtime_error("An expected lexical error did not occur");
}

void check_reused_instance() {
    vago::VagoLexer lexer;
    const std::string first =
        "[CROSS_ARMS][UNKNOWN_GESTURE][UNCROSS][NUM_3]";
    const auto first_position = first.find("[NUM_3]");
    verify_tokens(lexer.tokenize(first),
                  {{"TK_NUM", "[NUM_3]", first_position}});
    verify_tokens(lexer.tokenize("[ID_QUAD_6] [EOF]"),
                  {{"TK_ID", "[ID_QUAD_6]", 0},
                   {"TK_EOF", "[EOF]", 12}});
    verify_tokens(lexer.tokenize(""), {});
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: vago_lexer_tests <test-name>\n";
        return 2;
    }
    try {
        const std::string name = argv[1];
        if (name == "reused_instance") {
            check_reused_instance();
        } else {
            bool found = false;
            for (const auto& test : cases) {
                if (test.name == name) {
                    check(test);
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw std::runtime_error("Unknown test name: " + name);
            }
        }
        std::cout << "PASS: " << name << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << argv[1] << ": " << error.what() << '\n';
        return 1;
    }
}
