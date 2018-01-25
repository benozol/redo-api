"""
A very thin python API to DJB’s redo
===

redo_api reads and writes files with extensions csv, pickle, txt, json, yaml,
and h5, xls(x).

redo_api additionaly reads files with extensions py (to python module), and
without extension (no data).

Example python do script:
```python
#!/usr/bin/env python3
import redo

# Get first redo snippet, assuming that there is only ones
arg, = redo.snippets

# Run redo-ifchange on the dependency file and get its data
dep = redo.ifchange("{arg}.dependency.csv")

result = process(dep)

redo.output(result)  # Write resulting data to the temporary file
```
"""
from .redo import read_data, ifchange, ifchange_ignore, write_data, output, print, push, pop, popjoin, exit

try:
    from .redo import target, base, temp, parent
except ImportError:
    pass
