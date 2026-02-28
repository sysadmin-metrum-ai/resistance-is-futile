# Codebase Structure

**Analysis Date:** 2026-02-27

## Directory Layout

```
resistance-is-futile/
├── .planning/                   # GSD planning artifacts
│   └── codebase/               # Codebase mapping documents
├── tools/                      # Tool implementations
│   └── drone-acharya/          # Go CLI tool for trilateration
│       ├── cmd/                # CLI subcommands
│       ├── io/                 # Input/output handling
│       ├── trilat/             # Trilateration algorithm
│       ├── main.go             # Entry point
│       ├── go.mod              # Go module definition
│       └── README.md           # Tool documentation
├── test-hover.py               # Python flight test script
├── requirements.txt            # Python dependencies
└── README.md                   # Main project documentation
```

## Directory Purposes

**Root Directory:**
- Purpose: Project documentation and flight scripts
- Contains: README, Python test script, requirements
- Key files: `README.md`, `test-hover.py`, `requirements.txt`

**tools/drone-acharya/:**
- Purpose: Go CLI tool for LPS anchor coordinate calculation
- Contains: Source code, tests, documentation
- Key files: `main.go`, `go.mod`, `README.md`

**tools/drone-acharya/cmd/:**
- Purpose: CLI command implementations
- Contains: template.go, solve.go
- Key files: `cmd/template.go`, `cmd/solve.go`

**tools/drone-acharya/io/:**
- Purpose: CSV/TSV parsing and output formatting
- Contains: csv.go, format.go, tests
- Key files: `io/csv.go`, `io/format.go`

**tools/drone-acharya/trilat/:**
- Purpose: Core trilateration mathematics
- Contains: Algorithm implementation and tests
- Key files: `trilat/trilat.go`

## Key File Locations

**Entry Points:**
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/main.go`: Go CLI entry point
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`: Python flight script entry point

**Configuration:**
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/go.mod`: Go module definition
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/requirements.txt`: Python dependencies

**Core Logic:**
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go`: Trilateration algorithm
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/io/csv.go`: CSV parsing

**Testing:**
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat_test.go`
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/io/csv_test.go`
- `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/integration_test.go`

## Naming Conventions

**Files:**
- Go: lowercase with underscores (e.g., `trilat.go`, `csv_test.go`)
- Python: lowercase with hyphens (e.g., `test-hover.py`)
- Markdown: lowercase (e.g., `README.md`)

**Directories:**
- Go packages: lowercase, no underscores (e.g., `trilat`, `io`, `cmd`)
- Top-level: descriptive (e.g., `tools`, `docs`)

**Go Types:**
- Types: PascalCase (e.g., `Coord`, `Result`, `ValidationRow`)
- Functions: PascalCase (e.g., `Solve`, `Validate`, `ReadDistances`)

## Where to Add New Code

**New CLI Subcommand:**
- Implementation: `tools/drone-acharya/cmd/<subcommand>.go`
- Register in: `tools/drone-acharya/main.go`

**New Output Format:**
- Implementation: `tools/drone-acharya/io/format.go`
- Add new Write* function

**New Algorithm Variant:**
- Implementation: `tools/drone-acharya/trilat/`
- Add new file or function

**Python Flight Scripts:**
- Implementation: Root directory or `scripts/`
- Follow cflib patterns from `test-hover.py`

## Special Directories

**.git/:** Git repository metadata - generated, not committed

**.planning/codebase/:** GSD planning artifacts - generated, committed

**tools/drone-acharya/:** Main code - committed, version controlled

---

*Structure analysis: 2026-02-27*
