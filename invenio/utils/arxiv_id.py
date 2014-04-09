# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013 CERN.
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

import urllib2
from xml.dom.minidom import parseString

from invenio.modules.records.api import Record


def finds_arxiv(term):
    """
    Searches the ArXiv id in the database, if doesn't find fetches it from the
    arxiv.org API
    """
    #FIXME: check if the arxiv id belongs to a thesis (or whatever) so the data fetched matches the form
    if term:
        from invenio.legacy.search_engine import perform_request_search
        recid = perform_request_search(p=term)
        record = {}
        if recid and len(recid) == 1:
            # Query the database
            record = Record.get_record(recid)
        #partir aqui: se a cena ja esta na db, entao deve avisar que nao pode ser importado de novo
        else:
            # Make request
            server = "http://export.arxiv.org/api"
            script = "/query?search_query=all:"
            url = server + script + term
            external_request = urllib2.urlopen(url).read()

            xml = parseString(external_request)

            results = xml.getElementsByTagName('opensearch:totalResults').item(0).childNodes[0].data

            if int(results) == 1:
                record['authors'] = xml.getElementsByTagName('author').item(0).childNodes[1].firstChild.data
                record['title'] = xml.getElementsByTagName('title').item(1).firstChild.data
                record['abstract'] = xml.getElementsByTagName('summary').item(0).firstChild.data
                record['preprint_info'] = {}
                record['preprint_info']['date'] = xml.getElementsByTagName('published').item(0).firstChild.data
                #FIXME: move this inspire related field to some task in the workflow
                record['inspire_id'] = term

            print record
    return record
