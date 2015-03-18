# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013, 2015 CERN.
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
Check the metadata of the records that contain a DOI by comparing it to the
metadata returned by crossref.
"""

from difflib import SequenceMatcher
from itertools import product
import re

from invenio.crossrefutils import get_metadata_for_doi
from invenio.bibknowledge import get_kbr_values
from invenio.bibauthorid_general_utils import is_doi, get_doi
from invenio.bibauthorid_name_utils import (
    create_unified_name,
    create_matchable_name
)


def compare_str(str1, str2):
    """Return similarity (0.0 to 1.0) between the two strings."""
    return SequenceMatcher(None, str1, str2).ratio()


def get_value(record, tag):
    """Get the value of a (unique) field or null."""
    record_values = list(record.iterfield(tag))
    if len(record_values) == 0:
        return None
    return record_values[0][1]


def get_values(record, tag):
    """Get the values of a (unique) field or null."""
    return map(lambda x: x[1], list(record.iterfield(tag)))


def find_volume_in_title(journal_title):
    """Search for volume letter in journal title."""
    volume_search = re.search("( [A-Z] )|( [A-Z]$)", journal_title)

    return volume_search.group(0).strip() if volume_search else ""


def wrong_doi_format_warning(doi, record):
    """Record warning if wrong DOI format."""
    record.warn("Invalid DOI format: {}".format(doi))


def compare_metadata(metadata, rec):
    """Compare a record with the metadata returned by CrossRef.

    @param rec Record
    @param doc xml.etree.ElementTree representation of the xml returned by crossref
    """
    confidence_different = 0
    msgs = []
    msg_tpl = "Invalid {0} or wrongly assigned DOI: CrossRef: {1}; Record: {2}"

    # Check journal
    journals_crossref = metadata.get("container-title", [])
    journals_record = get_values(rec, "773__p")
    journals_similarity = []
    missing_journals = []
    volume_extra = ""
    confidence_different_journals = 0
    journal_comparisons = 0
    different_journals = 0
    if len(journals_crossref) and len(journals_record):
        journals_crossref = map(lambda x: x[0].decode("utf-8") if
                                isinstance(x, tuple) else
                                x.decode("utf-8"),
                                journals_crossref)
        for journal_record, journal_crossref in product(journals_record,
                                                        journals_crossref):
            journal_comparisons += 1
            # Remove volume number from the title
            journal_crossref = re.sub(":.*$", "", journal_crossref)
            volume_extra = find_volume_in_title(journal_crossref)
            journal_crossref = re.sub(" (Section|Volume)$",
                                      "",
                                      journal_crossref)
            mapped_journal = get_kbr_values("JOURNALS",
                                            journal_crossref,
                                            searchtype='e')
            original_similarity = compare_str(journal_crossref, journal_record)
            this_journals_similarity = []
            if not mapped_journal:
                mapped_original = get_kbr_values("JOURNALS",
                                                 journal_record,
                                                 searchtype='e')
                # add a suggestion only if there's also a mapping for the
                # record journal
                if mapped_original:
                    missing_journals.append("{0}---{1}\n".format(journal_crossref,
                                                                 mapped_original[0][0]))
                this_journals_similarity = original_similarity
            else:
                mapped_similarity = compare_str(mapped_journal[0][0],
                                                journal_record)
                this_journals_similarity = max(mapped_similarity,
                                               original_similarity)
            journals_similarity.append(this_journals_similarity)
            if this_journals_similarity < 0.6:
                different_journals += 1
        confidence_different_journals += (1 - max(journals_similarity))*2
        # if all the journal names fail to compare
        if journal_comparisons == different_journals:
            confidence_different += confidence_different_journals
            msgs.append(msg_tpl.format("journal name (773__p)",
                                       journal_crossref,
                                       journal_record))

        if len(missing_journals):
            missing_journals = set(missing_journals)
            for jo in missing_journals:
                rec.warn("missing {}".format(jo))

    # Check issn
    issns_crossref = metadata.get("ISSN", [])
    issn_record = get_value(rec, "022__a")
    if len(issns_crossref) and issn_record is not None:
        issn_record_lower = issn_record.lower()
        different_issns = map(lambda issn_cref: issn_cref.lower() != issn_record_lower,
                              issns_crossref)
        if len(different_issns) == len(issns_crossref):
            confidence_different += 3
            msgs.append(msg_tpl.format("ISSN (022__a)",
                                       issns_crossref,
                                       issn_record))

    # Check page number
    page_crossref = metadata.get("page")
    page_record = get_value(rec, "773__c")
    if page_record is not None and page_crossref is not None:
        page_record_lower = page_record.split("-")[0].lower()
        page_crossref_lower = str(page_crossref.lower()).split("-")[0]
        if page_record_lower != page_crossref_lower and \
                page_record_lower.find(page_crossref_lower) != 1:
            # ignores proceedings
            if not (page_record_lower.startswith("pp.") and
                    page_record_lower[3:].strip() != page_crossref_lower):
                confidence_different += 5
                msgs.append(msg_tpl.format("page number (773__c)",
                                           page_crossref,
                                           page_record))

    # Check author
    author_crossref = ', '.join(filter(None,
                                       [metadata.get("author")[0].get('family'),
                                        metadata.get("author")[0].get('given')])) if \
        metadata.get("author") else None
    author_record = get_value(rec, "100__a")
    if author_crossref is not None and author_record is not None:
        matchable_cref = create_matchable_name(create_unified_name(str(author_crossref)))
        matchable_recd = create_matchable_name(create_unified_name(author_record))
        author_similarity = compare_str(matchable_cref, matchable_recd)
        confidence_different += (1 - author_similarity)*1.5
        if author_similarity < 0.7:
            msgs.append(msg_tpl.format("author (100__a)",
                                       author_crossref,
                                       author_record))

    # Check author
    title_crossref = metadata.get("title")[0] if \
        isinstance(metadata.get("title"), list) and len(metadata.get("title")) else []
    title_record = get_value(rec, "245__a")
    if len(title_crossref) and title_record is not None:
        title_similarity = compare_str(title_crossref, title_record)
        confidence_different += (1 - title_similarity)*1.5
        if title_similarity < 0.7:
            msgs.append(msg_tpl.format("title (245__a)",
                                       title_crossref,
                                       title_record))

    # Check issue
    issue_crossref = metadata.get("issue")
    issue_record = get_value(rec, "773__n")
    if issue_crossref is not None and issue_record is not None and \
            issue_crossref.lower() != issue_record.lower():
        confidence_different += 2
        msgs.append(msg_tpl.format("issue (773__n)",
                                   issue_crossref,
                                   issue_record))

    # Check year
    year_crossref = str(metadata.get("issued").get("date-parts")[0][0]) if \
        isinstance(metadata.get("issued").get("date-parts"), list) else None
    year_record = get_value(rec, "773__y")
    if year_crossref is not None and year_record is not None and \
            year_crossref.lower() != year_record.lower():
        confidence_different += 2
        msgs.append(msg_tpl.format("year (773__y)",
                                   year_crossref,
                                   year_record))

    # Check volume
    volume_crossref = metadata.get("volume")
    volume_record = get_value(rec, "773__v")
    if volume_crossref is not None and volume_record is not None:
        volume_record_lower = volume_record.lower()
        volume_crossref_lower = str(volume_crossref.lower())
        volume_crossref_extra_lower = volume_extra.lower() + volume_crossref.lower()
        try:
            if volume_crossref_lower != volume_record_lower and \
                    volume_crossref_extra_lower != volume_record_lower and \
                    (volume_record_lower.find(volume_crossref_lower) != 1 and
                     volume_crossref_lower.find(volume_record_lower) != 1) and \
                    volume_crossref_lower[2:] != volume_record_lower[:2] and \
                    int(volume_record_lower[:2]) > 12:
                confidence_different += 2
                msgs.append(msg_tpl.format("volume (773__v)",
                                           volume_crossref,
                                           volume_record))
        except ValueError:
            pass

    if confidence_different > 4:
        rec.warn(msgs)


def check_records(records, doi_field="0247_a"):
    """Check the metadata of the records that contain a DOI.

    Comparing it to the metadata returned by CrossRef.
    """
    records_to_check = {}
    for record in records:
        # TODO: check only the 0247_a__2 DOI
        for _, doi in record.iterfield(doi_field):
            records_to_check[doi] = record

    for doi in records_to_check.keys():
        if doi != "" and is_doi(doi):
            metadata = get_metadata_for_doi(get_doi(doi))
            if metadata:
                compare_metadata(metadata, records_to_check[doi])
        else:
            wrong_doi_format_warning(doi, records_to_check[doi])
