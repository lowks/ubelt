# -*- coding: utf-8 -*-
"""
NEEDS CLEANUP SO IT EITHER DOES THE IMPORTS OR GENERATES THE FILE, NOT BOTH
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import multiprocessing
import textwrap

def indent(str_, indent='    '):
    return indent + str_.replace('\n', '\n' + indent)


def __excecute_imports(module, modname, imports, verbose=False):
    """ Module Imports """
    # level: -1 is a the Python2 import strategy
    # level:  0 is a the Python3 absolute import
    if verbose:
        print('[UTIL_IMPORT] EXECUTING %d IMPORT TUPLES' % (len(imports),))
    level = 0
    for name in imports:
        if level == -1:
            tmp = __import__(name, globals(), locals(), fromlist=[], level=level)
        elif level == 0:
            # FIXME: should support unicode. Maybe just a python2 thing
            tmp = __import__(modname, globals(), locals(), fromlist=[str(name)], level=level)


def __execute_fromimport_star(module, modname, imports, ignore_list=[],
                              ignore_startswith=[], ignore_endswith=[],
                              check_not_imported=True, verbose=False,
                              veryverbose=False):
    r"""
    Effectively import * statements

    The dynamic_import must happen before any * imports otherwise it wont catch
    anything.

    Ignore:
        ignore_startswith = []
        ignore_endswith = []
        check_not_imported = False
        verbose = True
        veryverbose = True
    """
    if verbose:
        print('[UTIL_IMPORT] EXECUTE %d FROMIMPORT STAR TUPLES.' % (len(imports),))
    from_imports = []
    # Explicitly ignore these special functions (usually stdlib functions)
    # FIXME: find a better way to do this
    ignoreset = set(['print', 'print_function', 'absolute_import', 'division',
                     'zip', 'map', 'range', 'list', 'zip_longest', 'filter',
                     'filterfalse', 'dirname', 'realpath', 'join', 'exists',
                     'normpath', 'splitext', 'expanduser', 'relpath', 'isabs',
                     'commonprefix', 'basename', 'input', 'reduce',
                    ] + ignore_list)

    for name in imports:
        #absname = modname + '.' + name
        child_module = sys.modules[modname + '.' + name]
        # Check if the variable already belongs to the module
        varset = set(vars(module)) if check_not_imported else set()
        fromset = set()  # set(fromlist) if fromlist is not None else set()
        def valid_attrname(attrname):
            """
            Guess if the attrname is valid based on its name
            """
            is_forced  = attrname in fromset
            is_private = attrname.startswith('_')
            is_conflit = attrname in varset
            is_module  = attrname in sys.modules  # Isn't fool proof (next step is)
            is_ignore1 = attrname in ignoreset
            is_ignore2 = any([attrname.startswith(prefix) for prefix in ignore_startswith])
            is_ignore3 = any([attrname.endswith(suffix) for suffix in ignore_endswith])
            is_ignore  = any((is_ignore1, is_ignore2, is_ignore3))
            is_valid = not any((is_ignore, is_private, is_conflit, is_module))
            #is_valid = is_valid and is_defined_by_module2(getattr(child_module, attrname), child_module)
            return (is_forced or is_valid)
        allattrs = dir(child_module)
        fromlist_ = [attrname for attrname in allattrs if valid_attrname(attrname)]
        #if verbose:
        #    print('[UTIL_IMPORT]     name=%r, len(allattrs)=%d' % (name, len(allattrs)))
        #if verbose:
        #    print('[UTIL_IMPORT]     name=%r, len(fromlist_)=%d' % (name, len(fromlist_)))
        valid_fromlist_ = []
        for attrname in fromlist_:
            attrval = getattr(child_module, attrname)
            try:
                # Disallow fromimport modules
                forced = attrname in fromset
                if not forced and getattr(attrval, '__name__') in sys.modules:
                    if veryverbose:
                        print('[UTIL_IMPORT] not importing: %r' % attrname)
                    continue
            except AttributeError:
                pass
            if veryverbose:
                print('[UTIL_IMPORT] %s is importing: %r' % (modname, attrname))
            valid_fromlist_.append(attrname)
            setattr(module, attrname, attrval)
        if verbose:
            print('[UTIL_IMPORT]     name=%r, len(valid_fromlist_)=%d' % (name, len(valid_fromlist_)))
        from_imports.append((name, valid_fromlist_))
    return from_imports


def _initstr(modname, imports, from_imports, withheader=True):
    """ Calls the other string makers """
    header         = _make_module_header() if withheader else ''
    import_str     = _make_imports_str(imports, modname)
    fromimport_str = _make_fromimport_str(from_imports, modname)
    initstr = '\n'.join([str_ for str_ in [
        header,
        import_str,
        fromimport_str,
    ] if len(str_) > 0])
    return initstr

def _make_module_header():
    return '\n'.join([
        '# flake8: noqa',
        'from __future__ import absolute_import, division, print_function, unicode_literals'])

def _make_imports_str(imports, rootmodname='.'):
    imports_fmtstr = 'from {rootmodname} import %s'.format(
        rootmodname=rootmodname)
    return '\n'.join([imports_fmtstr % (name,) for name in imports])

def _make_fromimport_str(from_imports, rootmodname='.'):
    if rootmodname == '.':
        # dot is already taken care of in fmtstr
        rootmodname = ''
    def _pack_fromimport(tup):
        name, fromlist = tup[0], tup[1]
        from_module_str = 'from {rootmodname}.{name} import ('.format(
            rootmodname=rootmodname, name=name)
        newline_prefix = (' ' * len(from_module_str))
        if len(fromlist) > 0:
            rawstr = from_module_str + ', '.join(fromlist) + ',)'
        else:
            rawstr = ''

        # not sure why this isn't 76? >= maybe?
        import textwrap
        packstr = '\n'.join(textwrap.wrap(rawstr, break_long_words=False,
                                          width=79, initial_indent='',
                                          subsequent_indent=newline_prefix))
        return packstr
    from_str = '\n'.join(map(_pack_fromimport, from_imports))
    return from_str

def dynamic_import(modname, imports, ignore_froms=[],
                   dump=False, ignore_startswith=[], ignore_endswith=[],
                   ignore_list=[], check_not_imported=True, verbose=False):
    """
    MAIN ENTRY POINT

    Dynamically import listed util libraries and their attributes.
    Create reload_subs function.

    Using __import__ like this is typically not considered good style However,
    it is better than import * and this will generate the good file text that
    can be used when the module is 'frozen"
    """
    if verbose:
        print('[UTIL_IMPORT] Running Dynamic Imports for modname=%r ' % modname)
    # Get the module that will be imported into
    try:
        module = sys.modules[modname]
    except:
        module = __import__(modname)
    # Import the modules
    __excecute_imports(module, modname, imports, verbose=verbose)
    # If developing do explicit import stars
    from_imports = __execute_fromimport_star(module, modname, imports,
                                             ignore_list=ignore_list,
                                             ignore_startswith=ignore_startswith,
                                             ignore_endswith=ignore_endswith,
                                             check_not_imported=check_not_imported,
                                             verbose=verbose)

    # If requested: print what the __init__ module should look like
    dump_requested = (('--dump-%s-init' % modname) in sys.argv or
                      ('--print-%s-init' % modname) in sys.argv) or dump
    overwrite_requested = ('--update-%s-init' % modname) in sys.argv
    if verbose:
        print('[UTIL_IMPORT] Finished Dynamic Imports for modname=%r ' % modname)

    if dump_requested:
        is_main_proc = multiprocessing.current_process().name == 'MainProcess'
        if is_main_proc:
            initstr = _initstr(modname, imports, from_imports)
            print(indent(initstr))
    # Overwrite the __init__.py file with new explicit imports
    if overwrite_requested:
        is_main_proc = multiprocessing.current_process().name == 'MainProcess'
        if is_main_proc:
            from os.path import join, exists
            initstr = _initstr(modname, imports, from_imports, withheader=False)
            new_else = indent(initstr)
            #print(new_else)
            # Get path to init file so we can overwrite it
            init_fpath = join(module.__path__[0], '__init__.py')
            print('attempting to update: %r' % init_fpath)
            assert exists(init_fpath)
            new_lines = []
            editing = False
            updated = False
            #start_tag = '# <AUTOGEN_INIT>'
            #end_tag = '# </AUTOGEN_INIT>'
            with open(init_fpath, 'r') as file_:
                #text = file_.read()
                lines = file_.readlines()
                for line in lines:
                    if not editing:
                        new_lines.append(line)
                    if line.strip().startswith('# <AUTOGEN_INIT>'):
                        new_lines.append('\n' + new_else + '\n    # </AUTOGEN_INIT>\n')
                        editing = True
                        updated = True
                    if line.strip().startswith('# </AUTOGEN_INIT>'):
                        editing = False
            if updated:
                print('writing updated file: %r' % init_fpath)
                new_text = ''.join(new_lines)
                with open(init_fpath, 'w') as file_:
                    file_.write(new_text)
            else:
                print('no write hook for file: %r' % init_fpath)
