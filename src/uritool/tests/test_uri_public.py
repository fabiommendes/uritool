import pytest
from uritool import get_public_problems, get_public_profile


def test_public_profile():
    problems = get_public_problems(3507)
    print(problems)
    assert False


if __name__ == '__main__':
    pytest.main('test_uri_public.py -q')
