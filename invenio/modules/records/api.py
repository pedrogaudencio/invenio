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

"""Record API."""

import six

from sqlalchemy.orm.exc import NoResultFound
from werkzeug.utils import cached_property

from invenio.modules.jsonalchemy.reader import Reader
from invenio.modules.jsonalchemy.wrappers import SmartJson
from invenio.modules.jsonalchemy.errors import ReaderException

from .models import Record as RecordModel


class Record(SmartJson):

    """Default/Base record class."""

    __storagename__ = "records"

    def __init__(self, json=None, **kwargs):
        if not json or '__meta_metadata__' not in json:
            kwargs['namespace'] = kwargs.get('namespace', 'recordext')
            kwargs['master_format'] = kwargs.get('master_format', 'json')
        super(Record, self).__init__(json, **kwargs)
        self.get_blob = lambda: self.blob

    @classmethod
    def create(cls, blob, master_format, **kwargs):
        """Create a new record from the blob using the right reader."""
        return Reader.translate(blob, Record, master_format, **kwargs)

    @classmethod
    def create_many(cls, blobs, master_format, **kwargs):
        """Create many new record from the blob using the right reader."""
        raise NotImplementedError()

    @classmethod
    def get_record(cls, recid, reset_cache=False):
        """Get one record from the DB.

        :param reset_cache: If set to `True` it creates the JSON again.
        """
        if not reset_cache:
            try:
                json = cls.storage_engine.get_one(recid)
                if json is None:
                    raise NoResultFound
                return Record(json)
            except (NoResultFound, AttributeError):
                pass
        # try to retrieve the record from the master format if any
        # this might be deprecated in the near future as soon as json will
        # become the master format, until then ...
        blob = cls.get_blob(recid)
        record_sql_model = RecordModel.query.get(recid)
        if record_sql_model is None or blob is None:
            return None
        additional_info = record_sql_model.additional_info \
            if record_sql_model.additional_info \
            else {'master_format': 'marc'}
        record = cls.create(blob, **additional_info)
        record._save()
        record_sql_model.additional_info = record.additional_info
        from invenio.ext.sqlalchemy import db
        db.session.merge(record_sql_model)
        db.session.commit()
        return record

    @classmethod
    def get_blob(cls, recid):
        """Get the blob from where the record was created."""
        #FIXME: start using bibarchive or bibingest for this
        from invenio.modules.formatter.models import Bibfmt
        from zlib import decompress

        record_blob = Bibfmt.query.get((recid, 'xm'))
        if record_blob is None:
            return None
        return decompress(record_blob.value)

    @property
    def blob(self):
        """Get the blob from where the record was created."""
        #FIXME: start using bibarchive or bibingest for this
        from invenio.modules.formatter.models import Bibfmt
        from zlib import decompress

        record_blob = Bibfmt.query.get((self['recid'], 'xm'))
        if record_blob is None:
            return None
        return decompress(record_blob.value)

    @cached_property
    def persistent_identifiers(self):
        """Create an ordered list with the name of the `PID` and its value.

        The value will be always a list containing dictionaries with this keys
        at least: `field_name` (same as the name of the `PID`) wit the value
        itself, `type` and `provider` (the last two could be empty)
        """
        class PIDList(list):

            """Helper class to build the ordered list of PIDs."""

            def insert(self, index, tuple_):
                """Ordered list insertion."""
                value = (tuple_[0], self._massage_pid_value(tuple_))
                try:
                    self[index] = value
                except IndexError:
                    for _ in xrange(len(self), index+1):
                        self.append(None)
                    self[index] = value

            def _massage_pid_value(self, tuple_):
                """Build a list of dictionaries containing the PID info."""
                if isinstance(tuple_[1], dict):
                    return [tuple_[1]]
                if isinstance(tuple_[1], (list, tuple)):
                    tmp = []
                    for item in tuple_[1]:
                        tmp.extend(self._massage_pid_value((tuple_[0], item)))
                    return tmp
                else:
                    return [{tuple_[0]:tuple_[1], 'type':'', 'provider':''}]

        pids = PIDList()
        for key, value in self.items(without_meta_metadata=True):
            if self.meta_metadata[key]['pid'] is not None:
                pids.insert(self.meta_metadata[key]['pid'], (key, value))
        return filter(None, pids)

    def _save(self):
        self.__class__.storage_engine.update_one(self.dumps())

    # Legacy methods, try not to use them as they are already deprecated

    def legacy_export_as_marc(self):
        """Create the MARCXML representation using the producer rules."""
        from collections import Iterable

        def encode_for_marcxml(value):
            from invenio.utils.text import encode_for_xml
            if isinstance(value, unicode):
                value = value.encode('utf8')
            return encode_for_xml(str(value))

        export = '<record>'
        marc_dicts = self.produce('json_for_marc')
        for marc_dict in marc_dicts:
            content = ''
            tag = ''
            ind1 = ''
            ind2 = ''
            for key, value in six.iteritems(marc_dict):
                if isinstance(value, six.string_types) or \
                        not isinstance(value, Iterable):
                    value = [value]
                for v in value:
                    if v is None:
                        continue
                    if key.startswith('00') and len(key) == 3:
                        # Control Field (No indicators no subfields)
                        export += '<controlfield tag="%s">%s</controlfield>\n'\
                            % (key, encode_for_marcxml(v))
                    elif len(key) == 6:
                        if not (tag == key[:3]
                                and ind1 == key[3].replace('_', '')
                                and ind2 == key[4].replace('_', '')):
                            tag = key[:3]
                            ind1 = key[3].replace('_', '')
                            ind2 = key[4].replace('_', '')
                            if content:
                                export += '<datafield tag="%s" ind1="%s"'\
                                    'ind2="%s">%s</datafield>\n' \
                                    % (tag, ind1, ind2, content)
                                content = ''
                        content += '<subfield code="%s">%s</subfield>'\
                            % (key[5], encode_for_marcxml(v))
                    else:
                        pass

            if content:
                export += \
                    '<datafield tag="%s" ind1="%s" ind2="%s">%s</datafield>\n'\
                    % (tag, ind1, ind2, content)

        export += '</record>'
        return export

    def legacy_create_recstruct(self):
        """Create the `recstruct` representation.

        It uses the producer rules and
        :func:`~invenio.legacy.bibrecord.create_record`.
        """
        # FIXME: it might be a bit overkilling
        from invenio.legacy.bibrecord import create_record
        record, status_code, errors = create_record(
            self.legacy_export_as_marc()
        )
        if status_code == 0:
            # There was an error
            if isinstance(errors, list):
                errors = "\n".join(errors)
            raise ReaderException(
                "There was an error while parsing MARCXML: %s" % (errors,))
        return record

# Functional interface
create_record = Record.create
create_records = Record.create_many
get_record = Record.get_record
get_record_blob = Record.get_blob
