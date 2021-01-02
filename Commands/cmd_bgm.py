import pathlib
import os
from glob import glob

def make_filetree(path, layer=0, is_last=False, indent_current='　', nest = -1):
    if (nest == 0):
        return ''
    if (nest == 1):
        is_last = True
    d = []
    if not pathlib.Path(path).is_absolute():
        path = str(pathlib.Path(path).resolve())

    # カレントディレクトリの表示
    current = path.split(os.sep)[::-1][0]
    d.append(pathlib.Path(current).parts[-1])
    if layer == 0:
        pass
        #print('<'+current+'>')
    else:
        branch = '└' if is_last else '├'
        #print('{indent}{branch}<{dirname}>'.format(indent=indent_current, branch=branch, dirname=pathlib.Path(current).parts[-1]))

    # 下の階層のパスを取得
    paths = [p for p in glob(path+'/*') if os.path.isdir(p) or os.path.isfile(p)]
    def is_last_path(i):
        return i == len(paths)-1

    # 再帰的に表示
    for i, p in enumerate(paths):

        indent_lower = indent_current
        if layer != 0:
            indent_lower += '　　' if is_last else '│　'

        if os.path.isfile(p):
            pass
            #branch = '└' if is_last_path(i) else '├'
            #print('{indent}{branch}{filename}'.format(indent=indent_lower, branch=branch, filename=os.path.splitext(os.path.basename(p))[0]))
        if os.path.isdir(p):
            d.append(make_filetree(p, layer=layer+1, is_last=is_last_path(i), indent_current=indent_lower, nest = nest-1))
        if (nest == 1):
            break
    return d

def depth(k):
    if not k:
        return 0
    else:
        if isinstance(k, list):
            return 1 + max(depth(i) for i in k)
        else:
            return 0