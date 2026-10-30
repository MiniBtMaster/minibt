"""``prepare_qt`` — pick a Qt binding and load QtWebEngineWidgets in time.

This is the one piece of the old ``pylightcharts.qtcharts`` package worth keeping:
it is not a widget, it just solves an import-order problem.

Qt refuses to import ``QtWebEngineWidgets`` once a ``QApplication`` exists, so the
first lines of a Qt application should be::

    from PyQt6.QtWidgets import QApplication        # import your binding first
    from pylightcharts.qt import prepare_qt
    prepare_qt()                                    # pylightcharts uses PyQt6 too
    app = QApplication([])

or force the binding explicitly::

    prepare_qt('PyQt6')

Chromium in the background
--------------------------
QtWebEngine's Chromium talks to Google endpoints on its own (component updates,
domain reliability, Safe Browsing) as soon as the first page is loaded. On a
blocked or offline network that shows up as *your* startup output::

    handshake failed; returned -1, SSL error code 1, net_error -101

Those requests have nothing to do with the chart - pylightcharts' page is fully
local and loads no external resource - so it is worth switching them off::

    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join([
        '--disable-background-networking',
        '--disable-component-update',
        '--disable-domain-reliability',
        '--disable-client-side-phishing-detection',
        '--disable-breakpad',
        '--disable-sync',
        '--no-pings',
        '--no-first-run',
    ])

Set it before the ``QApplication`` exists. If anything still prints, adding
``--log-level=3`` silences Chromium's own logging entirely (it also hides genuine
GPU warnings, which are harmless but noisy on some drivers).
"""
from __future__ import annotations

import os
from typing import Optional

__all__ = ['prepare_qt']


def prepare_qt(binding: Optional[str] = None):
    """Import a Qt binding and QtWebEngineWidgets **before** you build a
    ``QApplication``.

    :param binding: ``'PyQt6'`` / ``'PySide6'`` / ``'PyQt5'``. Without it the
        binding comes from ``$PYLIGHTCHARTS_QT``, else from whatever the
        application already imported, else by probing.
    :returns: the ``QWebEngineView`` class (or ``None`` when no binding is found).
    """
    if binding:
        os.environ['PYLIGHTCHARTS_QT'] = binding
    from . import widgets

    return widgets.QWebEngineView
