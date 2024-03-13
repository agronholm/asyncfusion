.. image:: https://github.com/agronholm/asyncfusion/actions/workflows/test.yml/badge.svg
  :target: https://github.com/agronholm/asyncfusion/actions/workflows/test.yml
  :alt: Build Status
.. image:: https://coveralls.io/repos/github/agronholm/asyncfusion/badge.svg?branch=master
  :target: https://coveralls.io/github/agronholm/asyncfusion?branch=master
  :alt: Code Coverage
.. image:: https://readthedocs.org/projects/asyncfusion/badge/?version=latest
  :target: https://asyncfusion.readthedocs.io/en/latest/?badge=latest
  :alt: Documentation
.. image:: https://badges.gitter.im/gitterHQ/gitter.svg
  :target: https://gitter.im/python-trio/AsyncFusion
  :alt: Gitter chat

AsyncFusion is an alternative asynchronous event loop implementation that combines the
functionality of both asyncio_ and trio_, allowing you to seamlessly combine code
written against either library. When loaded, it completely replaces the standard
library's asyncio machinery (in memory only!) as well as Trio core.

Quickstart
----------

.. code-block:: python

    import asyncfusion

    asyncfusion.install()  # MUST be done before importing asyncio or trio

    import asyncio
    import trio

    async def main():
        await asyncio.sleep(1)
        await trio.sleep(1)

    asyncio.run(main())

Documentation
-------------

View full documentation at: https://asyncfusion.readthedocs.io/

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _trio: https://github.com/python-trio/trio
