# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013, 2014 CERN.
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

from wtforms import TextField
from invenio.modules.deposit.field_base import WebDepositField
from ..validation_utils import doi_syntax_validator
from ..filter_utils import strip_prefixes, strip_string
from ..processor_utils import datacite_lookup

__all__ = ['DOIField']


def missing_doi_warning(dummy_form, field, submit=False, fields=None):
    """
    Field processor, checking for existence of a DOI, and otherwise
    asking people to provide it.
    """
    if not field.errors and not field.data:
        field.add_message("Please provide a DOI if possible.", state="warning")
        raise StopIteration()


def doi_already_exists(dummy_form, field, submit=False, fields=None):
    from invenio.legacy.search_engine import perform_request_search
    recid = perform_request_search(p=field.data)
    record = {}
    if recid and len(recid) == 1:
        field.add_message("The DOI you submitted already exists in the \
            database.", state="danger")
        raise StopIteration()


def doi_not_found_warning(dummy_form, field, submit=False, fields=None):
    """
    Field processor, checking for existence of a arXiv id, and otherwise
    asking people to provide it.
    """
    from invenio.utils.crossref import get_json_for_doi
    found = get_json_for_doi(field.data)
    if not field.errors and not found:
        field.add_message("This DOI was not found.", state="warning")
        raise StopIteration()


def doi_found_success(dummy_form, field, submit=False, fields=None):
    from invenio.utils.crossref import get_json_for_doi
    found = get_json_for_doi(field.data)
    if not field.errors and found:
        field.add_message("We found your DOI, you can now import it and we \
            will send you a message after it's done.", state="success")
        raise StopIteration()



class DOIField(WebDepositField, TextField):
    def __init__(self, **kwargs):
        defaults = dict(
            icon='barcode',
            validators=[
                doi_syntax_validator,
            ],
            filters=[
                strip_string,
                strip_prefixes("doi:", "http://dx.doi.org/"),
            ],
            # processors=[
            #     missing_doi_warning,
            #     datacite_lookup(display_info=True),
            #     doi_already_exists,
            #     doi_not_found_warning,
            # ],
            placeholder="e.g. 10.1234/foo.bar...",
            widget_classes="form-control"
        )
        defaults.update(kwargs)
        super(DOIField, self).__init__(**defaults)
