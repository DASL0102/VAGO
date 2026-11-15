cmake_minimum_required(VERSION 3.28)

project(VAGO_Lexer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Designar CONFIG REQUIRED)

add_library(vago_lexer_core STATIC
    src/lexer.cpp
)

target_include_directories(vago_lexer_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(vago_lexer_core
    PUBLIC Designar::Designar
)

add_executable(vago_lexer
    src/main.cpp
)

target_link_libraries(vago_lexer
    PRIVATE vago_lexer_core
)

include(CTest)

if(BUILD_TESTING)
    add_executable(vago_lexer_tests
        tests/lexer_tests.cpp
    )

    target_link_libraries(vago_lexer_tests
        PRIVATE vago_lexer_core
    )

    foreach(case_name IN ITEMS
        line
        polygon
        operators
        keywords
        char
        eof_explicit
        eof_final_rest
        eof_natural
        string_simple
        string_pauses
        comment
        error_unknown
        error_raw_text
        error_raw_string
        error_quote
        error_comment_unterminated
        error_comment_nested
        error_comment_closer
        example2_full
        example3_full
        example4_full
        empty_input
        spaces_only
        repeated_lexemes
        after_eof
        unknown_quad_7
        leading_zero_number
        reused_instance
    )
    add_test(
        NAME "lexer.${case_name}"
        COMMAND vago_lexer_tests "${case_name}"
    )
endforeach()
endif()
