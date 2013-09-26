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

import json
import xml.etree.ElementTree as ET

from docutils.nodes import SparseNodeVisitor
from lxml import etree
from os import path
from sphinx.builders import Builder

output_file = None


class MyNodeVisitor(SparseNodeVisitor):
    def __init__(self, document):
        self.document = document

        self.methods = []
        self.paths = {}
        self.current_method = None
        self.root = None
        self.in_method_definition = False
        self.needs_method_description = False
        self.in_bullet_list = False
        self.in_request = False
        self.in_response = False
        self.current_request_example = []
        self.current_response_example = []

    def depart_document(self, node):
        # We are done parsing this document, let's print everything we need.
        resources = ET.SubElement(self.root, 'resources', {
            'base': 'http://www.example.com'
        })

        # Create 'd', a dict of the form:
        # {
        #     'foo': {
        #         'bar': {},
        #         'baz': {}
        #     }
        # }
        # If the paths are 'foo/bar' and 'foo/baz'.
        d = {}
        for path, methods in self.paths.iteritems():
            cd = d
            l = path[1:-1].replace('(', '{').replace(')', '}').split('/')
            for e in l:
                if e not in cd:
                    cd[e] = {}
                cd = cd[e]

        def build_resources(root, d, path=''):
            for k, v in d.iteritems():
                tmp = ET.SubElement(root, 'resource', {'path': k})
                if path + '/' + k + '/' in self.paths:
                    for method in self.paths[path+'/'+k+'/']:
                        ET.SubElement(tmp, 'method', {'href': '#' + method})
                build_resources(tmp, v, path+'/'+k)

        build_resources(resources, d)

        # Now, add all the methods we've gathered.
        for method in self.methods:
            self.root.append(method)

        # Finally, write the output.
        with open(output_file, 'w+') as f:
            f.write(ET.tostring(self.root))

    # If we're inside a bullet list, all the "paragraph" elements will be
    # parameters description, so we need to know whether we currently are in a
    # bullet list.
    def depart_bullet_list(self, node):
        self.in_bullet_list = False

    def visit_bullet_list(self, node):
        self.in_bullet_list = True

    def visit_document(self, node):
        # This is where we should start. Let's build the root.
        attrs = {
            'xmlns': 'http://wadl.dev.java.net/2009/02',
            'xmlns:xsdxt': 'http://docs.rackspacecloud.com/xsd-ext/v1.0',
            'xmlns:wadl': 'http://wadl.dev.java.net/2009/02',
            'xmlns:xsd': 'http://docs.rackspacecloud.com/xsd/v1.0'
        }
        self.root = ET.Element('application', attrs)

    # If we are in a 'desc' node with the 'domain' attribute equal to 'http',
    # we're in a method definition. The next 'paragraph' element will be the
    # description of this method.
    def depart_desc(self, node):
        self.in_method_definition = False

    def visit_desc(self, node):
        attrs = {k: v for (k, v) in node.attlist()}
        if attrs['domain'] == 'http':
            self.in_method_definition = True

    def visit_desc_signature(self, node):
        attrs = {k: v for (k, v) in node.attlist()}
        if 'method' in attrs and 'path' in attrs:
            method_id = attrs['method'] + attrs['path'].replace('/', '_') + \
                "method"
            self.current_method = ET.Element('method', {
                'id': method_id,
                'name': attrs['method'].upper()
            })
            self.methods.append(self.current_method)
            path = attrs['path'].replace('(', '{').replace(')', '}')
            self.paths.setdefault(path, []).append(method_id)
            self.current_request = ET.SubElement(self.current_method,
                                                 'request')
            self.current_response = ET.SubElement(self.current_method,
                                                  'response',
                                                  {'status': '200'})
            self.needs_method_description = True

    def visit_paragraph(self, node):
        if self.in_method_definition and self.needs_method_description:
            text = node.astext()

            # Remove ":type data: foo" and ":return type: bar".
            type_index = text.find(':type data:')
            return_index = text.find(':return type:')
            min_index = min(type_index, return_index)
            if min_index > -1:
                text = text[0:min_index]

            # Create the doc node in the method.
            wadl = ET.SubElement(self.current_method, 'wadl:doc', {
                'xmlns': 'http://www.w3.org/1999/xhtml',
                'xml:lang': 'EN',
                'title': ''
            })
            ET.SubElement(wadl, 'p', {
                'xmlns': 'http://www.w3.org/1999/xhtml'
            }).text = text
            self.needs_method_description = False
        elif self.in_bullet_list:
            # We're describing a parameter here.
            # They look like "param_name (type) -- description in one or more
            # words".
            text = node.astext()
            dashes_index = text.find('--')
            param_name = text[0:text.find(' ')]
            param_type = text[text.find(' ')+1: dashes_index-1]
            param_descr = text[dashes_index+3:]
            param_type = param_type[1:]  # Remove '('

            # There are probably more types.
            if param_type.startswith("int"):
                param_type = 'xsd:int'
            elif param_type.startswith("list"):
                param_type = 'xsd:list'
            elif param_type .startswith("unicode"):
                param_type = 'xsd:string'
            else:
                raise ValueError(param_type)

            tmp = ET.SubElement(self.current_request, 'param', {
                'xmlns': 'http://wadl.dev.java.net/2009/02',
                'name': param_name,
                'type': param_type,
                'required': 'false',  # XXX Can we get the right value ?
                'style': 'query'      # XXX Can we get the right value ?
            })
            tmp = ET.SubElement(tmp, 'doc')
            ET.SubElement(tmp, 'p', {
                'xmlns': 'http://www.w3.org/1999/xhtml'
            }).text = param_descr
        elif self.in_request or self.in_response:
            self.visit_term(node)

    def visit_term(self, node):
        if self.in_request:
            self.current_request_example.append(node.astext())
        elif self.in_response:
            self.current_response_example.append(node.astext())

    def _finalize_json_example(self, parent, body):
            tmp = ET.SubElement(parent, 'representation', {
                'mediaType': 'application/json'
            })
            tmp = ET.SubElement(tmp, 'doc', {'xml:lang': 'EN'})
            json_text = json.loads(''.join(body))
            json_text = json.dumps(json_text, indent=4, sort_keys=True)
            ET.SubElement(tmp, 'xsdxt:code').text = json_text

    def visit_field_name(self, node):
        text = node.astext()
        if text == "Request json":
            self.in_request = True
            self.in_responses = False
        elif text == "Response json":
            self.in_request = False
            self.in_response = True
        else:
            self.in_request = False
            if self.current_request_example:
                self._finalize_json_example(self.current_request,
                                            self.current_request_example)
                self.current_request_example = []
            self.in_response = False
            if self.current_response_example:
                self._finalize_json_example(self.current_response,
                                            self.current_response_example)
                self.current_response_example = []


class DocBookBuilder(Builder):
    name = 'docbook'
    format = 'docbook'
    out_suffix = '.wadl'

    def get_outdated_docs(self):
        return 'all documents'  # XXX for now

    def prepare_writing(self, docnames):
        pass

    def write_doc(self, docname, doctree):
        # XXX: We only want to build the documentation for the v2 API.
        # We should be able to tell sphinx-build not to try and build doc for
        # other .rst files, but this does not seem to work. This is a
        # (Ceilometer-specific) workaround.
        if docname != 'webapi/v2':
            return

        global output_file
        output_file = path.join(self.outdir, path.basename(docname) +
                                self.out_suffix)

        visitor = MyNodeVisitor(doctree)
        doctree.walkabout(visitor)

    def get_target_uri(self, docname, typ=None):
        return ''
