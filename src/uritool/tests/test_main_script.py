import pytest
from uritool.__main__ import main, run, argparser


def test_main_show_display():
    run('3507', '1001')


if __name__ == '__main__':
    pytest.main('test_main_script.py -q')
