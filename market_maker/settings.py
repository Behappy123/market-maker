from __future__ import absolute_import
import os
import sys
from market_maker.utils.dotdict import dotdict
import market_maker._settings_base as baseSettings
from imp import reload


def import_path(fullpath):
    """
    Import a file with full path specification. Allows one to
    import from anywhere, something __import__ does not do.
    """
    path, filename = os.path.split(fullpath)
    filename, ext = os.path.splitext(filename)
    sys.path.insert(0, path)
    module = __import__(filename)
    reload(module)  # Might be out of date
    del sys.path[0]
    return module

userSettings = import_path(os.path.join('..', 'settings'))
symbolSettings = None
symbol = sys.argv[1] if len(sys.argv) > 1 else None
if symbol:
    print("Importing symbol settings for %s..." % symbol)
    try:
        symbolSettings = import_path(os.path.join('..', 'settings-%s' % symbol))
    except Exception as e:
        print("Unable to find settings-%s.py." % symbol)

# Assemble settings.
settings = {}
settings.update(vars(baseSettings))
settings.update(vars(userSettings))
if symbolSettings:
    settings.update(vars(symbolSettings))

# Main export
settings = dotdict(settings)
