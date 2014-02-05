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

from datetime import date
from docutils.nodes import SparseNodeVisitor, StopTraversal
import json
import os
from sphinx.builders import Builder
import tidylib
import xml.etree.ElementTree as ET


output_file = None


def generate_id(path, method):
    path = path.replace('(', '')
    path = path.replace(')', '')
    elems = path.split('/')
    elems = list(filter(lambda x: x, elems))  # Remove empty strings
    elems = elems[1:]  # Remove "vx" (v1, v2...)

    n_elems = len(elems)
    name = ""

    if method == 'delete':
        if elems[-1].endswith('_id'):
            name += "delete" + elems[-1][0:-3].capitalize()
    elif method == 'get':
        if elems[-1].endswith('_id'):
            name += "show" + elems[-1][0:-3].capitalize()
        elif elems[-1].endswith('_name'):
            name += "show" + elems[-1][0:-5].capitalize()
        elif n_elems > 2:
            if elems[-3][:-1] + '_id' == elems[-2]:
                name += 'show' + elems[-3][:-1].capitalize()
                name += elems[-1].capitalize()
            elif elems[-3][:-1] + '_name' == elems[-2]:
                name += 'show' + elems[-3][:-1].capitalize()
                name += elems[-1].capitalize()
        else:
            name += "list" + elems[-1].capitalize()
    elif method == 'post':
        if elems[-1].endswith('_id'):
            name += "create" + elems[-1][0:-3].capitalize()
        elif elems[-1].endswith('_name'):
            name += "create" + elems[-1][0:-5].capitalize()
        else:
            name += "create" + elems[-1][:-1].capitalize()
    elif method == 'put':
        if elems[-1].endswith('_id'):
            name += "update" + elems[-1][0:-3].capitalize()
        elif elems[-2].endswith('_id'):
            # The name is probably something like ".../foos/foo_id/bar". This
            # is the case in Ceilometer for "/v2/alarms/alarm_id/state"
            name += "update" + elems[-2][0:-3].capitalize() + \
                elems[-1].capitalize()

    if not name:
        name = raw_input('id for %s (%s)' % (path, method))

    return name


def generate_title_from_id(id_):
    words = []
    current_start = 0
    for i, char in enumerate(id_):
        if not char.islower():
            words.append(id_[current_start:i].lower())
            current_start = i

    if i > current_start:
        words.append(id_[current_start:])

    return ' '.join(words).capitalize()


def clean_up_xml(xml_str):
    # When using UTF-8, tidy does not add an encoding attribute. Do it
    # ourselves. See
    # http://tidy.cvs.sourceforge.net/viewvc/tidy/tidy/src/lexer.c?
    # revision=1.194&view=markup
    xml_str = xml_str.replace('?>', ' encoding="UTF-8"?>', 1)

    # tidy automatically inserts a whitespace at the end of a self-closing tag.
    # See line 1347 at:
    # http://tidy.cvs.sourceforge.net/viewvc/tidy/tidy/src/pprint.c?
    # revision=1.119&view=markup

    xml_str = xml_str.replace(' />', '/>')

    # Add this comment right after the <?...?> line. Not sure how to do this
    # using ElementTree.Comment(), since there is no parent element here.
    # XXX(cyril): The starting year may not be the right one for every project.
    xml_str = xml_str.replace('?>\n', '''?>
<!-- (C) 2012-%d OpenStack Foundation, All Rights Reserved -->
<!--*******************************************************-->
<!--         Import Common XML Entities                    -->
<!--                                                       -->
<!--     You can resolve the entites with xmllint          -->
<!--                                                       -->
<!--        xmllint -noent os-compute-2.wadl               -->
<!--*******************************************************-->
''' % date.today().year, 1)

    return xml_str


class MyNodeVisitor(SparseNodeVisitor):
    def __init__(self, document):
        SparseNodeVisitor.__init__(self, document)

        self.must_parse = False
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
        if not self.must_parse:
            # We've probably raised StopTraversal, but walkabout() will keep
            # running the depart_* functions. Here, this is only
            # depart_document(), so we have to leave early.
            return

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
                tmp = ET.SubElement(root, 'resource', {
                    # NOTE(cyril): sometimes, id and path might differ. This
                    # should be good enough, though.
                    'id': k.replace('{', '').replace('}', ''),
                    'path': k,
                })
                if path + '/' + k + '/' in self.paths:
                    for method in self.paths[path + '/' + k + '/']:
                        ET.SubElement(tmp, 'method', {'href': '#' + method})
                build_resources(tmp, v, path + '/' + k)

        build_resources(resources, d)

        # Now, add all the methods we've gathered.
        for method in self.methods:
            self.root.append(method)

        # Finally, write the output.
        with open(output_file, 'w+') as f:
            options = {
                'add-xml-decl': True,
                'indent': True,
                'indent-spaces': 4,
                'input-xml': True,
                'output-encoding': 'utf8',
                'output-xml': True,
                'wrap': 70
            }
            xml_str = tidylib.tidy_document(ET.tostring(self.root),
                                            options=options)[0]
            f.write(clean_up_xml(xml_str))

    # If we're inside a bullet list, all the "paragraph" elements will be
    # parameters description, so we need to know whether we currently are in a
    # bullet list.
    def depart_bullet_list(self, node):
        self.in_bullet_list = False

    def visit_bullet_list(self, node):
        self.in_bullet_list = True

    def visit_comment(self, node):
        # If this .rst file is meant to be parsed by
        # sphinxcontrib-docbookrestapi, then it must have a comment, before the
        # first section, that just reads 'docbookrestapi'.
        if node.astext() == 'docbookrestapi':
            self.must_parse = True

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
        attrs = dict(node.attlist())
        if attrs['domain'] == 'http':
            self.in_method_definition = True

    def visit_desc_signature(self, node):
        attrs = dict(node.attlist())
        if 'method' in attrs and 'path' in attrs:
            method_id = generate_id(attrs['path'], attrs['method'])
            self.current_method = ET.Element('method', {
                'id': method_id,
                'name': attrs['method'].upper()
            })
            self.methods.append(self.current_method)
            path = attrs['path'].replace('(', '{').replace(')', '}')
            self.paths.setdefault(path, []).append(method_id)
            self.current_wadl_doc = ET.SubElement(
                self.current_method, 'wadl:doc', {
                    'xmlns': 'http://docbook.org/ns/docbook',
                    'xml:lang': 'EN',
                    'title': generate_title_from_id(method_id)
                }
            )
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
            ET.SubElement(self.current_wadl_doc, 'para', {
                'role': 'shortdesc'
            }).text = text
            self.needs_method_description = False
        elif self.in_bullet_list:
            # We're describing a parameter here.
            # They look like "param_name (type) -- description in one or more
            # words".
            text = node.astext()
            dashes_index = text.find('--')
            param_name = text[0:text.find(' ')]
            param_type = text[text.find(' ') + 1: dashes_index - 2]
            param_descr = text[dashes_index + 3:]
            param_type = param_type[1:]  # Remove '('
            # Sometimes (especially when using enumerations), only some values
            # may be allowed. If so, they should be listed in the
            # documentation; store them here, and insert them in the code when
            # creating the required elements.
            valid_values = None

            # There are probably more types.
            if param_type.startswith("Enum"):
                valid_values = param_type[5:-1].split(', ')
                param_type = 'xsd:dict'
            elif param_type.startswith("int"):
                param_type = 'xsd:int'
            elif param_type.startswith("list"):
                param_type = 'xsd:list'
            elif param_type .startswith("unicode"):
                param_type = 'xsd:string'
            else:
                param_type = param_type[:-1]  # Remove ')'

            tmp = ET.SubElement(self.current_request, 'param', {
                'name': param_name,
                'type': param_type,
                'required': 'false',  # XXX Can we get the right value ?
                'style': 'query'      # XXX Can we get the right value ?
            })
            tmp = ET.SubElement(tmp, 'wadl:doc', {
                'xml:lang': 'EN',
                'xmlns': 'http://docbook.org/ns/docbook'
            })
            tmp = ET.SubElement(tmp, 'para')
            tmp.text = param_descr
            if valid_values:
                tmp.text += ' Valid values are '
                for i, value in enumerate(valid_values):
                    code = ET.SubElement(tmp, 'code')
                    code.text = value
                    if i + 1 != len(valid_values):
                        code.tail = ', '
                        if i + 2 == len(valid_values):
                            code.tail += 'or '
                    else:
                        code.tail = '.'
        elif self.in_request or self.in_response:
            self.visit_term(node)

    def visit_section(self, node):
        # If, by the time we visit the first section, we have not determined
        # that this .rst file defines a REST API, then we probably should not
        # be parsing it.
        if not self.must_parse:
            raise StopTraversal

    def visit_term(self, node):
        if self.in_request:
            self.current_request_example.append(node.astext())
        elif self.in_response:
            self.current_response_example.append(node.astext())

    def _finalize_json_example(self, parent, body):
            tmp = ET.SubElement(parent, 'representation', {
                'mediaType': 'application/json'
            })
            tmp = ET.SubElement(tmp, 'wadl:doc', {'xml:lang': 'EN'})
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
        global output_file
        output_file = os.path.join(self.outdir, os.path.basename(docname) +
                                   self.out_suffix)

        visitor = MyNodeVisitor(doctree)
        doctree.walkabout(visitor)

    def get_target_uri(self, docname, typ=None):
        return ''
