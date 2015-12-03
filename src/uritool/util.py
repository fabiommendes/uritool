def fetch_students(spec):
    """Return a list of students from the given spec."""

    return spec


def fetch_problems(spec):
    """Return a list of problems from the given spec."""

    return spec


def debug_print(verbose, *args, **kwds):
    """Print if verbose argument is True."""

    if verbose:
        print(*args, **kwds)


def normalize_language(lang):
    """Normalize language specifications for the URI online judge."""

    aliases = {
        # Python 2 aliases
        'Python'  : 'Python',
        'python'  : 'Python',
        'py'      : 'Python',
        'python2' : 'Python',
        'Python2' : 'Python',
        'py2'     : 'Python',

        # Python 3 aliases
        'Python 3': 'Python 3',
        'python3' : 'Python 3',
        'py3'     : 'Python 3',
        'Python3' : 'Python 3',

        # C aliases
        'C'       : 'C',
        'c'       : 'C',

        # C++ aliases
        'C++'     : 'C++',
        'cpp'     : 'C++',
        'Cpp'     : 'C++',
        'c++'     : 'C++',

        # Java aliases
        'Java'    : 'Java',
        'java'    : 'Java',
    }
    try:
        lang = aliases[lang]
    except KeyError:
        raise SystemExit('invalid language: %r' % lang)
