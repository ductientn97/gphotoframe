import urllib

from twisted.internet import threads
import gdata.photos.service
import gdata.media
import gdata.geo

#from ..preferences import PluginDialog

from base import *
from ..utils.keyring import Keyring
from ..constants import APP_NAME

def info():
    return ['Picasa Web', MakePicasaPhoto, PhotoTargetPicasa,
            PluginPicasaDialog ]

class MakePicasaPhoto (MakePhoto):

    def prepare(self):
        print self.target, self.argument

        self.username = 'yendo0206'

        key = Keyring('Google Account', protocol='http')
        key.get_passwd_async(self.username, self._prepare_cb)

    def _prepare_cb(self, identity):
        if identity is None: return

        self.gd_client = gdata.photos.service.PhotosService()
        self.gd_client.email = self.username + '@gmail.com'
        self.gd_client.password = identity[1]
        self.gd_client.source = APP_NAME
        self.gd_client.ProgrammaticLogin()

        if self.target == 'User':
            d = threads.deferToThread(self._get_user_feed, self.argument)
            #d.addCallback(self._get_album, self.argument)
        else:
            d = threads.deferToThread(self._get_feed, 
                                      self.target, self.argument)
            d.addCallback(self._set_photo_db)

    def _get_user_feed(self, uid):
        album_list = self._get_album_list(uid)
        self._get_album(album_list, uid)

    def _get_album_list(self, uid):
        album_list = []
        albums = self.gd_client.GetUserFeed(user=uid)
        for album in albums.entry:
            album_list.append(album.gphoto_id.text)
            #album_list.append(album.title.text)
        return album_list

    def _get_album(self, album_list, uid):
        print uid, album_list
        for album_id in album_list:
            photos = self._get_feed('Album', uid, album_id)
            self._set_photo_db(photos)

    def _get_feed(self, target, argument, option=None):

        url = {
            'Album' : '/user/%s/albumid/%s?kind=photo' % ( argument, option),
            'Community Search' : '/all?kind=photo&q=%s' % argument,
            'Featured' : '/featured'
            # 'User' : '/user/%s/?kind=%s' % ( argument, 'photo'),
            # 'contacts' : '/user/%s/contacts?kind=%s' % ( argumrnt, 'user'),
            # 'photo' : "/user/%s/albumid/%s/photoid/%s?kind=kinds",
            } 

        url = "/data/feed/api" + url[target]
        print url
        photos = self.gd_client.GetFeed(url)

        return photos

    def _set_photo_db(self, photos):
        for entry in photos.entry:
            owner_name = entry.author[0].name.text if entry.author \
                else self.username

            data = {'url'        : entry.content.src,
                    'owner_name' : owner_name,
                    'owner'      : owner_name,
                    'id'         : entry.gphoto_id.text,
                    'title'      : entry.title.text,
                    'summary'    : entry.summary.text,
                    'page_url'   : entry.GetHtmlLink().href,}

            photo = Photo()
            photo.update(data)
            self.photos.append(photo)

class PhotoTargetPicasa(PhotoTarget):

    def _construct_widget(self):
        super(PhotoTargetPicasa, self)._construct_widget()
        self._set_sensitive(state=True)

    def _label(self):
        return ['User', 'Community Search', 'Featured']

    def _set_default(self):
        pass

class PluginPicasaDialog(PluginDialog):

    def run(self):
        self.dialog = self.gui.get_widget('plugin_dialog')
        self.dialog.set_transient_for(self.parent)

        user_id = self.conf.get_string('plugins/picasa/user_id')
        self.entry3 = self.gui.get_widget('entry3')
        self.entry4 = self.gui.get_widget('entry4')

        if user_id != None:
            self.entry3.set_text(user_id)
            self.key = Keyring('Google Account', protocol='http')
            self.passwd = None

            self.key.get_passwd_async(user_id, self._run_cb)

    def _run_cb(self, identity):

        self.passwd = None
        if identity:
            self.passwd = identity[1]
            self.entry4.set_text(self.passwd)

        response_id = self.dialog.run()
        if response_id == gtk.RESPONSE_OK: 
            self._write_gconf()
        else:
            self.dialog.destroy()

    def _write_gconf(self):
        user_id = self.entry3.get_text()
        self.conf.set_string( 'plugins/picasa/user_id', user_id )

        new_passwd = self.entry4.get_text()
        if self.passwd is None or self.passwd != new_passwd:
            self.key.set_passwd_async(user_id, new_passwd, self._destroy_cb)
        else:
            self._destroy_cb()

    def _destroy_cb(self, *args):
        self.dialog.destroy()
