from collections import OrderedDict
from pathlib import Path
import builtins
import sys
import os


class Snippets:

    def __init__(self, base):
        self.snippets = Path(base).name.split('.')

    def __call__(self, n):
        if n is None:
            return self.snippets
        if n == 1:
            return '.'.join(self.snippets)
        else:
            res = self.snippets[:n-1]
            res.append('.'.join(self.snippets[n-1:]))
            return res

    def __getitem__(self, n):
        return self.snippets[n]

    def __iter__(self, n=None):
        return iter(self(n))


use_redo = not(os.getenv("NO_REDO"))

if len(sys.argv) == 4:
    # When called as `redo X.Y`
    target, base, temp = sys.argv[1:4]
    parent = Path(target).parent
    snippets = Snippets(base)
elif len(sys.argv) == 2 and sys.argv[0].startswith('default.'):
    # When called like `python default.Y.do X`
    base = sys.argv[1]
    target = sys.argv[0].replace('default.', base + '.').replace('.do', '')
    temp = target
    parent = Path(target).parent
    snippets = Snippets(base)
else:
    use_redo = False


def yaml_use_OrderedDict():
    import yaml

    def construct_OrderedDict(loader, node):
        loader.flatten_mapping(node)
        return OrderedDict(loader.construct_pairs(node))

    yaml.loader.Loader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_OrderedDict)

    def represent_OrderedDict(dumper, data):
        return dumper.represent_dict(list(data.items()))

    yaml.add_representer(OrderedDict, represent_OrderedDict,
                         yaml.dumper.Dumper)


yaml_use_OrderedDict()


class ReadData:

    def __init__(self, use_redo, ignore, args, kwargs):
        self.use_redo = use_redo
        self.ignore = ignore
        self.args = args
        self.kwargs = kwargs

    def read(self, arg):
        filenames, indices = self.linearize(arg)
        datas = self.read_list(filenames)
        return self.unlinearize(arg, indices, datas)

    def linearize(self, arg, offset=0):
        """Create a list of filenames from argument `arg`, and indices of the same
        structure as `arg` that point into the list."""
        if isinstance(arg, Path):
            filenames, indices = [str(arg)], offset
        elif type(arg) == str:
            filenames, indices = [arg], offset
        elif type(arg) in [tuple, list]:
            filenames, indices = [], []
            for child in arg:
                offset1 = offset + len(filenames)
                filenames1, indices1 = self.linearize(child, offset1)
                filenames += filenames1
                indices.append(indices1)
        elif type(arg) in [dict, OrderedDict]:
            filenames, indices = [], {}
            for key in arg:
                offset1 = offset + len(filenames)
                filenames1, indices1 = self.linearize(arg[key], offset1)
                filenames += filenames1
                indices[key] = indices1
        else:
            raise ValueError("Type " + str(type(arg)))
        return filenames, indices

    def unlinearize(self, arg, indices, datas):
        """Reconstruct `arg` with strings replaced by data from `data` according to
        `indices.`"""
        c = type(arg)
        if type(arg) == str or isinstance(arg, Path):
            return datas[indices]
        elif type(arg) in [tuple, list]:
            return c(self.unlinearize(arg1, indices1, datas)
                     for arg1, indices1 in zip(arg, indices))
        elif type(arg) in [dict, OrderedDict]:
            return c((key, self.unlinearize(arg[key], indices[key], datas))
                     for key in arg)

    def read_list(self, filenames):
        """Run `redo` on a list of filenames and return the list of generated file
        contents."""
        if self.use_redo:
            from shlex import quote
            command = 'redo-ifchange {}'.format(' '.join(quote(f) for f in filenames))
            value = os.system(command)
            if value != 0:
                sys.exit(value)
        results = []
        for filename in filenames:
            if self.ignore:
                result = None
            else:
                root, ext = os.path.splitext(filename)
                if ext == '':
                    result = None
                elif ext == '.txt':
                    with open(filename) as f:
                        result = f.readlines()
                elif ext == '.py':
                    from importlib import import_module
                    result = import_module(root.replace('/', '.'))
                elif ext == '.xls' or ext == '.xlsx':
                    import pandas as pd
                    result = pd.read_excel(filename, *self.args, **self.kwargs)
                elif ext == '.h5':
                    key = self.kwargs.pop('key')
                    import pandas as pd
                    result = pd.read_hdf(filename, key=key, *self.args, **self.kwargs)
                elif ext == '.json':
                    with open(filename) as f:
                        import json
                        kwargs = dict(self.kwargs)
                        if 'object_pairs_hook' not in self.kwargs:
                            kwargs['object_pairs_hook'] = OrderedDict
                        result = json.load(f, *self.args, **kwargs)
                elif ext == '.yaml':
                    with open(filename) as f:
                        import yaml
                        result = yaml.load(f, *self.args, **self.kwargs)
                elif ext == '.csv':
                    with open(filename) as f:
                        import pandas as pd
                        result = pd.read_csv(f, *self.args, **self.kwargs)
                elif ext == '.pickle':
                    with open(filename, 'rb') as f:
                        import pickle
                        result = pickle.load(f)
                else:
                    raise Exception("Unknown extension: "+ext)
            results.append(result)
        return results


def read_data(arg, *args, **kwargs):
    """Read data from the files in `arg` using their respective unserialization methods.

    `args` and `kwargs` are passed on to the unserialization methods.

    >>> df, lines = redo.read_data(("test.csv", "test.txt"))
    """
    return ReadData(False, False, args, kwargs).read(arg)


def ifchange(arg, *args, **kwargs):
    """Call redo-ifchange on the files in `arg` and reads their data using their respective unserialization methods.

    `args` and `kwargs` are passed on to the unserialization methods.

    >>> df, lines = redo.ifchange(("test.csv", "test.txt"))
    """
    return ReadData(use_redo, False, args, kwargs).read(arg)


def ifchange_ignore(arg):
    """Call redo-ifchange on the files in `arg`.

    >>> () = redo.ifchange_ignore(("test.csv", "test.txt"))
    """
    return ReadData(use_redo, True, [], {}).read(arg)


class WriteData:

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs

    def write_data(self, arg, output, target):
        _, ext = os.path.splitext(os.path.basename(target))
        if ext in ['.xls', '.xlsx']:
            import tempfile
            import shutil
            with tempfile.NamedTemporaryFile(suffix=ext) as f:
                arg.to_excel(f.name, *self.args, **self.kwargs)
                shutil.copyfile(f.name, output)
        elif ext == '.pickle':
            with open(output, 'wb') as f:
                import pickle
                pickle.dump(arg, f, *self.args, **self.kwargs)
        else:
            with open(output, 'w') as f:
                if ext == '.txt' or ext == '.log':
                    f.writelines(arg)
                elif ext == '.json':
                    import json
                    json.dump(arg, f, *self.args, **self.kwargs)
                elif ext == '.yaml':
                    import yaml
                    yaml.dump(arg, f, *self.args, **self.kwargs)
                elif ext == '.csv':
                    arg.to_csv(f, *self.args, **self.kwargs)
                elif ext == '.h5':
                    key = self.kwargs.pop('key')
                    arg.to_hdf(f, *self.args, key=key, mode='w', **self.kwargs)
                else:
                    raise Exception("Unknown extension: "+ext)


def write_data(arg, filename, *args, **kwargs):
    """Writes the data `arg` to a file `filename` using a matching serialization method.

    `args` and `kwargs` are passed to the serialization method.

    Example:

    >>> redo.write_data(df, "data.csv", index=False)"""
    WriteData(args, kwargs).write_data(arg, filename, filename)


def output(arg, *args, **kwargs):
    """Writes the data `arg` to the temporary file in the redo process

    Example:

    >>> redo.output(df, index=Fals)"""
    WriteData(args, kwargs).write_data(arg, temp, target)


def print(fmt, *args, **kwargs):
    s = fmt.format(*args, **kwargs) if args or kwargs else fmt
    builtins.print(">>", s, file=sys.stderr)


SEPARATORS = list('+$!')


def push(snippets, N):
    """
    >>> push(['abc'], 0)
    'abc'
    >>> push(['abc', 'def'], 0)
    'abc+def
    >>> push(['abc+def', 'ghi'], 0)
    'abc$def+ghi
    """
    def replace(s):
        for s1, s2 in reversed(list(zip(SEPARATORS[N:], SEPARATORS[N+1:]))):
            s = s.replace(s1, s2)
        return s
    return SEPARATORS[N].join(replace(s) for s in snippets)


def pop(snippet, N):
    """
    >>> pop('abc')
    ['abc']
    >>> pop('abc+def')
    ['abc', 'def']
    >>> pop('abc$def+ghi')
    ['abc+def', 'ghi']
    """
    def replace(s):
        for s1, s2 in reversed(list(zip(SEPARATORS[N+1:], SEPARATORS[N:]))):
            s = s.replace(s1, s2)
        return s
    return [replace(s) for s in snippet.split(SEPARATORS[0])]


def popjoin(snippet, N):
    return '.'.join(pop(snippet, N))


def exit(code):
    sys.exit(code)
