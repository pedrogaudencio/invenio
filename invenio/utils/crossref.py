# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2014 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
API to fetch metadata in MARCXML and JSON formats from crossref site using DOI
"""

import requests
from lxml.etree import fromstring

from invenio.base.globals import cfg
from invenio.legacy.bibconvert.registry import templates
from invenio.legacy.bibconvert.xslt_engine import convert
from invenio.modules.deposit.processor_utils import etree_to_dict


# Exceptions classes
class CrossrefError(Exception):

    """ Crossref errors. """

    def __init__(self, code):
        """ Initialisation. """
        self.code = code

    def __str__(self):
        """ Return error code. """
        return repr(self.code)


def get_marcxml_for_doi(doi):
    """
    Send doi to the http://www.crossref.org/openurl page.

    Attaches parameters: email, doi and redirect.
    Returns the MARCXML code or throws an exception, when
    1. DOI is malformed
    2. Record not found
    """
    if cfg.get('DEPOSIT_CROSSREF_EMAIL') is None:
        raise CrossrefError("error_crossref_no_account")

    # Clean the DOI
    doi = doi.strip()

    # Getting the data from external source
    response = requests.get("http://www.crossref.org/openurl/",
                            params=dict(pid=cfg.get('DEPOSIT_CROSSREF_EMAIL'),
                                        redirect=False,
                                        id=doi)
                            )
    content = response.content

    # Check if the returned page is html - this means the DOI is malformed
    if "text/html" in response.headers['content-type']:
        raise CrossrefError("error_crossref_malformed_doi")
    if 'status="unresolved"' in content:
        raise CrossrefError("error_crossref_record_not_found")

    # Convert xml to marc using convert function
    # from bibconvert_xslt_engine file
    # Seting the path to xsl template
    xsl_crossref2marc_config = templates.get('crossref2marcxml.xsl', '')

    output = convert(xmltext=content,
                     template_filename=xsl_crossref2marc_config)
    return output


def get_json_for_doi(doi):
    """ Send doi to crossref API to gather content to autofill form fields. """
    if cfg.get('DEPOSIT_CROSSREF_EMAIL') is None:
        raise CrossrefError("error_crossref_no_account")

    # Clean the DOI
    doi = doi.strip()

    response = requests.get("http://www.crossref.org/openurl/",
                            params=dict(pid=cfg.get('DEPOSIT_CROSSREF_EMAIL'),
                                        redirect=False,
                                        id=doi)
                            )
    content = response.content

    query = {}
    # Check if the returned page is html - this means the DOI is malformed
    if "text/html" in response.headers['content-type']:
        data = {}
        query['status'] = 'malformed'
    else:
        data = etree_to_dict(fromstring(content))

        # Check if status="unresolved" - this means the DOI was not found
        if 'status="unresolved"' in content:
            query['status'] = 'notfound'
        else:
            query['status'] = 'success'
            for d in data['crossref_result'][0]['query_result'][1]['body'][0]['query']:
                query.update(dict(d.items()))

        del data['crossref_result']

    data['source'] = 'crossref'
    data['query'] = query

    return data
