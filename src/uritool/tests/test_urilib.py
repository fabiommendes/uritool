import pytest
import datetime
from uritool import httpcache
from uritool.urilib import get_public_problems, get_public_profile, Discipline


TEST_PROFILE = 3507
TEST_DISCIPLINE = 1088


def test_public_problems():
    problems = get_public_problems(3507)
    min_problems = {1001, 1003, 1187, 1002, 1036, 1010, 1078, 1004, 1018, 1253}
    assert min_problems.issubset(problems.index)
    assert list(problems.columns) == ['name', 'ranking', 'submission', 'lang',
                                      'time', 'date']


def test_public_profile():
    profile = get_public_profile(3507)
    assert profile.username == 'Fábio Macedo Mendes'
    assert profile.university == 'UnB-Gama'
    assert profile.country == 'BRA'
    assert profile.solved >= 10
    assert profile.tried >= 10
    assert profile.submissions >= 20
    assert profile.ranking >= 100
    assert profile.date == datetime.date(2013, 4, 5)


def test_fetch_discipline():
    discipline = Discipline(TEST_DISCIPLINE)
    assert 3703 in discipline.homeworks.index


def test_invalid_login_raise_error():
    discipline = Discipline(1234, username='foo', password='bar')
    with pytest.raises(ConnectionError):
        print(discipline.homeworks)



if __name__ == '__main__':
    pytest.main('test_urilib.py -q')
