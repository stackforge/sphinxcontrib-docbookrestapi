#!/usr/bin/env python
# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Cyril Roelandt <cyril.roelandt@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import unittest

from sphinxcontrib.docbookrestapi.docbook import generate_id


class TestUtils(unittest.TestCase):
    def test_generate_id(self):
        test_cases = [
            # (path, method, expected_result)
            ('/v2/foos', 'get', 'listFoos'),

            ('/v2/foos/foo_id', 'delete', 'deleteFoo'),
            ('/v2/foos/foo_id', 'get', 'showFoo'),
            ('/v2/foos/foo_id', 'post', 'createFoo'),
            ('/v2/foos/foo_id', 'put', 'updateFoo'),

            ('/v2/foos/foo_id/bar', 'get', 'showFooBar'),
            ('/v2/foos/foo_id/bar', 'put', 'updateFooBar'),
        ]

        for (path, method, result) in test_cases:
            self.assertEqual(generate_id(path, method), result)
