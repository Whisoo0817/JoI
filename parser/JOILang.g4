grammar JOILang;

// --- Parser Rules ---

scenario            : NEWLINE* statement_list EOF;


statement_list : statement ( (NEWLINE | SEMICOLON)+ statement )* (NEWLINE | SEMICOLON)*;

statement           : value_assign_behavior
                    | action_behavior
                    | if_statement
                    | loop_statement
                    | for_each_statement
                    | wait_until_statement
                    | delay_statement
                    | compound_statement
                    | break
                    ;

break : BREAK;

compound_statement: '{' NEWLINE* statement_list '}';


value_assign_behavior : output ASSIGN arithmetic_expression
                      | output INITIAL_ASSIGN arithmetic_expression;

action_behavior     : (output ASSIGN)? range_type '(' tag_list ')' DOT IDENTIFIER '(' action_input ')'
                    | (output ASSIGN)? '(' tag_list ')' DOT IDENTIFIER '(' action_input ')'
                    ;

output              : IDENTIFIER;

//identifier_list     : IDENTIFIER (COMMA IDENTIFIER)*;

range_type          : ALL
                    | ANY
                    ;

tag_list            : hashtag_list;

hashtag_list        : (HASHTAG_ID)+;

action_input        : // empty rule
                    | input_list
                    ;


arithmetic_expression
    : arithmetic_expression ('*'|'/') arithmetic_expression
    | arithmetic_expression ('+'|'-') arithmetic_expression
    | '(' arithmetic_expression ')'
    | primary_expression
    ;

input_list          : arithmetic_expression (COMMA arithmetic_expression)*;

primary_expression  : (TRUE|FALSE)
                    | IDENTIFIER
                    | INTEGER
                    | DOUBLE
                    | STRING_LITERAL
                    | (range_type)? '(' tag_list ')' DOT IDENTIFIER
                    ;


for_each_statement  : FOR_EACH '(' IDENTIFIER COLON list_expression ')' NEWLINE* statement;

list_expression     : IDENTIFIER
                    | ALL '(' tag_list ')' DOT IDENTIFIER;


if_statement        : IF '(' condition_list ')' NEWLINE* statement NEWLINE* else_statement?;

condition_list      : condition_atom
                    | '(' condition_list ')'
                    | condition_list (OR | AND) condition_list
                    | NOT condition_atom
                    ;

condition_atom      : arithmetic_expression comparison_operator arithmetic_expression
                    | arithmetic_expression
                    ;

comparison_operator : (GE|LE|EQ|NE|'>'|'<') OR_FLAG?;


else_statement      : ELSE statement;

loop_statement      : LOOP '(' loop_condition ')' NEWLINE* statement;

loop_condition      : // empty rule
                    | condition_list
                    ;

period_time         : INTEGER time_unit;

time_unit           : MILLISECOND
                    | SECOND
                    | MINUTE
                    | HOUR
                    | DAY
                    ;

wait_until_statement : WAIT_UNTIL '(' condition_list ')'
                     ;

delay_statement     : DELAY '(' period_time ')';


// --- Lexer Rules ---

INTEGER             : [+-]? [0-9]+;
DOUBLE              : [+-]? ([0-9]* '.' [0-9]+ | [0-9]+ '.');
STRING_LITERAL      : '"' ( ~('\\'|'"') | '\\.' )* '"'
                    | '\'' ( ~('\\'|'\'') | '\\.' )* '\'';


WAIT_UNTIL          : 'wait until';
BREAK               : 'break';
DELAY               : 'delay';
LOOP                : 'loop';
IF                  : 'if';
ELSE                : 'else';
FOR_EACH            : 'for';
NOT                 : 'not';
ALL                 : 'all';
ANY                 : 'any';
OR                  : 'or';
AND                 : 'and';
MILLISECOND         : 'MSEC';
SECOND              : 'SEC';
MINUTE              : 'MIN';
HOUR                : 'HOUR';
DAY                 : 'DAY';
TRUE                : 'true';
FALSE               : 'false';

GE                  : '>=';
LE                  : '<=';
EQ                  : '==';
NE                  : '!=';
INITIAL_ASSIGN      : ':=';
ASSIGN              : '=';
PLUS                : '+';
MINUS               : '-';
TIMES               : '*';
DIVIDE              : '/';
COMMA               : ',';
COLON               : ':';
SEMICOLON           : ';';
LBRACKET            : '[';
RBRACKET            : ']';
DOT                 : '.';
OR_FLAG             : '|';


IDENTIFIER          : [a-zA-Z_] [a-zA-Z0-9_]*;
TAG_IDENTIFIER      : [\p{XID_Start}\p{N}] [\p{XID_Continue}:-]* ;

HASHTAG_ID          : '#' TAG_IDENTIFIER;


WS                  : [ \t]+ -> skip;
NEWLINE             : '\r'? '\n';

COMMENT_SINGLE_LINE : '//' ~[\r\n]* -> skip; //
COMMENT_MULTI_LINE  : '/*' .*? '*/' -> skip; //

ERROR_TOKEN         : .;
