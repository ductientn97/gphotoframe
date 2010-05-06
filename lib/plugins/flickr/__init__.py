import random

try:
    import simplejson as json
except:
    import json

from ..base import PhotoList, PhotoSourceUI, PhotoSourceOptionsUI, \
    Photo, PluginBase
from ...utils.iconimage import WebIconImage
from ...utils.config import GConf
from ...utils.gnomescreensaver import GsThemeWindow
from api import *
from authdialog import *

def info():
    return [FlickrPlugin, FlickrPhotoList, PhotoSourceFlickrUI, PluginFlickrDialog]

class FlickrPlugin(PluginBase):
    
    def __init__(self):
        self.name = 'Flickr'
        self.icon = FlickrIcon

class FlickrPhotoList(PhotoList):

    def __init__(self, target, argument, weight, options, photolist):
        super(FlickrPhotoList, self).__init__(
            target, argument, weight, options, photolist)
        self.page_list = FlickrAPIPages()

    def prepare(self):
        self.photos = []

        factory = FlickrFactoryAPI()
        api_list = factory.api
        if not self.target in api_list:
            print "flickr: %s is invalid target." % self.target
            return

        self.api = factory.create(self.target, self.argument)
        # print self.api

        if self.api.nsid_conversion:
            nsid_url = self.api.get_url_for_nsid_lookup(self.argument)

            if nsid_url is None: 
                print "flickr: invalid nsid API url."
                return
            self._get_url_with_twisted(nsid_url, self._nsid_cb)
        else:
            self._get_url_for(self.argument)

    def _nsid_cb(self, data):
        d = json.loads(data)
        argument = self.api.parse_nsid(d)
        if argument is None:
            print "flickr: can not find, ", self.argument
            return

        self._get_url_for(argument)

    def _get_url_for(self, argument):
        page = self.page_list.get_page()
        url = self.api.get_url(argument, page) 
        if not url: return

        self._get_url_with_twisted(url)
        interval_min = self.conf.get_int('plugins/flickr/interval', 60)
        self._start_timer(interval_min)

    def _prepare_cb(self, data):
        d = json.loads(data)

        if d.get('stat') == 'fail':
            print "Flickr API Error (%s): %s" % (d['code'], d['message'])
            return

        self.total = len(d['photos']['photo'])
        self.page_list.update(d['photos'])

        for s in d['photos']['photo']:
            if s['media'] == 'video': continue

            url_base = "http://farm%s.static.flickr.com/%s/%s_" % (
                s['farm'], s['server'], s['id'])
            url = "%s%s.jpg" % (url_base, s['secret'])
            url_b = "%s%s_b.jpg" % (url_base, s['secret'])

            page_url = "http://www.flickr.com/photos/%s/%s" % (
                s['owner'], s['id'])

            data = {'type'       : 'flickr',
                    'url'        : url,
                    'url_b'      : url_b,
                    'owner_name' : s['ownername'],
                    'owner'      : s['owner'],
                    'id'         : s['id'],
                    'title'      : s['title'],
                    'page_url'   : page_url,
                    'geo'        : {'lon' : s['longitude'], 
                                    'lat' : s['latitude']},
                    'fav'        : FlickrFav(self.target == 'Favorites', 
                                             {'id': s['id']}),
                    'icon'       : FlickrIcon}

            if s.get('url_o'):
                url = s.get('url_o')
                w, h = int(s.get('width_o')), int(s.get('height_o'))
                data.update({'url_o': url, 'size_o': [w, h]})

            photo = FlickrPhoto()
            photo.update(data)
            self.photos.append(photo)

class PhotoSourceFlickrUI(PhotoSourceUI):

    def get_options(self):
        return self.options_ui.get_value()

    def _build_target_widget(self):
        super(PhotoSourceFlickrUI, self)._build_target_widget()
 
        self._widget_cb(self.target_widget)
        self.target_widget.connect('changed', self._widget_cb)

    def _widget_cb(self, widget):
        target = widget.get_active_text()
        api = FlickrFactoryAPI().create(target)
        
        checkbutton = self.gui.get_widget('checkbutton_flickr_id')
        self._change_sensitive_cb(checkbutton, api)

        self.options_ui.checkbutton_flickr_id_sensitive(api)
        self.options_ui.checkbutton_flickr_id.connect(
            'toggled', self._change_sensitive_cb, api)

    def _change_sensitive_cb(self, checkbutton, api):
        default, label = api.set_entry_label()
        check = checkbutton.get_active() if api.is_use_own_id() else default
        self._set_argument_sensitive(label, check)

        # tooltip 
        tip = api.tooltip() if check else ""
        self._set_argument_tooltip(tip)

        # ok button sensitive
        arg_entry = self.gui.get_widget('entry1')
        state = True if arg_entry.get_text() else not check
        self._set_sensitive_ok_button(arg_entry, state)

    def _label(self):
        keys = FlickrFactoryAPI().api.keys()
        keys.sort()
        return [ api for api in keys ]

    def _make_options_ui(self):
        self.options_ui = PhotoSourceOptionsFlickrUI(self.gui, self.data)

class PhotoSourceOptionsFlickrUI(PhotoSourceOptionsUI):

    def get_value(self):
        state = self.checkbutton_flickr_id.get_active()
        return {'other_id' : state}

    def _set_ui(self):
        self.child = self.gui.get_widget('flickr_vbox')
        self.checkbutton_flickr_id = self.gui.get_widget('checkbutton_flickr_id')

    def _set_default(self):
        state = self.options.get('other_id', False)
        self.checkbutton_flickr_id.set_active(state)

    def checkbutton_flickr_id_sensitive(self, api):
        state = api.is_use_own_id()
        self.checkbutton_flickr_id.set_sensitive(state)

class FlickrPhoto(Photo):

    def get_url(self):
        self.conf = GConf()
        screensaver = GsThemeWindow().get_anid() 
        fullscreen = self.conf.get_bool('fullscreen', False)
        high_resolution = self.conf.get_bool('high_resolution', True)

        if high_resolution and (screensaver or fullscreen):
            w, h = self.get('size_o') or [None, None]
            cond = w and h and (w <= 1280 or h <= 1024)
            url = 'url_o' if cond else 'url_b'
        else:
            url = 'url'

        #print url, w or None, h or None
        return self[url]

class FlickrFav(object):

    def __init__(self, state=False, arg={}):
        self.fav = state
        self.arg = arg
        self.urlget = UrlGetWithProxy()

    def change_fav(self, rate_dummy):
        url = self._get_url()
        d = self.urlget.getPage(url)
        self.fav = not self.fav

    def _get_url(self):
        api = FlickrFavoritesRemoveAPI if self.fav else FlickrFavoritesAddAPI
        url = api().get_url(self.arg['id'])
        return url

class FlickrAPIPages(object):

    def __init__(self):
        self.page_list = []

    def get_page(self):
        page = random.sample(self.page_list, 1)[0] if self.page_list else 1
        return page

    def update(self, feed):
        self.page = feed.get('page')
        self.pages = feed.get('pages')
        self.perpage = feed.get('perpage')

        if not self.page_list and self.pages:
            self.page_list = range(1, self.pages+1)

        if self.page in self.page_list:
            self.page_list.remove(self.page)

class FlickrIcon(WebIconImage):

    def __init__(self):
        self.icon_name = 'flickr.ico'
        self.icon_url = 'http://www.flickr.com/favicon.ico'