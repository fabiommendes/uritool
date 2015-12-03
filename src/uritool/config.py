def _read_config():
    """Read configuration in .uriconfig.ini."""

    import configparser
    import os

    basepath = os.getcwd()
    prev = None
    while basepath != prev:
        prev = basepath
        path = os.path.join(basepath, 'uriconfig.ini')
        if os.path.exists(path):
            break
        basepath = os.path.split(basepath)[0]

    parser = configparser.ConfigParser()
    parser.read(path)
    return parser


#
# Load config constants
#
_config = _read_config()

# URI section
uri_username = _config.get('uri', 'username', fallback=None)
uri_password = _config.get('uri', 'password', fallback=None)
uri_discipline = _config.get('uri', 'discipline', fallback=None)
uri_ignore_ids = _config.get('uri', 'ignore_ids', fallback='')
uri_ignore_ids = list(map(int, uri_ignore_ids.split(',')))

# Generic sections
urlcache = _config.get('conf', 'urlcache', fallback='urlcache.db')
