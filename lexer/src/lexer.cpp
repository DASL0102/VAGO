#include <vago/lexer.hpp>

#include <stdexcept>
#include <string>

namespace vago {

    VagoLexer::VagoLexer() {
        const std::string digits = "(0|1|2|3|4|5|6|7|8|9)";
        const std::string letters =
            "(A|B|C|D|E|F|G|H|I|J|K|L|M|N|O|P|Q|R|S|T|U|V|W|X|Y|Z)";
        const std::string symbol_char = "(" + letters + "|" + digits + "|_)";

        lexer_.add_token("TK_NUM", "\\[NUM_" + digits + "+\\]");
        lexer_.add_token("TK_DELIM", "\\[DELIM_END\\]");
        lexer_.add_token("TK_OP_ASSIGN", "\\[OP_ASSIGN\\]");
        lexer_.add_token("TK_PAREN_OPEN", "\\[C_SHAPE_LEFT\\]");
        lexer_.add_token("TK_PAREN_CLOSE", "\\[C_SHAPE_RIGHT\\]");
        lexer_.add_token("TK_COMMA", "\\[SIDE_SWIPE\\]");
        lexer_.add_token("TK_OP_MATH", "\\[OP_MATH_(ADD|SUB)\\]");
        lexer_.add_token("TK_OP_REL", "\\[OP_REL_(EQ|NEQ)\\]");
        lexer_.add_token("TK_OP_LESS_EQ", "\\[POINT_LEFT_EQ\\]");
        lexer_.add_token("TK_OP_GREATER_EQ", "\\[POINT_RIGHT_EQ\\]");
        lexer_.add_token("TK_OP_LESS", "\\[POINT_LEFT\\]");
        lexer_.add_token("TK_OP_GREATER", "\\[POINT_RIGHT\\]");
        lexer_.add_token("TK_OP_AND", "\\[OP_LOGIC_AND\\]");
        lexer_.add_token("TK_OP_OR", "\\[OP_LOGIC_OR\\]");
        lexer_.add_token("TK_BLOCK_START", "\\[BLOCK_START\\]");
        lexer_.add_token("TK_BLOCK_END", "\\[BLOCK_END\\]");
        lexer_.add_token("TK_CHAR", "\\[FINGER_SPELL_" + letters + "\\]");
        lexer_.add_token("TK_EOF", "\\[(EOF|REST_STATE_FINAL)\\]");

        // A string is one or more finger-spelled letters between QUOTE gestures.
        const std::string finger_spell = "\\[FINGER_SPELL_" + letters + "\\]";
        const std::string string_separator = "( |\t|\r|\n|\\[REST_STATE\\])*";
        lexer_.add_token(
            "TK_STRING",
            "\\[QUOTE\\]" + string_separator +
            "(" + finger_spell + string_separator + ")+\\[QUOTE\\]"
        );
        lexer_.add_token("TK_QUOTE", "\\[QUOTE\\]");

        // Comment boundaries are internal tokens (not returned to the parser).
        lexer_.add_token("TK_COMMENT_START", "\\[CROSS_ARMS\\]");
        lexer_.add_token("TK_COMMENT_END", "\\[UNCROSS\\]");
        lexer_.add_token("TK_SPACE", "\\[REST_STATE\\]");
        lexer_.add_token("TK_SPACE", "( |\t|\r|\n)+");
        lexer_.add_token("TK_SYMBOL", "\\[" + symbol_char + "+\\]");

        // Symbol table reclassified using a hashmap
        keywords_.insert("[LOOP_CIRCULAR]", "TK_KW_WHILE");
        keywords_.insert("[ARMS_CROSSED_IF]", "TK_KW_IF");
        keywords_.insert("[PALM_FLIP]", "TK_KW_ELSE");
        keywords_.insert("[INDEX_EXTENDED]", "TK_KW_POINT");
        keywords_.insert("[FRAME_SHAPE]", "TK_KW_GROUP");
        keywords_.insert("[ZIG_ZAG_MOTION]", "TK_KW_LINE");
        keywords_.insert("[DOT_CIRCLE]", "TK_KW_CIRCLE");
        keywords_.insert("[PALM_UP]", "TK_KW_POS");
        keywords_.insert("[PALM_DOWN]", "TK_KW_NEG");
        keywords_.insert("[ID_QUAD_1]", "TK_ID");
        keywords_.insert("[ID_QUAD_2]", "TK_ID");
        keywords_.insert("[ID_QUAD_3]", "TK_ID");
        keywords_.insert("[ID_QUAD_4]", "TK_ID");
        keywords_.insert("[ID_QUAD_5]", "TK_ID");
        keywords_.insert("[ID_QUAD_6]", "TK_ID");
    }

    Designar::DynArray<Designar::Token> VagoLexer::tokenize(
        const std::string& input
    ) const {
        auto scanned = lexer_.tokenize(input);
        Designar::DynArray<Designar::Token> result;
        bool in_comment = false;
        std::size_t comment_start = 0;

        for (std::size_t i = 0; i < scanned.size(); ++i) {
            Designar::Token token = scanned[i];

            if (token.name == "TK_COMMENT_START") {
                if (in_comment) {
                    throw std::runtime_error(
                        "Nested VAGO comment at position " +
                        std::to_string(token.position)
                    );
                }
                in_comment = true;
                comment_start = token.position;
                continue;
            }

            if (token.name == "TK_COMMENT_END") {
                if (!in_comment) {
                    throw std::runtime_error(
                        "Unexpected [UNCROSS] at position " +
                        std::to_string(token.position)
                    );
                }
                in_comment = false;
                continue;
            }

            if (in_comment) continue;

            if (token.name == "TK_QUOTE") {
                throw std::runtime_error(
                    "Malformed or unterminated VAGO string at position " +
                    std::to_string(token.position)
                );
            }
            if (token.name == "TK_SPACE") continue;

            if (token.name == "TK_SYMBOL") {
                const std::string* name = keywords_.search(token.lexeme);
                if (name == nullptr) {
                    throw std::runtime_error(
                        "Unknown VAGO gesture at position " +
                        std::to_string(token.position) + ": " + token.lexeme
                    );
                }
                token.name = *name;
            }
            result.append(token);
        }

        if (in_comment) {
            throw std::runtime_error(
                "Unterminated VAGO comment starting at position " +
                std::to_string(comment_start)
            );
        }
        return result;
    }

    Designar::DynArray<Designar::Token> tokenize(const std::string& input) {

        static const VagoLexer shared_lexer;
        return shared_lexer.tokenize(input);
    }

} // namespace vago
