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
from ..validation_utils import arxiv_syntax_validator
from ..filter_utils import strip_prefixes, strip_string
from invenio.utils.arxiv_id import finds_arxiv

__all__ = ['ArXivField']


def missing_arxiv_warning(dummy_form, field, submit=False, fields=None):
    """
    Field processor, checking for existence of a arXiv id, and otherwise
    asking people to provide it.
    """
    if not field.data:
        field.add_message("Please provide an arXiv id if possible.",
                          state="info")
        raise StopIteration()


def arxiv_not_found_warning(dummy_form, field, submit=False, fields=None):
    """
    Field processor, checking for existence of a arXiv id, and otherwise
    asking people to provide it.
    """
    found = finds_arxiv(field.data)
    if not field.errors and not found:
        field.add_message("This arXiv id was not found.", state="danger")
        raise StopIteration()
    else:
        #FIXME: "success" is appending instead of replacing the message class
        field.add_message("We found the ArXiv, you can now import it and we \
            will send you an email after it's finished.", state="success")
        raise StopIteration()


class ArXivField(WebDepositField, TextField):
    def __init__(self, **kwargs):
        defaults = dict(
            icon='barcode',
            validators=[
                arxiv_syntax_validator,
            ],
            filters=[
                strip_string,
                strip_prefixes("arxiv:"),
            ],
            processors=[
                missing_arxiv_warning,
                arxiv_not_found_warning,
            ],
            placeholder="e.g. 1234.5678...",
            widget_classes="form-control"
        )
        defaults.update(kwargs)
        super(ArXivField, self).__init__(**defaults)
