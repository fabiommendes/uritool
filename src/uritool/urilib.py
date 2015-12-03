"""
Tools for fetching data from the URI online judge website 
(at http://https://www.urionlinejudge.com.br/).
"""
import re
import datetime
import requests
import pandas as pd
import numpy as np
from collections import namedtuple, OrderedDict
from lxml import html as etree
from uritool.httpcache import htmlopen, urlcache, urlopen, urldate
from uritool.util import normalize_language
from uritool import config

# Constants
problem_fields = 'id name ranking submission lang time date'.split()
profile_fields = ('username university country solved tried submissions '
                  'ranking date').split()
Problem = namedtuple('Problem', problem_fields)
Profile = namedtuple('Profile', profile_fields)

__version__ = '0.2'


#
# Extract problems and information from the website
#
def get_public_problems(profile, verbose=True):
    """Extract public submissions from the given profile."""

    problems = []
    urlbase = ('https://www.urionlinejudge.com.br/judge/pt/profile/'
               '%s/page:%s/sort:run_id/direction:asc')
    refreshed = set()
    i = 0

    while True:
        i += 1
        url = urlbase % (profile, i)

        # Read html or break if encounter an error page
        try:
            html = htmlopen(url, verbose=verbose)
        except RuntimeError as ex:
            if ex.args[0] == 404:
                break
            raise

        # Process table
        tbody = html.xpath('//table/tbody')[0]
        transaction = []
        for tr in tbody:
            data = [x.text_content().strip() for x in tr]
            if not data[0] or len(data) == 1:
                break

            # Convert some columns..
            data[0] = int(data[0])  # problem profile
            data[2] = _ranking(data[2])  # ranking
            data[5] = float(data[5])  # time
            data[6] = _todatetime(data[6])  # date

            problem = Problem(*data)
            transaction.append(problem)

        # Add transaction to problem list
        if len(transaction) == 28:
            problems.extend(transaction)
        elif url not in refreshed:
            # Force refresh
            urlopen(url, verbose=verbose, expires=120)
            refreshed.add(url)
            i -= 1
        else:
            problems.extend(transaction)
            break

    # Create dataframe
    return pd.DataFrame(problems, columns=problem_fields)


def get_public_profile(profile, verbose=True):
    """View all non-problem related information in the public profile."""

    url = ('https://www.urionlinejudge.com.br/judge/pt/profile/'
           '%s/page:1/sort:run_id/direction:asc') % profile
    html = htmlopen(url, verbose=verbose)
    username = html.xpath('//div[@class="pb-username"]')[0].text_content()
    info = html.xpath('//ul[@class="pb-information"]/li')
    data = (x.text_content().strip() for x in info)
    data = (x.partition(':') for x in data)
    data = dict((k.lower(), v) for (k, _, v) in data)
    data['username'] = username

    # Make conversions
    dd, mm, yyyy = map(int, data.pop('desde').split('/'))
    data['date'] = datetime.date(yyyy, mm, dd)
    data['ranking'] = int(data.pop('posição')[:-1])
    data['solved'] = int(data.pop('resolvido'))
    data['submissions'] = int(data.pop('submissões'))
    data['tried'] = int(data.pop('tentado'))
    data['country'] = data.pop('país')
    data['university'] = data.pop('universidade').strip()
    return Profile(**data)


def get_detailed_progress(discipline, homework, username=None, password=None):
    """Retrieve a pandas data frame for a discipline/homework combination."""

    discipline = Discipline(discipline)
    return discipline.progress(homework)


def get_progress(discipline=None, username=None, password=None,
                 delay_penalty=None):
    """Retrieve a pandas data frame with the grades of all homeworks in the
    given disciplines.

    Parameters
    ----------

    discipline: int
        URI id for the desired discipline
    username, password: str
        Site credentials. It will use the authentication provided in the
        `uriconfig.ini` file, if not provided.
    delay_penalty : float
        Represents the fraction of the total grade that is discarded due to
        delayed submissions.

    Returns
    -------

    A data frame like the one bellow::

        uri_id   1234   2345    3456
        00001    0.00   0.00    0.00
        00002   52.94  50.00  100.00
        00003   70.58  75.00  100.00
        00004   82.35   0.00  100.00
        00005    5.88   0.00  100.00
          ...     ...    ...     ...

    The indexes in the first column correspond to URI ids. The name of each
    column correspond to a homework.
    """

    discipline = Discipline(discipline, username=username, password=password)

    if delay_penalty is None:
        return discipline.full_grades()
    delay_penalty = 1.0

    # Fetch all student responses
    student_problems = {id_: get_public_problems(id_)
                        for id_ in discipline.students.index}

    # Fetch graded homeworks and try to merge both
    homework_ids = discipline.homeworks.id
    data = [discipline.progress(id).fillna(0) for id in homework_ids]
    df = pd.DataFrame()
    for hw_id, homework in zip(homework_ids, data):
        problems = [int(col.partition(' ')[0]) for col in homework.columns]
        for idx, row in homework.iterrows():
            solved = set(p for p in problems if p in student_problems[idx])
            for p, result in row.items():
                if not result and p in solved:
                    row[p] = delayed_ratio * 100
        df[hw_id] = homework.mean(1)
    return df


#
# Utility functions
#
def filter_problems(problems, lang=None, ids=(), maxdate=None, mindate=None):
    """Filter problem list."""

    problems = list(problems)
    ids = set(ids)

    if lang:
        lang = normalize_language(lang)
        problems = [p for p in problems if p.lang == lang]
    if ids:
        problems = [p for p in problems if p.id in ids]
    if maxdate:
        problems = [p for p in problems if p.date <= maxdate]
    if mindate:
        problems = [p for p in problems if p.date >= mindate]

    return problems


#
# URI Academic
#
class Discipline:
    """Expose information from a single discipline in URI Academic."""

    def __init__(self, pk=None, username=None, password=None, verbose=False):
        self.pk = pk or config.uri_discipline
        self.username = username
        self.password = password
        self.verbose = verbose
        self.username = username or config.uri_username
        self.password = password or config.uri_password

    def __getattr__(self, attr):
        if attr in ['homeworks', 'students', 'title', 'professor']:
            self.__fetch_details()
            return getattr(self, attr)
        raise AttributeError(attr)

    #
    # Properties and attributes
    #
    @property
    def auth(self):
        return self.username, self.password

    @property
    def session(self):
        try:
            return self._session
        except AttributeError:
            if self.username is None or self.password is None:
                msg = 'cannot start session without username and password'
                raise RuntimeError(msg)
            self.login()
            return self._session

    @session.setter
    def session(self, value):
        self._session = value

    #
    # Public API
    #
    def login(self):
        """Login in Academic using the given credentials."""

        # Retrieve and parse data
        loginurl = 'https://www.urionlinejudge.com.br/academic/login'
        self.session = requests.session()
        request = self.session.get(loginurl)
        data = request.text
        parser = etree.HTMLParser()
        html = etree.fromstring(data, parser=parser)

        # Obtain CRSF data from form field
        token = html.xpath('//input[@name="data[_Token][key]"]')[0].value
        fields = html.xpath('//input[@name="data[_Token][fields]"]')[0].value
        unlocked = html.xpath('//input[@name="data[_Token][unlocked]"]')[
            0].value

        # Submit form
        payload = {
            '_method'                  : 'POST',
            'data[_Token][key]'        : token,
            'data[_Token][fields]'     : fields,
            'data[_Token][unlocked]'   : unlocked,
            'data[Professor][email]'   : self.username,
            'data[Professor][password]': self.password,
        }
        self.session.post(loginurl, data=payload)

    def progress(self, homework):
        """Return a table with the progress of each student in the chosen
        homework."""

        url = 'https://www.urionlinejudge.com.br/academic/homeworks/progress/%s'
        urldetail = 'https://www.urionlinejudge.com.br/academic/homeworks' \
                    '/view/%s'
        data = self.__htmlopen(url % homework)
        details = self.__htmlopen(urldetail % homework)

        # If deadline is not expired, reload a more recent version every 2 hours
        was_loaded = urldate(url % homework)
        deadline = data.xpath('//li[@class="box st-r"]/strong')[0]
        dd, mm = map(int, deadline.text_content().split('/'))
        deadline = datetime.datetime(was_loaded.year, mm, dd, 23, 59, 59)
        if was_loaded <= deadline:
            data = self.__htmlopen(url % homework, expire=120)
            details = self.__htmlopen(urldetail % homework, expire=120)

        # Extract question names
        question_to_name = {}
        rows = details.get_element_by_id('hw-list').xpath('tbody/tr')
        for row in rows:
            question_id = int(row[1].text_content())
            question_name = row[2].text_content().strip()
            question_to_name[question_id] = question_name

        # Get responses
        table = data.xpath('//div[@class="homeworks progess"]/table')[0]
        responses = []
        index = []
        for row in table[1:]:
            student_url = row[0].xpath('a')[0].attrib['href']
            student_id = int(student_url.rpartition('/')[-1])
            index.append(student_id)
            response = []

            for x in row[1:-1]:
                if x[0].attrib['class'] == 'void':
                    value = float('nan')
                elif x[0].attrib['class'] == 'tried':
                    value = 0
                elif x[0].attrib['class'] == 'solved':
                    value = 100
                else:
                    raise RuntimeError
                response.append(value)
            responses.append(response)

        # Valid header
        header = table[0]
        valid_cols = len(header) - sum(x.text_content() == '-' for x in header)
        valid_cols -= 2  # name/total
        header = [int(x.text_content()) for x in header[1:valid_cols + 1]]
        header = ['%s (%s)' % (id, question_to_name[id]) for id in header]
        responses = [row[:valid_cols] for row in responses]

        # Extact columns and make dataframe
        index = pd.Index(index, name='uri_id')
        return pd.DataFrame(np.array(responses), index=index, columns=header)

    def full_grades(self):
        """Return a table with the progress of each student in all homeworks
        in the given discipline."""

        df = pd.DataFrame(self.students['name'])
        for hw in self.homeworks.index:
            df[hw] = self.progress(hw).fillna(0).mean(1)
        return df

    #
    # Private utility methods
    #
    def __htmlopen(self, url, **kwds):
        if url in urlcache():
            return htmlopen(url, **kwds)
        else:
            return htmlopen(url, session=self.session, **kwds)

    def __fetch_details(self):
        """Fetch details from the first page."""

        def getdate(x):
            x = x.rpartition(' ')[0]
            return datetime.datetime.strptime(x, '%B %d, %Y %H:%M %p')

        url = 'https://www.urionlinejudge.com.br/academic/disciplines/view/%s'
        html = self.__htmlopen(url % self.pk, refresh=False)

        # Main details
        fields = html.xpath('//dl[@class="large"]/dd')
        fields = [x.text_content().strip() for x in fields]
        self.title = fields[0]
        self.professor = fields[1]
        self.date = getdate(fields[2])
        self.update = getdate(fields[3])

        # Homework list
        columns = 'id title deadline'.split()
        table = html.xpath('//div[@class="homeworks index"]/table')[0]
        data = [[x.text_content().strip() for x in row[1:4]]
                for row in table[1:]]
        self.homeworks = df = pd.DataFrame(data, columns=columns)
        df['deadline'] = [getdate(x) for x in df['deadline']]
        df.index = pd.Index([int(x) for x in df.pop('id')], name='id')

        # Students list
        columns = 'uri_id name terms permission accepted exercises ' \
                  'total'.split()
        table = html.xpath('//div[@class="homeworks index"]/table')[1]
        data = [[x.text_content().strip()
                 for x in row[1:8]] for row in table[1:]]
        self.students = df = pd.DataFrame(data, columns=columns)
        df.index = pd.Index([int(x) for x in df.pop('uri_id')], name='uri_id')
        del df['terms'], df['permission'], df['accepted']


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



if __name__ == '__main__':
    print(get_progress(delayed_ratio=0.5))
