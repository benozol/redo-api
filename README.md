# redo\_api
A python API to DJB’s redo.

# Basic use of redo\_api in a python redo script
```python
#!/usr/bin/env python3
import redo

# Get first redo snippet, assuming that there is only ones
arg, = redo.snippets

# Run redo-ifchange on the dependency file and read its data with an appropriate unserializer
dep = redo.ifchange(f"{arg}.dependency.csv")

result = process(dep)

# Write resulting data to the temporary redo file, using an appropriate serializer
redo.output(result)
```

# Installation

```shell
pipenv install git+https://github.com/benozol/redo_api#egg=redo_api
```
