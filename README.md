BitMEX Market Maker
===================

To get started:

1. Copy settings.py.example to settings.py
2. Edit settings.py to add your BitMEX username and password and change bot parameters.
  * Run with DRY_RUN=True to test cost and spread.
  3. Set up dependencies: `python setup.py install`
  4. Run it: `python market-maker.py [symbol]`


Based on [liquidbot](https://github.com/chrisacheson/liquidbot).

API Keys
--------

The BitMEX Market Maker bot now supports API Keys. Support for generating keys will be in the BitMEX UI soon,
but until it is, you can generate and manage them by executing the `generate-api-key.py` script in this directory.
