# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from __future__ import absolute_import, print_function

from datetime import date

from flask import render_template
from flask.ext.login import current_user

from invenio.ext.login import UserInfo
from invenio.modules.deposit.models import DepositionType, Deposition
from workflow import patterns as p
from invenio.modules.formatter import format_record
from invenio.modules.deposit.tasks import render_form, \
    create_recid, \
    prepare_sip, \
    finalize_record_sip, \
    upload_record_sip, \
    prefill_draft, \
    has_submission, \
    hold_for_approval, \
    load_record, \
    merge_record, \
    process_sip_metadata, \
    process_bibdocfile, \
    merge_changes


# =======
# Helpers
# =======
def file_firerole(email, access_right, embargo_date):
    """Compute file firerole for a file given access_right, embargo_date."""
    # Generate firerole
    fft_status = []
    if access_right == 'open':
        # Access to everyone
        fft_status = [
            'allow any',
        ]
    elif access_right == 'embargoed':
        # Access to submitter, deny everyone else until embargo date,
        # then allow all
        fft_status = [
            'allow email "%s"' % email,
            'deny until "%s"' % embargo_date,
            'allow any',
        ]
    elif access_right in ('closed', 'restricted',):
        # Access to submitter, deny everyone else
        fft_status = [
            'allow email "%s"' % email,
            'deny all',
        ]
    return "firerole: %s" % "\n".join(fft_status)


# =========================
# JSON processing functions
# =========================
def process_draft(draft):
    """Process loaded form JSON."""
    pass


def process_recjson(deposition, recjson):
    """Process exported recjson (common for both new and edited records)."""
    # ================
    # ISO format dates
    # ================
    for k in recjson.keys():
        if isinstance(recjson[k], date):
            recjson[k] = recjson[k].isoformat()

    # =======
    # Authors
    # =======
    if 'authors' in recjson and recjson['authors']:
        recjson['_first_author'] = recjson['authors'][0]
        recjson['_additional_authors'] = recjson['authors'][1:]

    # =======
    # Journal
    # =======
    # Set year or delete fields if no title is provided
    if recjson.get('journal.title', None):
        recjson['journal.year'] = recjson['publication_date'][:4]

    # ==================================
    # Map dot-keys to their dictionaries
    # ==================================
    for k in recjson.keys():
        if '.' in k:
            mainkey, subkey = k.split('.')
            if mainkey not in recjson:
                recjson[mainkey] = {}
            recjson[mainkey][subkey] = recjson.pop(k)

    return recjson


def process_recjson_new(deposition, recjson):
    """Process exported recjson for a new record."""
    process_recjson(deposition, recjson)

    # ================
    # Owner
    # ================
    # Owner of record (can edit/view the record)
    user = UserInfo(deposition.user_id)
    email = user.info.get('email', '')
    recjson['owner'] = dict(
        email=email,
        username=user.info.get('nickname', ''),
        id=deposition.user_id,
        deposition_id=deposition.id,
    )

    return recjson


def process_recjson_edit(deposition, recjson):
    """Process recjson for an edited record."""
    process_recjson(deposition, recjson)

    return recjson


def process_files(deposition, bibrecdocs):
    """Process bibrecdocs for extra files."""
    sip = deposition.get_latest_sip(sealed=False)

    fft_status = file_firerole(
        sip.metadata['owner']['email'],
        sip.metadata['access_right'],
        sip.metadata.get('embargo_date'),
    )

    sip.metadata['fft'] = []

    for bf in bibrecdocs.list_latest_files():
        sip.metadata['fft'].append({
            'name': bf.name,
            'format': bf.format,
            'restriction': fft_status,
            'description': 'KEEP-OLD-VALUE',
            'comment': 'KEEP-OLD-VALUE',
        })


def merge(deposition, dest, a, b):
    """Merge changes from editing a deposition."""
    data = merge_changes(deposition, dest, a, b)

    # Force ownership (owner of record (can edit/view the record))
    user = UserInfo(deposition.user_id)
    data['owner'].update(dict(
        email=user.info.get('email', ''),
        username=user.info.get('nickname', ''),
        id=deposition.user_id,
        deposition_id=deposition.id,
    ))

    return data


def run_tasks(update=False):
    """Run bibtasklet and webcoll after upload."""
    def _run_tasks(obj, dummy_eng):
        from invenio.legacy.bibsched.bibtask import task_low_level_submission

        d = Deposition(obj)
        sip = d.get_latest_sip(sealed=True)

        recid = sip.metadata['recid']
        communities = sip.metadata.get('provisional_communities', [])

        common_args = []
        sequenceid = getattr(d.workflow_object, 'task_sequence_id', None)
        if sequenceid:
            common_args += ['-I', str(sequenceid)]

        if update:
            tasklet_name = 'bst_openaire_update_upload'
        else:
            tasklet_name = 'bst_openaire_new_upload'

        task_id = task_low_level_submission(
            'bibtasklet', 'webdeposit', '-T', tasklet_name,
            '--argument', 'recid=%s' % recid, *common_args
        )
        sip.task_ids.append(task_id)

        for c in communities:
            task_id = task_low_level_submission(
                'webcoll', 'webdeposit', '-c', 'provisional-user-%s' % c,
                *common_args
            )
            sip.task_ids.append(task_id)
        d.update()
    return _run_tasks


# ===============
# Deposition type
# ===============
class EditableRecordDeposition(DepositionType):

    """Editable article deposition workflow."""

    workflow = [
        p.IF_ELSE(
            has_submission,
            # Existing deposition
            [
                # Load initial record
                load_record(
                    draft_id='_edit',
                    post_process=process_draft
                ),
                # Render the form and wait until it is completed
                render_form(draft_id='_edit'),
            ],
            # New deposition
            [
                # Load pre-filled data from cache
                prefill_draft(draft_id='_default'),
                # Render the form and wait until it is completed
                render_form(draft_id='_default'),
                # Test if all files are available for API
                #api_validate_files(),
            ]
        ),
        # Create the submission information package by merging data
        # from all drafts - i.e. generate the recjson.
        prepare_sip(),
        p.IF_ELSE(
            has_submission,
            [
                # Process SIP recjson
                process_sip_metadata(process_recjson_edit),
                # Merge SIP metadata into record and generate MARC
                # merge_record(
                #     draft_id='_edit',
                #     post_process_load=process_draft,
                #     process_export=process_recjson_edit,
                #     merge_func=merge,
                # ),
                # Set file restrictions
                #process_bibdocfile(process=process_files),
            ],
            [
                # Process SIP metadata
                process_sip_metadata(process_recjson_new),
                # Reserve a new record id
                create_recid(),
            ]
        ),
        # Generate MARC based on recjson structure
        finalize_record_sip(),
        # Hold the deposition for admin approval
        #hold_for_approval(),
        p.IF_ELSE(
            has_submission,
            [
                # Seal the SIP and write MARCXML file and call bibupload on it
                upload_record_sip(),
                # Schedule background tasks.
                #run_tasks(update=True),
            ],
            [
                # Note: after upload_record_sip(), has_submission will return
                # True no matter if it's a new or editing of a deposition.
                upload_record_sip(),
                #run_tasks(update=False),
            ]
        ),
    ]
    # stopable = True
    # enabled = True
    # default = True
    # # api = True

    hold_for_upload = False

    @classmethod
    def default_draft_id(cls, deposition):
        """."""
        if deposition.has_sip() and '_edit' in deposition.drafts:
            return '_edit'
        return '_default'

    # @classmethod
    # def marshal_deposition(cls, deposition):
    #     """
    #     Generate a JSON representation for REST API of a Deposition
    #     """
    #     # Get draft
    #     if deposition.has_sip() and '_edit' in deposition.drafts:
    #         draft = deposition.get_draft('_edit')
    #         metadata_fields = cls.marshal_metadata_edit_fields
    #     elif deposition.has_sip():
    #         # FIXME: Not based on latest available data in record.
    #         sip = deposition.get_latest_sip(sealed=True)
    #         draft = record_to_draft(
    #             Record.create(sip.package, master_format='marc'),
    #             post_process=process_draft
    #         )
    #         metadata_fields = cls.marshal_metadata_edit_fields
    #     else:
    #         draft = deposition.get_or_create_draft('_default')
    #         metadata_fields = cls.marshal_metadata_fields

    #     # Fix known differences in marshalling
    #     draft.values = filter_empty_elements(draft.values)
    #     if 'grants' not in draft.values:
    #         draft.values['grants'] = []

    #     # Set disabled values to None in output
    #     for field, flags in draft.flags.items():
    #         if 'disabled' in flags and field in draft.values:
    #             del draft.values[field]

    #     # Marshal deposition
    #     obj = marshal(deposition, cls.marshal_deposition_fields)
    #     # Marshal the metadata attribute
    #     obj['metadata'] = marshal(unicodifier(draft.values), metadata_fields)

    #     # Add record and DOI information from latest SIP
    #     for sip in deposition.sips:
    #         if sip.is_sealed():
    #             recjson = sip.metadata
    #             if recjson.get('recid'):
    #                 obj['record_id'] = fields.Integer().format(
    #                     recjson.get('recid')
    #                 )
    #                 obj['record_url'] = fields.String().format(url_for(
    #                     'record.metadata',
    #                     recid=recjson.get('recid'),
    #                     _external=True
    #                 ))
    #             if recjson.get('doi') and \
    #                recjson.get('doi').startswith(CFG_DATACITE_DOI_PREFIX+"/"):
    #                 obj['doi'] = fields.String().format(recjson.get('doi'))
    #                 obj['doi_url'] = fields.String().format(
    #                     "http://dx.doi.org/%s" % obj['doi']
    #                 )
    #             break

    #     return obj

    # @classmethod
    # def marshal_draft(cls, obj):
    #     """
    #     Generate a JSON representation for REST API of a DepositionDraft
    #     """
    #     return marshal(obj, cls.marshal_draft_fields)

    # @classmethod
    # def api_action(cls, deposition, action_id):
    #     if action_id == 'publish':
    #         return deposition.run_workflow(headless=True)
    #     elif action_id == 'edit':
    #         # Trick: Works in combination with load_record task to provide
    #         # proper response codes to API clients.
    #         if deposition.state == 'done' or deposition.drafts:
    #             deposition.reinitialize_workflow()
    #         return deposition.run_workflow(headless=True)
    #     elif action_id == 'discard':
    #         deposition.stop_workflow()
    #         deposition.save()
    #         return deposition.marshal(), 201
    #     raise InvalidApiAction(action_id)

    # @classmethod
    # def api_metadata_schema(cls, draft_id):
    #     schema = super(upload, cls).api_metadata_schema(draft_id)
    #     if schema and draft_id == '_edit':
    #         if 'recid' in schema['schema']:
    #             del schema['schema']['recid']
    #         if 'modification_date' in schema['schema']:
    #             del schema['schema']['modification_date']
    #     return schema

    @classmethod
    def render_completed(cls, d):
        """Render page when deposition was successfully completed."""
        ctx = dict(
            deposition=d,
            deposition_type=(
                None if d.type.is_default() else d.type.get_identifier()
            ),
            uuid=d.id,
            my_depositions=Deposition.get_depositions(
                current_user, type=d.type
            ),
            sip=d.get_latest_sip(),
            format_record=format_record,
        )

        return render_template('deposit/completed.html', **ctx)

    @classmethod
    def process_sip_metadata(cls, deposition, metadata):
        """Implement this method in your subclass to process metadata prior to MARC generation."""
        pass
