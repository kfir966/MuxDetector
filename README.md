# MuxDetector (`muxfind`)

`muxfind` is a dependency-free Python 3.10+ command-line tool that classifies
Liberty output-pin functions as MUX2, MUX4, MUX8, or not a mux. Classification
uses the Boolean function, not cell or pin names.

## Run

Install from the project directory:

```shell
python -m pip install -e .
```

On systems where the Python 3 command is `python3`, use that in place of
`python`.

Analyze one or more plain or gzipped Liberty files. CSV goes to stdout unless
`-o` is given; `--debug` writes counts and elapsed time to stderr.

```shell
muxfind mux_train.lib
muxfind library1.lib.gz library2.lib -o results.csv --debug
```

## Tri-state decision

By default, an output pin with a `three_state` attribute is reported as
`NOT_MUX`. A tri-state output can be high-impedance, which is not represented by
the pin's Boolean function. Use `--tristate-policy function` to classify the
Boolean function anyway; the result includes a tri-state note.

## Five-part module architecture

1. **Reader**
   `muxfind/reader.py`
   Opens plain or gzip Liberty files and reads their text.

2. **Liberty structure parser**
   `muxfind/liberty/tokenizer.py`, `muxfind/liberty/parser.py`,
   Tokenizes Liberty text, extracts cells and direct output pins, and skips
   nested non-pin groups.

3. **Boolean function parser and AST**
   `muxfind/boolean/expression_parser.py`, `muxfind/boolean/ast.py`
   Parses Liberty Boolean syntax into an abstract syntax tree (AST).

4. **MUX analyzer**
   `muxfind/boolean/mux_analyzer.py`, `muxfind/boolean/bdd.py`
   Removes irrelevant inputs, identifies select and data inputs pins, and checks
   whether every select setting maps to one data input. 
   For wide expressions, the BDD finds the relevant inputs before truth-table analysis.

5. **CSV output and CLI**
   `muxfind/library_analyzer.py`, `muxfind/csv_writer.py`
   writes CSV with the results.

## Terms

- **AST (abstract syntax tree):** a tree representation of the function, with
  nodes for constants, input variables, NOT, and binary operations.
- **BDD (binary decision diagram):** a graph that represents a Boolean function
  by testing variables and following 0/1 branches. This tool uses a reduced,
  ordered BDD (ROBDD) to find relevant variables in wide expressions before
  creating a truth table.
- **Vacuous input:** an input mentioned in the expression that cannot change
  the output. It is not counted as a true dependency.
- **Binate input:** an input that can affect the output in both directions
  under different settings of the other inputs. MUX select inputs are binate.
- **Cofactor:** the function left after fixing one input to a value. 
  low cofactor = fixes that input to `0`; 
  high cofactor =  fixes it to `1`. 
  Comparing them shows whether, and how, that input can change the output. 
  For example,
  `S AND D`: fixing `S` to `0` leaves `0`; fixing `S` to `1` leaves `D`.

## Recognition algorithm and why it is correct

For at most 16 syntactic inputs, the analyzer evaluates the expression as an
integer bit vector: each bit is one truth-table row. With more inputs, a bounded
ROBDD first finds the inputs that can affect the output. 
The analyzer then removes vacuous inputs and 
compares the low and high cofactors of each remaining:
input 
- If the cofactors differ in both directions, the input is binate and may
be a select pin. 
- If it can only stay the same or change from 0 to 1, it is positive-unate; 
- if it can only stay the same or change from 1 to 0, it is negative-unate.

A function is accepted only when:

1. It has exactly 3, 6, or 11 active inputs: respectively one, two, or three
   selects plus 2, 4, or 8 data inputs.
2. For every select setting, fixing the selects leaves the output equal to one
   data input, or to its negate val (`NOT` of that data input).
3. Every data input is selected exactly once.
4. All data paths have the same polarity: all normal or all inverted.

These checks directly test the functional definition of a MUX.

## Complexity and limits

### Truth-table work

- With `n` inputs, all possible input combinations make `2^n` truth-table rows.
  The row count doubles each time another input is added.
- Each AST node produces a truth-table bit vector. Python's integer bit
  operations process many row bits at once, so each node takes about
  `2^n / w` integer-digit operations, 
  where `w` is the number of bits in one Python integer digit.
- For an AST with `A` nodes, total work is about `A * 2^n / w`. The analyzer
  uses this method only up to 16 syntactic inputs (at most 65,536 rows).
- The intermediate vectors together use about `A * 2^n` bits of memory.

### Wider expressions and supported MUX sizes

Above 16 syntactic inputs, a bounded ROBDD is used to find which inputs can
affect the output before building a truth table. Its limits are 128 variables,
100,000 decision nodes, and 200,000 cached operations. BDD size can still grow
exponentially; reaching a limit is reported as an analysis error.

The analyzer recognizes 2:1, 4:1, and 8:1 MUXes. A 16:1 MUX can be parsed, but
is not recognized as a MUX: the analyzer does not support its 4-select,
16-data-input mapping.

## Library scaling

Current behavior:
The reader loads the entire library text. The tokenizer then creates a cleaned
copy and a token list. As a result, memory use grows with the size of the whole
library.

Planned 100,000-cell design:
1. Read the file incrementally instead of loading it into one string.
2. Scan until one complete `cell (...) { ... }` group is found, then yield only
   that cell's text. The yielded text is the input for one iteration.
3. In that iteration, tokenize, parse, and analyze the yielded cell text, then
   write its CSV result rows, before requesting the next cell.
4. Repeat until the file ends. The scanner must track comments, quoted strings,
   escapes, and brace depth so it finds the real end of each cell.

This way, the tool processes one cell's text per iteration rather than holding
the whole library text and all its tokens in memory.

## Limitations

- The parser supports the Liberty structures and syntax needed by this tool, 
  and not the full Liberty grammar.
- The analyzer recognizes MUX2, MUX4, and MUX8 only. Larger MUXes, such as a
  16:1 MUX, are not classified as MUXes.
- A missing or malformed Boolean function is reported as `NO_FUNCTION`.
- The reader does not yet stream cells; large-library memory use is not
  benchmarked.

## Tests

Install pytest and run the test suite:

```shell
python -m pip install pytest
python -m pytest -q
```

The tests include custom Liberty cells for normal and inverted MUXes, invalid
functions, sequential and tri-state cells, nested groups, and multiple outputs.
They also generate a library with 1,000 simple cells and run the CLI with both
tri-state policies.

## Validation results

The training library produces 9 MUX2, 2 MUX4, 10 NOT_MUX, 1 SEQUENTIAL, and
1 NO_FUNCTION result across 23 output rows. All eight rows in
[`mux_train_sample_expected.csv`](mux_train_sample_expected.csv) match the
provided expected columns. Full results are in
[`out_train.csv`](out_train.csv).

PDK results are stored once per library in 'pdk_results' sub-dir in the files:
sky130_fd_sc_hd__tt_025C_1v80_results.csv
and
NangateOpenCellLibrary_typical_results.csv.
They were generated from the public OpenROAD-flow-scripts sky130 HD and
Nangate45 Liberty libraries. The times below are single-run measurements and
will vary by system.

| Library | Parsed cells | Output rows | MUX2 | MUX4 | MUX8 | NOT_MUX | SEQUENTIAL | NO_FUNCTION | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sky130 HD, `tt_025C_1v80` | 428 | 438 | 7 | 30 | 0 | 347 | 69 | 12 | 1.902 s |
| Nangate45, typical | 135 | 137 | 2 | 0 | 0 | 98 | 29 | 8 | 1.077 s |

The sky130 MUX outputs are the `mux2`, `mux2i`, and `mux4` cells. Nangate45
produced `MUX2_X1` and `MUX2_X2`. No MUX8 was found in either run.
