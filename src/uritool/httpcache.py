"""
Retrieve and cache data from urls.
"""
import requests
import shelve
import datetime
from lxml import html as etree
from . import config
from .util import debug_print

# URL Cache
URLCACHE = None
URLCACHEPATH = config.urlcache
MINUTE_DELTA = datetime.timedelta(minutes=1)
INTERNET_SLOW = False


def urlcache():
    """Return the global url cache object.

    It is a map from urls to data. The url cache is automatically replaced
    after 1 day."""

    global URLCACHE
    if URLCACHE is None:
        URLCACHE = shelve.open(URLCACHEPATH)
    return URLCACHE


def urlsave(url, data):
    """Saves data for given url in cache."""

    cache = urlcache()
    cache[url] = datetime.datetime.now(), data
    cache.sync()


def urlrefresh(url, *args, **kwds):
    """Refresh chache for the given url."""

    cache = urlcache()
    del cache[url]
    urlopen(url, *args, **kwds)


def urldate(url):
    """Return the date for the url saved in cache."""

    try:
        return urlcache()[url][0]
    except KeyError:
        return None


def urlopen(url, verbose=True, refresh=False, session=requests, expires=None,
            **kwds):
    """Cached url opener. Return a string of data."""

    global INTERNET_SLOW

    # Retrieve from cache
    cache = urlcache()
    cdate, data = cache.get(url, (None, None))
    if refresh:
        pass
    elif isinstance(data, int):
        raise RuntimeError(data, url)
    elif data is not None:
        if expires is None or INTERNET_SLOW:
            return data
        else:
            delta = datetime.datetime.now() - cdate
            if delta <= MINUTE_DELTA * expires:
                return data

    # Download data from the given url
    debug_print(verbose, '  Fetching url: %s' % url)
    timeout = 10 if url in cache else 30
    try:
        request = session.get(url, timeout=timeout, **kwds)
    except:
        INTERNET_SLOW = True
        if url in cache:
            debug_print(verbose, '  Internet too slow: using cache.')
        else:
            raise
    data = request.status_code if request.status_code != 200 else request.text
    urlsave(url, data)
    return data


def htmlopen(url, *args, **kwds):
    """Like urlopen(), but returns parsed HTML."""

    parser = etree.HTMLParser()
    data = urlopen(url, *args, **kwds)
    return etree.fromstring(data, parser=parser)
