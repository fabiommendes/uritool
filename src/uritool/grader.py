import os
from decimal import Decimal, InvalidOperation
from datetime import datetime
import pandas as pd

# Names
__all__ = ['Grade', 'Grader']


class CancelOperation(Exception):
    """Cancel the current operation and go back to a nice starting point."""


class FinishGrading(Exception):
    """Finish the grading job."""


class ValidationError(Exception):
    """Exception raised for failed validations."""


class Grader:
    """Simple command line tool that helps registering grades of lots of
    students.

    After the Grader is initialized, its `.run()` method should be called in
    order to start the grading process.

    Parameters
    ----------

    students : dict
        A dictionary mapping student ids to their corresponding names.
    validate_grade : callable
        A validation function that takes a Grade object as input and return
        the validated grade or raises a ValidationError.
    validate_id : callable
        A validation function that takes an id string as input and return the
        validated pair (id, name) or raises a ValidationError. The user can
        also pass a type such as int or str and it will correctly validate
        the inputs as the desired type.
    path : str
        Path to a CSV file that holds grading data for the given job. This file
        must have a
    """

    def __init__(self, students={}, validate_grade=None, validate_id=str,
                 path=None):
        # Create dataframe from students dict
        data = [(x, str(y or x)) for (x, y) in students.items()]
        data.sort(key=lambda x: x[0])
        index = pd.Series([x[0] for x in data], name='id')
        names = [str(x[1]) for x in data]
        self.data = pd.DataFrame({
                                     'name': names
                                     }, index=index)

        # Add extra columns
        search = ['%s %s' % (x.casefold(), y) for (x, y) in zip(names, index)]
        self.data['__search'] = search
        self.data['grade'] = float('nan')
        self.data['timestamp'] = datetime.now()

        # Register validators
        self.validate_grade = self.__auto_validate_grade()
        self.validate_id = self.__auto_validate_id(validate_id)

        # Saves path and a backup
        self.path = path
        if path is not None:
            if os.path.exists(path):
                self.update_from_path(path)
                self.save_backup(path)
            self.save_to_path(path)

    def update_from_path(self, path):
        """Update the grading Job contents from the given file.

        It expects that the file holds data in a CSV format with a single header
        row and the following columns:

          id           name grade                  timestamp
        1234    John Lennon   9.0 2015-11-27 08:49:25.345277
        4321 Paul McCartney   9.5 2015-11-27 08:49:30.323211

        The columns id and grade are obligatory. The grader will always save
        columns in the order above, but it can load files with columns on any
        order. If the CSV file has additional columns, they will be preserved
        and new rows will be filled with nan's.

        """

        df = pd.read_csv(path)
        df.index = df.pop('id')

        # Set default 'timestamp' and 'auto' columns
        try:
            df['timestamp'] = pd.DatetimeIndex(df['timestamp'])
        except KeyError:
            df['timestamp'] = self._zero.timestamp

        # Normalize search
        if 'name' not in df:
            df['name'] = [str(x) for x in df.index]

        # Normalize __search column
        df['__search'] = ['%s (%s)' % (x.casefold(), y)
                          for (x, y) in zip(df['name'], df.index)]

        # Update data
        self.data = self.data.align(df)[0]
        self.data.update(df)

    def save_to_path(self, path):
        """Save a report in the given file."""

        self.report().to_csv(path)

    def save(self):
        """Save progress, if Grader keeps track of a file."""

        if self.path is not None:
            self.save_to_path(self.path)

    def report(self):
        """Return a data frame with the grading job result."""

        df = self.data.copy()
        del df['__search']
        return df

    def run(self):
        """Grader's mainloop."""

        while True:
            try:
                self.step()
                self.save()
            except FinishGrading:
                break

        if input('See grades? [Y/n] ').casefold() in ['y', '']:
            print(self.report())

    def step(self):
        """Evaluate a single student.

        This performs a single step in the application's mainloop."""

        try:
            student_id = self.select()
            student_name = self.data.loc[student_id, 'name']
            grade = self.get_value('%s (%s)' % (student_name, student_id))
        except CancelOperation:
            print('---')
            return self.step()

        row = self.data.loc[student_id]
        if pd.isnull(row['grade']):
            self.data.loc[student_id, 'grade'] = grade
            self.data.loc[student_id, 'timestamp'] = datetime.now()
        else:
            if grade == row['grade']:
                pass
            else:
                msg = '"%s" was already graded as %s. Overwrite? [y/N] '
                response = input(msg % (row['name'], row['grade']))
                if response.casefold() == 'y':
                    self.data.loc[student_id, 'grade'] = grade
                    self.data.loc[student_id, 'timestamp'] = datetime.now()
                    return print('---')
        print('grade registered!')
        print('---')

    def get_value(self, name='student'):
        """Fetches a valid grade from the user."""

        value = self.validate_grade(input('Grade %s: ' % name))
        if not value:
            raise CancelOperation
        while True:
            try:
                return self.validate_grade(value)
            except (InvalidOperation, ValidationError):
                value = input('Bad value, try again: ')
                if not value:
                    raise CancelOperation

    def select(self):
        """Select a valid student."""

        # Select a student name
        student = input("Student: ")
        if not student:
            student = input('Bad student name, try again: ')
        if not student:
            response = input('Do you want to leave? [Y/n] ')
            if response.casefold() in ['y', '']:
                raise FinishGrading


            else:
                return self.select()

        # Match name with list
        matches = self.matches(student)
        if not matches:
            response = input('Not found!\nWant to add it [y/N]? ')
            if response.casefold() == 'y':
                return self.add_student(student)
            else:
                raise CancelOperation
        else:
            result = self.pick_result(matches)
        return result

    def pick_result(self, matches):
        """Ask the user for a valid student from a list of `matches`."""

        if len(matches) == 1:
            return matches[0]

        # Display options
        for i, match in enumerate(matches):
            descr = '%s (%s)' % (self.data['name'][match], match)
            print('    %s) %s' % (i + 1, descr))
        print('    Or press <enter> to restart or <0> to type a new id')
        response = input('Choose one: ')

        # User wants to restart
        if not response:
            return self.step()

        # User wants to type a new school id
        if response == '0':
            student = input('Name (id): ')
            return self.add_student(student)

        # Check user input
        while True:
            try:
                selection = int(response) - 1
            except ValueError:
                pass
            else:
                try:
                    return matches[selection]
                except IndexError:
                    pass
            response = input('Bad response, try again: ')

    def matches(self, value):
        """Return a list of all student ids that matches the given query."""

        value = value.casefold()
        data = zip(self.data.index, self.data['__search'])
        return [idx for (idx, name) in data if value in name]

    def add_student(self, student):
        """Add student id to the database and return its complete name."""

        while True:
            try:
                name, id_ = self.validate_id(student)
                break
            except ValidationError:
                student = input('Type name (id): ')

        if id_ in self.data.index:
            print('student already exists!')
        else:
            row = pd.DataFrame({
                'name'     : name,
                '__search' : '%s %s' % (name.casefold(), id_),
                'timestamp': datetime.now(),
            }, index=[id_])
            self.data = self.data.append(row)
            self.data.sort_index(inplace=True)
        return id_

    def save_backup(self, path):
        """Choose a proper .bak-X file to save. Cycle 5 times at most."""

        basepath, basename = os.path.split(os.path.abspath(path))
        basepath = os.path.join(basepath, 'backup')

        if not os.path.exists(basepath):
            os.mkdir(basepath)

        for idx in range(5):
            bak_name = os.path.join(basepath, '%s.bak-%s' % (path, idx))
            if not os.path.exists(bak_name):
                break
        else:
            for idx in range(4):
                src = os.path.join(basepath, '%s.bak-%s' % (path, idx + 1))
                dest = os.path.join(basepath, '%s.bak-%s' % (path, idx))
                os.rename(src, dest)

        with open(path) as source:
            with open(bak_name, 'w') as destination:
                destination.writelines(source)

    def __auto_validate_id(self, id_type=str):
        """Return a automatically created validation function for id fields.

        If id_type is given and is a type, it simply apply id_type() to the
        input and return the result. Raises a validation error if conversion
        is not possible.
        """

        def validate(idstr):
            idstr = idstr.strip()

            if '(' in idstr and idstr.endswith(')'):
                name, _, id_ = idstr.partition('(')
                name = name.strip()
                id_ = id_[:-1].strip()
                try:
                    id_ = id_type(id_)
                except:
                    raise ValidationError('invalid "name (id)": %s' % idstr)
            else:
                try:
                    name = idstr
                    id_ = id_type(idstr)
                except:
                    raise ValidationError('invalid id: %s' % idstr)

            return name, id_

        return validate

    def __auto_validate_grade(self):
        def validator(x):
            try:
                return Decimal(x)
            except ValueError:
                raise ValidationError

        return validator
