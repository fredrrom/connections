from lark import Lark


# Canonical TPTP syntax reference: https://tptp.org/TPTP/SyntaxBNF.html
# This grammar implements the supported 0.1 FOF/CNF/QMF subset directly.
GRAMMAR = r"""
?start: tptp_file

tptp_file: tptp_input*

?tptp_input: fof_annotated
           | cnf_annotated
           | qmf_annotated
           | include

fof_annotated: "fof" "(" name "," formula_role "," fof_formula annotations ")" "."
cnf_annotated: "cnf" "(" name "," formula_role "," cnf_formula annotations ")" "."
qmf_annotated: "qmf" "(" name "," formula_role "," fof_formula annotations ")" "."

include: "include" "(" file_name include_optionals ")" "."
include_optionals: ["," formula_selection ["," space_name]]
?formula_selection: formula_selection_names
                  | star
?formula_selection_names: "[" name_list "]"
?star: "*"
name_list: name ("," name)*
?space_name: name

annotations: ["," source ["," general_list]]

formula_role: LOWER_WORD ("-" general_term)?

?source: dag_source
       | internal_source
       | external_source
       | unknown_source
       | source_list
unknown_source: "unknown"
?source_list: "[" sources "]"
sources: source ("," source)*

dag_source: name
          | inference_record
inference_record: "inference" "(" inference_rule "," general_list "," parents ")"
?inference_rule: atomic_word

internal_source: "introduced" "(" intro_type "," general_list ["," parents] ")"
?intro_type: atomic_word

external_source: file_source
               | theory
               | creator_source

file_source: "file" "(" file_name file_info ")"
?file_info: ["," name]
theory: "theory" "(" theory_name ["," general_list] ")"
?theory_name: atomic_word
creator_source: "creator" "(" creator_name "," general_list "," parents ")"
?creator_name: atomic_word

parents: "[" [parent_list] "]"
parent_list: parent_info ("," parent_info)*
parent_info: source [":" general_term]

general_list: "[" [general_terms] "]"
general_terms: general_term ("," general_term)*

general_term: general_colon
            | general_data
            | general_list
general_colon: general_data ":" general_term

general_data: atomic_word
            | general_function
            | variable
            | number
            | distinct_object
            | formula_data
            | bind
            | bind_type

general_function: atomic_word "(" general_terms ")"
bind: "bind" "(" variable "," formula_data ")"
bind_type: "bind_type" "(" variable "," bound_type ")"
bound_type: BOUND_TYPE_LANG "(" raw_payload ")"

formula_data: FORMULA_DATA_RAW_LANG "(" raw_payload ")"
            | FORMULA_DATA_FOF_LANG "(" fof_formula ")"
            | FORMULA_DATA_FOT_LANG "(" fof_term ")"

?cnf_formula: cnf_disjunction
            | "(" cnf_disjunction ")"

?cnf_disjunction: cnf_literal
                | cnf_literal "|" cnf_disjunction -> cnf_or_formula

?cnf_literal: fof_atomic_formula
            | unary_connective fof_atomic_formula -> cnf_prefix_unary
            | fof_term infix_inequality fof_term  -> cnf_infix_unary

?fof_formula: fof_logic_formula

?fof_logic_formula: fof_binary_formula
                 | fof_unary_formula
                 | fof_unitary_formula

?fof_binary_formula: fof_binary_nonassoc
                  | fof_binary_assoc
fof_binary_nonassoc: fof_binary_assoc nonassoc_connective fof_binary_assoc
                   | fof_binary_assoc nonassoc_connective fof_unit_formula
                   | fof_unit_formula nonassoc_connective fof_binary_assoc
                   | fof_unit_formula nonassoc_connective fof_unit_formula
?fof_binary_assoc: fof_or_formula
                 | fof_and_formula
fof_or_formula: fof_unit_formula "|" fof_unit_formula
             | fof_unit_formula "|" fof_or_formula
fof_and_formula: fof_unit_formula "&" fof_unit_formula
              | fof_unit_formula "&" fof_and_formula

?fof_unary_formula: fof_prefix_unary
                  | fof_infix_unary
                  | fof_modal_unary
fof_prefix_unary: unary_connective fof_unit_formula
fof_infix_unary: fof_term infix_inequality fof_term
fof_modal_unary: modal_connective ":" fof_unit_formula

modal_connective: MODAL_OPERATOR ["(" fof_term ")"]

?fof_unit_formula: fof_unitary_formula
                 | fof_unary_formula

?fof_unitary_formula: fof_quantified_formula
                    | fof_atomic_formula
                    | "(" fof_logic_formula ")"

fof_quantified_formula: fof_quantifier "[" fof_variable_list "]" ":" fof_unit_formula
fof_variable_list: variable
                 | variable "," fof_variable_list

fof_atomic_formula: fof_plain_atomic_formula
                  | fof_defined_atomic_formula
                  | fof_system_atomic_formula

?fof_plain_atomic_formula: fof_plain_term
?fof_defined_atomic_formula: fof_defined_plain_formula
                          | fof_defined_infix_formula
?fof_defined_plain_formula: fof_defined_plain_term
fof_defined_infix_formula: fof_term defined_infix_pred fof_term
?fof_system_atomic_formula: fof_system_term

?fof_plain_term: constant                                      -> term_tuple
               | functor "(" fof_arguments ")"                 -> term_tuple
?fof_defined_term: defined_term                                -> term_tuple
                 | fof_defined_atomic_term
?fof_defined_atomic_term: fof_defined_plain_term
?fof_defined_plain_term: defined_constant                      -> term_tuple
                       | defined_functor "(" fof_arguments ")" -> term_tuple
?fof_system_term: system_constant                              -> term_tuple
                | system_functor "(" fof_arguments ")"         -> term_tuple
fof_arguments: fof_term ("," fof_term)*
?fof_term: fof_function_term
         | variable
fof_function_term: fof_plain_term
                 | fof_defined_term
                 | fof_system_term

?fof_quantifier: FOF_QUANTIFIER

?nonassoc_connective: NONASSOC
?unary_connective: UNARY
?defined_infix_pred: infix_equality
?infix_equality: INFIX_EQ
?infix_inequality: INFIX_NEQ

FOF_QUANTIFIER: "!" | "?"
NONASSOC: "<=>" | "=>" | "<=" | "<~>" | "~|" | "~&"
UNARY: "~"
MODAL_OPERATOR: "#box" | "#dia"
INFIX_NEQ: "!="
INFIX_EQ: "="
BOUND_TYPE_LANG: "$thf" | "$tff"
FORMULA_DATA_RAW_LANG: "$thf" | "$tff" | "$cnf"
FORMULA_DATA_FOF_LANG: "$fof"
FORMULA_DATA_FOT_LANG: "$fot"

?name: atomic_word
     | integer
?file_name: atomic_word

?atomic_word: LOWER_WORD
            | SINGLE_QUOTED
            | BACK_QUOTED

variable: UPPER_WORD
?number: integer | rational | real
?defined_term: number | distinct_object
?integer: SIGNED_INTEGER | UNSIGNED_INTEGER
?rational: SIGNED_RATIONAL | UNSIGNED_RATIONAL
?real: SIGNED_REAL | UNSIGNED_REAL
?distinct_object: DISTINCT_OBJECT

?functor: atomic_word
?defined_functor: DOLLAR_WORD
?system_functor: DOLLAR_DOLLAR_WORD
?constant: functor
?defined_constant: defined_functor
?system_constant: system_functor
?predicate: atomic_word
?proposition: predicate
?defined_predicate: defined_functor
?defined_proposition: defined_predicate

raw_payload: raw_item*
?raw_item: RAW_TEXT
         | "(" raw_payload ")"
         | "[" raw_payload "]"
         | "{" raw_payload "}"

RAW_TEXT: /[^()\[\]{}]+/

LOWER_WORD: /[a-z][A-Za-z0-9_]*/
UPPER_WORD: /[A-Z][A-Za-z0-9_]*/
DOLLAR_WORD: /\$[A-Za-z][A-Za-z0-9_]*/
DOLLAR_DOLLAR_WORD: /\$\$[A-Za-z][A-Za-z0-9_]*/
SINGLE_QUOTED: /'([^'\\]|\\.)*'/
BACK_QUOTED: /`[A-Za-z][A-Za-z0-9_]*/
DISTINCT_OBJECT: /"([^"\\]|\\.)*"/

SIGNED_REAL: /[+-](?:[0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?|[0-9]+[eE][+-]?[0-9]+)/
UNSIGNED_REAL: /(?:[0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?|[0-9]+[eE][+-]?[0-9]+)/
SIGNED_RATIONAL: /[+-][0-9]+\/[1-9][0-9]*/
UNSIGNED_RATIONAL: /[0-9]+\/[1-9][0-9]*/
SIGNED_INTEGER: /[+-](?:0|[1-9][0-9]*)/
UNSIGNED_INTEGER: /0|[1-9][0-9]*/

LINE_COMMENT: /%[^\n]*/
BLOCK_COMMENT: /\/\*[\s\S]*?\*\//

%import common.WS
%ignore WS
%ignore LINE_COMMENT
%ignore BLOCK_COMMENT
"""


PARSER = Lark(GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=True)
