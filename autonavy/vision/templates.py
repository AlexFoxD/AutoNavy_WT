"""Explicit asset loading and bounded versioned single-channel template edges."""
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from autonavy.config import VisionSettings, resource_root
from toolkit.resources import read_image


class TemplateError(ValueError):
    """A named required template could not be loaded or prepared."""


GAME_ASSETS = {
    'start':'start', 'join_game':'joingame4', 'join':'join', 'end':'end', 'close':'close',
    'checkin':'checkin', 'no':'no', 'ok01':'ok01', 'ok02':'ok02', 'ok03':'ok03',
    'tectree':'tectree', 'time':'time', 'yes':'yes', 'exit':'exit', 'returntobase':'rtb',
    'joining':'joining', 'havejoin':'hvjoin', 'buy':'buy', 'back':'back', 'base':'base',
    'ingameing':'ingaming', 'backtobase':'backtobase', 'backtobase2':'backtobase2',
    'autobuyparts':'autobuyparts', 'cart':'cart', 'confirm':'confirm', 'confirm1':'confirm1',
    'confirm2':'confirm2', 'improvement':'improvement', 'improvement_':'improvement_',
    '_purchase':'purchase', 'purchase_confirm':'purchase_confirm', 'crew_cancel':'crew_cancel',
    'rtlg_no':'rtlg_no', 'research':'research', 'research1':'research1', 'box':'box',
    'waiting':'waiting', 'data':'data', 'wtlogo':'wtlogo', 'fire':'6auto', 'lock':'lock',
}


def validate_image(name, image):
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim not in (2,3) or min(image.shape[:2]) <= 0
            or (image.ndim == 3 and image.shape[2] not in (3,4))):
        raise TemplateError(f'Template {name}: expected a nonempty uint8 gray/BGR/BGRA image')


@dataclass(frozen=True, eq=False)
class Template:
    image: np.ndarray
    version: int
    black_mask: bool = False


class TemplateRegistry:
    def __init__(self, *, max_entries=64):
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError('Template cache bound must be positive')
        self._templates = {}
        self._cache = OrderedDict()
        self._max_entries = max_entries

    @property
    def names(self):
        return tuple(self._templates)

    @property
    def cache_size(self):
        return len(self._cache)

    def register(self, name, image, *, version=1, black_mask=False):
        validate_image(name, image)
        if type(version) is not int or version < 1:
            raise TemplateError(f'Template {name}: version must be positive')
        owned = image.copy()
        owned.flags.writeable = False
        self._templates[name] = Template(owned, version, black_mask)
        for key in tuple(self._cache):
            if key[0] == name:
                del self._cache[key]

    def image(self, name):
        try:
            return self._templates[name].image
        except KeyError as exc:
            raise TemplateError(f'Template {name}: not registered') from exc

    def prepared_image(self, name):
        source = self.image(name)
        if self._templates[name].black_mask:
            return cv2.inRange(cv2.cvtColor(source[:,:,:3], cv2.COLOR_BGR2HSV),
                               np.array((0,0,0)), np.array((180,255,46)))
        return source

    def edges(self, name, *, profile_id='legacy-1280x720', settings=VisionSettings()):
        self.image(name)
        template = self._templates[name]
        key = (name, template.version, profile_id, settings.preprocess_version,
               settings.canny_input, settings.canny_low, settings.canny_high, template.black_mask)
        if key not in self._cache:
            source = self.prepared_image(name)
            if settings.canny_input == 'gray' and source.ndim == 3:
                source = cv2.cvtColor(source[:,:,:3], cv2.COLOR_BGR2GRAY)
            edge = cv2.Canny(source, settings.canny_low, settings.canny_high)
            if edge.min() == edge.max():
                raise TemplateError(f'Template {name}: degenerate constant/empty edges')
            edge.flags.writeable = False
            self._cache[key] = edge
            if len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        self._cache.move_to_end(key)
        return self._cache[key]

    @classmethod
    def from_settings(cls, settings):
        registry = cls()
        paths = {name: (settings.paths.templates / (stem+'.png'), cv2.IMREAD_COLOR)
                 for name, stem in GAME_ASSETS.items()}
        paths.update(aim=(settings.paths.aim_template, cv2.IMREAD_UNCHANGED),
                     crash_warning=(resource_root()/'src/crash_warning.png', cv2.IMREAD_COLOR),
                     crashed=(resource_root()/'src/crashed.png', cv2.IMREAD_COLOR))
        for name, (path, flags) in paths.items():
            if not Path(path).is_file():
                raise TemplateError(f'Template {name}: missing file {path}')
            image = read_image(path, flags)
            if image is None:
                raise TemplateError(f'Template {name}: cannot decode {path}')
            registry.register(name, image, black_mask=name == 'lock')
            registry.edges(name, profile_id=settings.geometry.profile_id, settings=settings.vision)
        return registry
