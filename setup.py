import setuptools
from setuptools import setup

VERSION = '0.1'
AUTHOR = 'Fábio Macêdo Mendes'

#
# Main configuration script
#
setup(
    name='uritool',
    version=VERSION,
    description='Extract data from the URI Online Judge website at https://www.urionlinejudge.com.br/',
    author='Fábio Macêdo Mendes',
    author_email='fabiomacedomendes@gmail.com',
    url='https://github.com/fabiommendes/uritool/',
    long_description=(
        r'''Extract data from URI website and grade the submissions by your
        students.'''),

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries',
    ],

    package_dir={'': 'src'},
    packages=setuptools.find_packages('src'),
    license='GPL',
    install_requires=['lxml'],
    
    #
    # Scripts
    #
    entry_points={
        'console_scripts': ['uritool = uritool.__main__:main'],
    },
    zip_safe=False,
)

