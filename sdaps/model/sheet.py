# -*- coding: utf-8 -*-
# SDAPS - Scripts for data acquisition with paper based surveys
# Copyright(C) 2008, Christoph Simon <post@christoph-simon.eu>
# Copyright(C) 2008, Benjamin Berg <benjamin@sipsolutions.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import buddy
from . import data as datamodule
from . import db

class Sheet(buddy.Object):

    _pickled_attrs = {'data', 'images', 'survey_id',
                      'questionnaire_id', 'global_id', 'valid',
                      'quality', 'recognized', 'verified'}

    def __init__(self):
        self.survey = None
        self.data = dict()
        self.images = list()
        self.survey_id = None
        self.questionnaire_id = None
        self.global_id = None
        self.valid = 1
        self.quality = 1

        self.recognized = False
        self.verified = False

    def add_image(self, image):
        self.images.append(image)
        image.sheet = self

    def get_page_image(self, page):
        # Simply return the image for the requested page.
        # Note: We return the first one we find; this means in the error case
        #       that a page exists twice, we return the first one.
        for image in self.images:
            if image.page_number == page and image.survey_id == self.survey.survey_id:
                return image
        return None

    def reinit_state(self):
        for k, v in self.data.items():
            obj = self.survey.questionnaire.find_object(k)

            v._parent = obj

    def __jgetstate__(self):
        # json is unable to serialize our tuples as keys, so make strings with
        # '^' as a separator.
        res = self.__getstate__()
        res_data = dict()
        res['data'] = res_data

        for k, v in self.data.items():
            res_data['^'.join(str(_) for _ in k)] = v

        return res

    def __jsetstate__(self, data):
        _tmp = data['data']
        data['data'] = {}
        for k, v in _tmp.items():
            data['data'][tuple(int(_) for _ in k.split('^'))] = db.fromJson(v, datamodule)

        for k in range(len(data['images'])):
            data['images'][k] = db.fromJson(data['images'][k], Image)
            data['images'][k].sheet = self

        self.__dict__ = data
        self.survey = None

    @property
    def empty(self):
        for k, v in self.data.items():
            if not v.empty:
                return False

        return True

    @property
    def complete(self):
        """A boolean whether this sheet is complete in the sense that
        every page of the questionnaire has been identified.
        ie. it is false if there are missing pages"""

        # Simply retrieve every page, and see if it is not None
        for page in range(self.survey.questionnaire.page_count):
            if self.get_page_image(page + 1) is None:
                return False
        return True

    @property
    def dirty(self):
        if hasattr(self, '_dirty'):
             return True
        for d in self.data.values():
            if hasattr(d, '_dirty'):
                return True
        for i in self.images:
            if hasattr(i, '_dirty'):
                return True

    def _clear_dirty(self):
        if hasattr(self, '_dirty'):
             del self._dirty
        for d in self.data.values():
            if hasattr(d, '_dirty'):
                del d._dirty
        for i in self.images:
            if hasattr(i, '_dirty'):
                del i._dirty

    def __setattr__(self, attr, value):
        if attr.startswith('_') or attr == 'survey':
            object.__setattr__(self, attr, value)
            return

        # Nonexisting attributes should never be set.
        assert attr in self._pickled_attrs

        self.__setattr__('_dirty', True)

        # We need to fall back to "None" for __init__ to work.
        try:
            old_value = getattr(self, attr)
            force = False
        except AttributeError:
            old_value = None
            force = True

        if force or value != old_value:
            object.__setattr__(self, attr, value)
            # survey may be None if the sheet does not belong to a survey yet.
            if self.survey is not None:
                self.survey.questionnaire.notify_data_changed(None, None, attr, old_value)

    # Can be used for debugging purposes
    # XXX: Comment before releasing
    def __del__(self):
        # A dirty sheet should never be freed, just a sanity check to catch errors
        assert(not self.dirty)

class Image(buddy.Object):

    # Could make "sheet" a private property instead!
    _pickle_skip = {'sheet'}

    def __init__(self):
        self.sheet = None
        self.filename = str()
        self.tiff_page = 0
        self.rotated = 0
        self.raw_matrix = None
        self.page_number = None
        self.survey_id = None
        self.global_id = None
        self.questionnaire_id = None
        #: Whether the page should be ignored (because it is a blank back side)
        self.ignored = False

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            return object.__setattr__(self, attr, value)
        if attr != 'sheet':
            object.__setattr__(self, '_dirty', True)

        object.__setattr__(self, attr, value)

