"""
Tools for fetching data from the URI online judge website 
(at http://https://www.urionlinejudge.com.br/).
"""
import re
import os
import shelve
import datetime
import itertools
import urllib.request
from collections import namedtuple, OrderedDict
from lxml import html as etree


# Constants
URLCACHE = None
URLCACHEPATH = os.path.expanduser('~/.uriurlcache.db')
Problem = namedtuple('Problem', 'id name ranking submission lang time date'.split())
__version__ = '0.1'


def urlcache():
    """Return the global url cache object. 
    
    It is a map from urls to data. The url cache is automatically replaced 
    after 1 day."""
    
    global URLCACHE
    if URLCACHE is None:
        URLCACHE = shelve.open(URLCACHEPATH)
    return URLCACHE
    

def urlopen(url, verbose=False):
    """Cached url opener"""
    
    cache = urlcache()
    try:
        if isinstance(cache[url], tuple):
            raise urllib.error.HTTPError(*cache[url])
        return cache[url]
    except KeyError:
        pass

    _condprint(verbose, '  Fetching url: %s...' % url)
    try:
        with urllib.request.urlopen(url) as F:
            data = F.read().decode('utf8')
    except urllib.error.HTTPError as ex:
        cache[url] = (url, ex.code, ex.msg, None, None)
        cache.sync()
        raise
    else:
        cache[url] = data
        cache.sync()
    return data


def view_problems(profile, verbose=False):
    """Extract all public information from the given profile"""
    
    problems = []
    urlbase = 'https://www.urionlinejudge.com.br/judge/pt/profile/%s/page:%s'
    
    for i in itertools.count(1):
        url = urlbase % (profile, i)
        parser = etree.HTMLParser()
        
        # Read html or break if encounter an error page
        try:
            data = urlopen(url, verbose=verbose)
            html = etree.fromstring(data, parser=parser)
        except urllib.error.HTTPError:
            break
        
        # Process table
        tbody = html.xpath('//table/tbody')[0]
        for tr in tbody:
            data = [x.text_content().strip() for x in tr]
            if not data[0] or len(data) == 1:
                break
            
            # Convert some columns..
            data[0] = int(data[0])                # problem profile
            data[2] = _ranking(data[2])           # ranking
            data[5] = float(data[5])              # time
            data[6] = _todatetime(data[6])        # date
            
            problem = Problem(*data)
            problems.append(problem)
            
    return problems


def filter_problems(problems, lang=None, ids=(), maxdate=None, mindate=None):
    """Filter problem list by some criteria"""
    
    problems = list(problems)
    ids = set(ids)

    if lang:
        problems = [p for p in problems if p.lang == lang]
    if ids:
        problems = [p for p in problems if p.id in ids]
    if maxdate:
        problems = [p for p in problems if p.date <= maxdate]
    if mindate:
        problems = [p for p in problems if p.date >= mindate]
        
    return problems


#
# Script interface
#
def main():
    """Execute as an script"""
    
    import argparse

    parser = argparse.ArgumentParser(description='Fetch data from students')
    
    parser.add_argument(
        'students', help='comma separated list of students ids or a CSV file with (student, URI id) columns')
    
    parser.add_argument(
        'problems', help='comma separated list of problems to be processed')
    
    parser.add_argument(
        '--lang', '-l',
        help='accepted languages')
    
    parser.add_argument(
        '--output', '-o',
        help='output format: check/count')
    
    parser.add_argument(
        '--sep', '-s',
        help='separation character')
    
    parser.add_argument(
        '--clear', '-c',
        help='clear url cache before proceeding',
        action='store_const', const=True)
    
    parser.add_argument(
        '--reverse', '-r',
        help='interpret each row in the students file as (URI id, name) instead of (name, URI id)',
        action='store_const', const=True)
    
    parser.add_argument(
        '--version', '-v',
        help='show program\'s version',
        action='version', version='uritool %s' % __version__)

    args = parser.parse_args()
    
    if args.clear:
        cache = urlcache()
        cache.clear()
        cache.sync()
        
    # Fetch all student problems
    sep = args.sep or ','
    students = OrderedDict()
    for name, uriid in _ids(args.students, args.reverse, sep):
        problems = students.setdefault(name, [])
        if uriid is not None:
            problems.extend(view_problems(uriid, verbose=True))
    
    # Filter by problem
    problems = None
    if args.problems != '*':
        problems = set(_problems(args.problems, sep))
        for L in students.values():
            L[:] = filter_problems(L, ids=problems)
            
    # Filter by language
    if args.lang:
        name = {
            # Python 2 aliases
            'python': 'Python', 'py': 'Python', 'python2': 'Python', 
            'Python2': 'Python', 'py2': 'Python', 
            
            # Python 3 aliases
            'python3': 'Python 3', 'py3': 'Python 3', 'Python3': 'Python 3',
            
            # C aliases
            'c': 'C',
            
            # C++ aliases
            'cpp': 'C++', 'Cpp': 'C++', 'c++': 'C++',
            
            # Java aliases
            'java': 'Java',
        }
        langs = args.lang.split(',')
        langs = [name.get(x, x) for x in langs]
        
        # Check if languages are valid
        delta = set(langs) - {'Python', 'Python 3', 'C', 'C++', 'Java'}
        if delta:
            raise SystemExit('invalid language: %r' % delta.pop())
        
        # Filter languages
        for L in students.values():
            L[:] = sum([filter_problems(L, lang=lang) for lang in langs], [])
    
    # Select correct output
    if args.output is None or args.output == 'check':
        print(csv_check(students))
    elif args.output == 'count':
        print(csv_count(students, problems))
    else:
        raise SystemExit('invalid output format: %r' % args.output)

    
#
# CSV outputs
#
def csv_check(D, problems=None):
    """From a mapping from students to problems, print a table with students
    as rows of zeros and ones telling which problems were solved"""
    
    problems = sorted(problems or _problemset(D))
    solvedmap = _solvedproblems(D) 

    data = ['id, '.rjust(27) + ', '.join(map(str, problems))]
    for st, solved in sorted(solvedmap.items()):
        line = [str(st).rjust(25)]
        for p in problems:
            if p in solved:
                line.append('   1')
            else:
                line.append('   0')
        data.append(', '.join(line))
            
    return unindent('\n'.join(data))
    
    
def csv_count(D, problems):
    """From a mapping from students to problems, print a table with students
    as rows with the counts of solved problems"""
    
    problems = sorted(problems or _problemset(D))
    solvedmap = _solvedproblems(D) 

    data = ['id, count'.rjust(32)]
    for st, solved in sorted(solvedmap.items()):
        line = [str(st).rjust(25), str(len(set(solved))).rjust(5)]
        data.append(', '.join(line))
            
    return unindent('\n'.join(data))


#
# Utility functions
#
def unindent(st):
    """Unindent data"""

    regex = re.compile(r'^\s*')
    lines = st.splitlines()
    indent = min([regex.match(line).end() for line in lines])
    return '\n'.join([line[indent:] for line in lines])


def _solvedproblems(D):
    solved = {}
    for student, L in D.items():
        solved[student] = set(p.id for p in L)
    return solved


def _problemset(D):
    problems = set()
    for L in D.values():
        for p in L:
            problems.add(p.id)
    return problems


def _todatetime(st):
    date, time = st.split('-')
    dd, mm, yy = map(int, date.split('/'))
    hh, mi, ss = map(int, time.split(':'))
    return datetime.datetime(yy, mm, dd, hh, mi, ss)


def _ranking(st):
    return int(st[:-1])


def _ids(data, reverse=False, sep=','):
    if data.replace(sep, '').isdigit():
        out = [(x, x) for x in map(int, data.split(sep))]
    else:
        namefirst = (reversed if reverse else iter)
        path = os.path.join(os.getcwd(), data)
        data = []
        with open(path) as F:
            for idx, line in enumerate(F.readlines()):
                words = line.split(sep)
                words = (words * 2 if len(words) == 1 else words)
                name, uri, *__ = namefirst(words)
                try:
                    uri = uri.strip()
                    uri = int(uri)
                except ValueError:
                    if not uri:
                        uri = None
                    elif idx != 0:
                        raise
                name = name.strip()
                data.append((name, uri))
        out = data
        
    return sorted(set(out))


def _problems(data, sep=','):
    if data.replace(sep, '').isdigit():
        return map(int, data.split(sep))
    else:
        cwd = os.getcwd()
        with open(os.path.join(cwd, data)) as F:
            data = F.read().replace(sep, ' ').split()
        return map(int, data)


def _condprint(verbose, *args, **kwds):
    if verbose:
        print(*args, **kwds)
    
    
if __name__ == '__main__':
    # Ex.: 3672, 3507
    import sys
    sys.argv = ['python', '3672,3507', '*', '--lang', 'python,python3,cpp,c', '-o', 'count']
    main()
