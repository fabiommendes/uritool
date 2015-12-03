import sys
import os
import argparse
from . import config


def grade_sub_parser(subparser):
    parser = subparser('grade', help='performs a manual grading job')
    parser.add_argument(
        'exam',
        help='name of the homework/exam that needs to be graded',
    )
    parser.add_argument(
        '--reset', '-r',
        help='resets all grades for the given exam, if they already exists.',
        action='store_const', const=True,
    )
    return parser


def uri_academic_sub_parser(subparser):
    parser = subparser('uri-academic', help='fetch data from uri academic')
    parser.add_argument(
        '--auth', '-a',
        help='authentication string in the form of username:password.',
    )
    parser.add_argument(
        '--discipline', '-d',
        help='discipline code in URI academic.',
    )
    parser.add_argument(
        '--silent', '-s',
        help='run silently',
        action='store_const', const=True,
    )
    parser.add_argument(
        '--delay-penalty', '-p',
        help='if given, delayed submissions will be accepted, but will receive'
             'the given penalty. It must be in the 0-100 range.'
    )
    return parser


def compile_sub_parser(subparser):
    parser = subparser('compile',
                       help='compile all data into the main.csv file.')

    # parser.add_argument(
    #    '--pdf',
    #    help='also saves data as pdf',
    # )
    # parser.add_argument(
    #    '--ods',
    #    help='also saves data as an openoffice spreadsheet',
    # )
    return parser


def full_parser():
    """Return the argparser for the main program."""

    from uritool import __version__

    parser = argparse.ArgumentParser(description='Fetch data from students')
    parser.add_argument(
        '--clear', '-c',
        help='clear url cache before proceeding',
        action='store_const', const=True
    )
    parser.add_argument(
        '--version', '-v',
        help='show program\'s version',
        action='version', version='uritool %s' % __version__
    )
    subparsers = parser.add_subparsers(dest='command')
    grade_sub_parser(subparsers.add_parser)
    uri_academic_sub_parser(subparsers.add_parser)
    compile_sub_parser(subparsers.add_parser)
    return parser


def main(args=None):
    """Load arguments and execute as an script"""

    # Special arguments
    if '--clear' in sys.argv:
        if os.path.exists(config.urlcache):
            os.unlink(config.urlcache)
        return

    parser = full_parser()
    args = parser.parse_args(args)

    # Infers the type of subparser and process it
    actions = {
        'grade'       : run_grade_command,
        'compile'     : run_compile_command,
        'uri-academic': run_uri_academic_command,
    }
    try:
        action = actions[args.command]
        kwds = vars(args)
        del kwds['command'], kwds['clear']
    except KeyError:
        parser.print_usage()
    else:
        action(**kwds)


#
# Action runners
#
def run_grade_command(exam, reset=False):
    from .grader import Grader

    main_csv = get_main_csv()
    students = dict(zip(main_csv.index, main_csv['name']))
    grader = Grader(students, path='exam-%s.csv' % exam)
    if reset:
        grader.data['grade'] = float('nan')
    grader.run()


def run_compile_command(pdf=False):
    main_csv = make_main_csv()
    save_main_csv(main_csv)
    if pdf:
        save_main_pdf(main_csv)


def run_uri_academic_command(discipline, auth=None, silent=False,
                             delay_penalty=None):
    import pandas as pd
    from . import urilib

    # Get valid authentication
    auth = auth or ':'
    username, password = auth.split(':')
    username = username or config.uri_username
    password = password or config.uri_password
    discipline = int(discipline or config.uri_discipline)
    if not (username and password and discipline):
        msg = ('\n'
               '    Must provide username:password and discipline.\n'
               '    Edit uriconfig.ini to set default values.')
        raise SystemExit(msg)

    # Fetch from academic and print
    table = urilib.get_progress(discipline=discipline,
                                username=username,
                                password=password,
                                delay_penalty=delay_penalty)
    table = table.drop(config.uri_ignore_ids)

    # Synchronize with students.csv
    students = students_csv()
    is_bad = table.index.isin(students['uri id']) != True

    # Check if there is any unknown student
    if any(is_bad) and False:
        bad = table[is_bad]
        print(
            '\nError: these URI ids were not found in students.csv!\n'
            'Either remove them from your discipline or setup the ignore_ids\n'
            'variable in the [uri] section of uriconfig.ini.'
        )
        print(bad)
        raise SystemExit(0)

    # Align data by student id
    align = pd.DataFrame(students.index, index=students['uri id'])
    table, align = table.align(align, axis=0)
    table['uri id'] = list(table.index)
    table['id'] = align.iloc[:, 0]
    data = table.as_matrix()

    # Recreate data frame from aligned tabular data.
    # Remove the last column to be the index
    index = data[:, -1]
    data = data[:, :-1]
    columns = list(table.columns)[:-1]
    table = pd.DataFrame(data, index=index, columns=columns)

    # Use names from students.csv
    table['name'] = students['name']

    # Reorganize rows and columns in a better order
    table.sort_index(inplace=True)
    columns = list(table.columns)
    columns.insert(1, columns.pop())
    table = table[columns]

    # FIXME: save with backup
    table.to_csv('uri.csv')

    # Print table
    if not silent:
        print('TABLE HEAD\n==========')
        print(table.head())
        print('...\n')
        print('TABLE TAIL\n==========')
        print(table.head())


#
# Utilities
#
def get_main_csv():
    """Return a DataFrame holding data of the main.csv file"""

    import pandas as pd

    try:
        df = pd.read_csv('main.csv')
    except FileNotFoundError:
        index = pd.Series([], name='id')
        return pd.DataFrame([], index=index)
    df.index = df['id']
    return df


def save_main_csv(df):
    """Saves main data frame in the main.csv file."""

    df.to_csv('main.csv')


def save_main_pdf(df):
    """Saves a dataframe as a pdf file."""

    raise NotImplementedError


def make_main_csv():
    """Return a data frame with the collected content for the main.csv file."""

    import pandas as pd

    # Start with an empty data frame
    index = pd.Series([], name='id')
    main_df = pd.DataFrame([], index=index)

    # Collect all exams
    files = [f for f in os.listdir(os.getcwd())
             if f.startswith('exam-') and f.endswith('.csv')]
    for f in files:
        name = f[5:-4]
        df = pd.read_csv(f)
        df.index = df['id']
        main_df[name] = df['grade']

    # Collect all data from URI academic
    # ...
    return main_df


def students_csv():
    """Return a data frame with data in students.csv."""

    import pandas as pd

    try:
        df = pd.read_csv('students.csv')
    except OSError:
        index = pd.Series([], name='id')
        df = pd.DataFrame({
                              'name'  : [],
                              'uri id': []
                              }, index=index)
        df.to_csv('students.csv')
        return df
    df.index = df['id']
    if 'name' not in df:
        df['name'] = [str(x) for x in df.index]
    if 'uri id' not in df:
        df['uri id'] = float('nan')
    return df


if __name__ == '__main__':
    main()
