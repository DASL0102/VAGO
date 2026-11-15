#pragma once

#include <map.hpp>
#include <string>
#include <lexer.hpp>

namespace vago {

class VagoLexer {
    public:
        VagoLexer();

        Designar::DynArray<Designar::Token> tokenize(
            const std::string& input
        ) const;

    private:
        Designar::Lexer lexer_;
        Designar::HashMap<std::string, std::string> keywords_;
    };

    Designar::DynArray<Designar::Token> tokenize(
        const std::string& input
    );

} // namespace vago
