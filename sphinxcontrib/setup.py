#!/usr/bin/env python

from sphinxcontrib.docbook import DocBookBuilder

def setup(app):
    app.add_builder(DocBookBuilder)
