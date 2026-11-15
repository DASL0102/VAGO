#include <exception>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vago/lexer.hpp>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: vago_lexer <file.vago>\n";
        return 2;
    }

    std::ifstream file(argv[1], std::ios::binary);
    if (!file) {
        std::cerr << "Could not open VAGO input file: " << argv[1] << '\n';
        return 2;
    }

    const std::string input(
        (std::istreambuf_iterator<char>(file)),
        std::istreambuf_iterator<char>()
    );
    if (file.bad()) {
        std::cerr << "Could not read VAGO input file: " << argv[1] << '\n';
        return 2;
    }

    try {
        const auto tokens = vago::tokenize(input);
        for (std::size_t i = 0; i < tokens.size(); ++i) {
            const auto& token = tokens[i];
            std::cout << token.name << " | "
                      << token.lexeme << " | "
                      << token.position << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "Lexical error: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
