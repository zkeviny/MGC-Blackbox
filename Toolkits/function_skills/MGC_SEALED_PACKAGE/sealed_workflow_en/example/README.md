# example/ — Demo Script Set

> 4 scripts demonstrating MGC 1.5.2's `ext08` auto-recognition and runtime sealed routing for all cross-script call patterns.
> Uses Python standard library only. Cross-platform: macOS / Linux / Windows.

## File structure

```
example/
├── config_a.py        # A · config script (callable via both import and subprocess)
├── script_b.py        # B · gets values from A via import → writes txt1.txt to Desktop
├── script_c.py        # C · calls A via subprocess → writes txt2.txt to Desktop
├── script_d.py        # D · imports B + subprocess C → writes combined.txt to Desktop
└── README.md          # this file
```

## ext08 pattern demo matrix (verified on MGC 1.5.2)

| Call relation | Code pattern | ext08 edge type | Recognized |
|--------------|---------------|-----------------|------------|
| B → A | `from config_a import get_greeting, DEFAULT_USER` | `from_import` | ✅ |
| B → A | `import config_a` | `import` | ✅ |
| C → A | `subprocess.run([sys.executable, "config_a.py", ...])` | `subprocess` | ✅ |
| D → B | `import script_b; script_b.run(...)` | `import` | ✅ |
| D → C | `subprocess.run([sys.executable, "script_c.py", ...])` | `subprocess` | ✅ |

> Before 1.5.2, `subprocess.run([sys.executable, "x.py"])` literal list runtime routing was **not supported**; from 1.5.2 it is fully supported.

## Output files (explicit disk artifacts — black-box execution does not rely on `print`)

| File | Written by | Content |
|------|-----------|---------|
| `~/Desktop/txt1.txt` | B | Greeting from A via `import`, plus DEFAULT_USER |
| `~/Desktop/txt2.txt` | C | Summary written by C (calls A via subprocess) |
| `~/Desktop/txt2_via_a.txt` | A (spawned by C) | Greeting written by A's subprocess |
| `~/Desktop/combined.txt` | D | Rollup of B and C outputs |

> On Linux, if `~/Desktop` does not exist, falls back to `~`.

## Recommended try-it-yourself flow (MGC MCP tools)

### 1. Store

```python
mgc_save_file(
    path="./example",
    info_owner="demo_workflow",
    diff_2="example",
)
# Auto-builds ext08 call graph (verified 5 edges)
```

### 2. Get your own node_pub

```python
my_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
# Returns multi-line PEM public key
```

### 3. Seal to your own node

```python
mgc_seal_package(
    info_owner="demo_workflow",
    diff_2="example",
    ext04=str(my_pub),                          # required: target node PEM
    output_dir="./_demo_out",                   # required: output directory
)
# → generates example_delivery/example.mgc_file + README.md
```

### 4. Import the sealed package

```python
mgc_save_file(
    path="./_demo_out/example_delivery/example.mgc_file",
    info_owner="demo_workflow",                 # required: must match sealing-time
    diff_2="example",
)
# Decrypts into 5 records (including SKILL.md)
```

### 5. Black-box run

```python
mgc_run(
    info_type="script",
    info_owner="demo_workflow",
    diff_2="example",
    diff_3="script_d.py",
)
# → {"status": "started"}
# AI sees no source code
```

### 6. Verify results

After 5 seconds, check that all 4 files exist on the Desktop — `txt1.txt`, `txt2.txt`, `txt2_via_a.txt`, `combined.txt`. All 4 present = end-to-end success.

> ⚠️ Known warning: MGC may misreport same-package `script_b` as an external dependency (`DEP_MISSING`) — ignore it; the scripts themselves run normally.

## Design principles

1. **Zero non-standard dependencies**: only `os` / `sys` / `subprocess` / `argparse` / `pathlib` / `time`
2. **Cross-platform**: `Path.home() / "Desktop"`, falls back to `~` on Linux
3. **Black-box friendly**: every result is explicitly written to a Desktop file, no `print` capture dependency
4. **Complete argparse**: each script has a literal `default=`, so `ext02` is auto-recognized
5. **UTF-8 throughout**: avoids Windows CJK garbling

## Patterns NOT demonstrated (see SKILL.md for the full list)

- Dynamic module name: `importlib.import_module(x)`
- Absolute path: `open("/Users/.../config.py")`
- Cross-subdirectory: `Path(__file__).parent.parent / "y.py"`
- Function-level reference: `import helpers; helpers.some_func()` without a literal `Path`

These **cannot be recognized by ext08**; details in SKILL.md "Recognizable cross-script patterns".