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

from flask import request
from flask.ext.login import current_user
from flask.ext.restful import Resource, abort, marshal_with, fields, \
    reqparse
from flask.ext.restful.utils import unpack
from functools import wraps
from werkzeug.utils import secure_filename

from invenio.ext.restful import require_api_auth, error_codes

from cerberus import Validator

from .api import Document


class APIValidator(Validator):
    """
    Adds new datatype 'raw', that accepts anything.
    """
    def _validate_type_any(self, field, value):
        pass


#
# Decorators
#
def error_handler(f):
    """
    Decorator to handle deposition exceptions
    """
    @wraps(f)
    def inner(*args, **kwargs):
        #try:
        return f(*args, **kwargs)
        #except Exception as e:
        #    current_app.logger.error(e)
        #    if len(e.args) >= 1:
        #        abort(400, message=e.args[0], status=400)
        #    else:
        #        abort(500, message="Internal server error", status=500)
    return inner


def require_header(header, value):
    """
    Decorator to test if proper content-type is provided.
    """
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if header == 'Content-Type':
                test_value = request.headers.get(header, '').split(';')[0]
            else:
                test_value = request.headers.get(header, '')

            if test_value != value:
                abort(
                    415,
                    message="Expected %s: %s" % (header, value),
                    status=415,
                )
            return f(*args, **kwargs)
        return inner
    return decorator


def api_request_globals(f):
    """
    Set a variable in request to allow functions further down the chain to
    determine if the request is an API request.
    """
    @wraps(f)
    def inner(*args, **kwargs):
        request.is_api_request = True
        return f(*args, **kwargs)
    return inner


def filter_errors(result):
    """
    Extract error messages from a draft.process() result dictionary.
    """
    error_messages = []
    for field, msgs in result.get('messages', {}).items():
        if msgs.get('state', None) == 'error':
            for m in msgs['messages']:
                error_messages.append(dict(
                    field=field,
                    message=m,
                    code=error_codes['validation_error'],
                ))
    return error_messages


# =========
# Mix-ins
# =========
document_decorators = [
    #require_api_auth,
    error_handler,
    api_request_globals,
]


class InputProcessorMixin(object):
    """
    Mix-in class for validating and processing deposition input data
    """
    #input_schema = draft_data_extended_schema

    def validate_input(self, deposition, draft_id=None):
        """
        Validate input data for creating and update a deposition
        """
        return
        v = APIValidator()
        draft_id = draft_id or deposition.get_default_draft_id()
        metadata_schema = deposition.type.api_metadata_schema(draft_id)

        if metadata_schema:
            schema = self.input_schema.copy()
            schema['metadata'] = metadata_schema
        else:
            schema = self.input_schema

        # Either conform to dictionary schema or dictionary is empty
        if not v.validate(request.json, schema) and \
           request.json:
            abort(
                400,
                message="Bad request",
                status=400,
                errors=map(lambda x: dict(
                    message=x,
                    code=error_codes["validation_error"]
                ), v.errors),
            )

    def process_input(self):
        """ Process input data """
        pass


# =========
# Resources
# =========
class DocumentListResource(Resource):
    """
    Collection of depositions
    """
    method_decorators = document_decorators

    def get(self):
        """
        List depositions

        :param type: Upload type identifier (optional)
        """
        result = Document.storage_engine.model.query.all()
        return map(lambda o: Document.get_document(o.id).dumps(), result)

    @require_header('Content-Type', 'application/json')
    def post(self):
        """
        Create a new deposition
        """
        # Create deposition (uses default deposition type unless type is given)
        #d = Deposition.create(current_user, request.json.get('type', None))
        # Validate input data according to schema
        #self.validate_input(d)
        # Process input data
        #self.process_input(d)
        # Save if all went fine
        #d.save()
        #return d.marshal(), 201
        abort(405)

    def put(self):
        abort(405)

    def delete(self):
        abort(405)

    def head(self):
        abort(405)

    def options(self):
        abort(405)

    def patch(self):
        abort(405)


class DocumentFileResource(Resource):
    """
    Represent a document file
    """
    method_decorators = document_decorators

    def get(self, document_uuid):
        """ Get a document file """
        d = Document.get_document(document_uuid)
        return d.dumps()

    def delete(self, resource_id, file_id):
        """ Delete existing deposition file """
        abort(405)

    def post(self, resource_id, file_id):
        abort(405)

    @require_header('Content-Type', 'application/json')
    def put(self, resource_id, file_id):
        """ Update a deposition file - i.e. rename it"""
        abort(405)

    def head(self, document_uuid):
        abort(405)

    def options(self, document_uuid):
        abort(405)

    def patch(self, document_uuid):
        abort(405)


#
# Register API resources
#
def setup_app(app, api):
    api.add_resource(
        DocumentListResource,
        '/api/document/',
    )
    api.add_resource(
        DocumentFileResource,
        '/api/document/<string:document_uuid>',
    )
    print 'setuped', app, api
