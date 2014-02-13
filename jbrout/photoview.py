__author__ = 'solmyr'

import gtk
import gobject
import pango
import sys

import time
import os
import gc
from __main__ import GladeApp


class PhotoView(GladeApp):
    glade = os.path.join('..', os.path.dirname(os.path.dirname(__file__)), 'data', 'photoview.glade')
    window = "vbox1"

    @staticmethod
    def humanReadableByteCound(bytes, si = True):
        unit = 1000 if si else 1024
        if bytes < unit:
            return str(bytes)+'B'

        exp = max([(i if unit**i <= bytes else 0) for i in xrange(1,6)])
        return '%.1f %s%sB' % (float(bytes)/unit**exp, ('kMGTPE' if si else 'KMGTPE')[exp-1], '' if si else 'i')

    @staticmethod
    def humanReadableDate(date):
        #import time
        #return time.strftime("%d/%m/%Y %I:%M:%S%p", time.gmtime(seconds))
        return date[6:8]+' / '+date[4:6]+' / '+date[0:4]+' '+date[8:10]+':'+date[10:12]+':'+date[12:14]

    def createStockButton(self, image = None, text = None, iconSize = gtk.ICON_SIZE_BUTTON,textPosition = "right"):
        assert( (image != None) or (text != None), "Cannot create empty stock button" )

        if type(image) == str:
            icon = gtk.image_new_from_stock(image, iconSize)
        else:
            return gtk.Label(text)
        icon.show()

        if text == None:
            return icon

        label = gtk.Label(text)
        label.show()

        if textPosition in ('left', 'right'):
            box = gtk.HBox(spacing=4)
        else:
            box = gtk.VBox(spacing=4)

        if textPosition in ('left', 'up'):
            box.add(label)
        box.add(icon)
        if textPosition in ('right', 'down'):
            box.add(label)

        box.show()
        return box



    def init(self, parent, params = {}):
        #connect buttons with icons
        self.index = None
        self._thumbnails_cache = {}

        self.zoom_fit_button.add(self.createStockButton(gtk.STOCK_ZOOM_FIT))
        self.zoom_100_button.add(self.createStockButton(gtk.STOCK_ZOOM_100))
        self.library_back_button.add(self.createStockButton(gtk.STOCK_GO_BACK, "Back to Library"))
        self.play_slideshow_button.add(self.createStockButton(gtk.STOCK_MEDIA_PLAY, "Play"))
        self.prev_button.add(self.createStockButton(gtk.STOCK_MEDIA_PREVIOUS))
        self.next_button.add(self.createStockButton(gtk.STOCK_MEDIA_NEXT))

        self.add_tag_button.add(self.createStockButton(gtk.STOCK_ADD))
        self.thumbnails = [self.thumbnail1, self.thumbnail2, self.thumbnail3, self.thumbnail4, self.thumbnail5, self.thumbnail6, self.thumbnail7 ]
        self.viewport1.modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#888A85'))

        #connect eventboxes to thumbnails
        dx = -3
        for eventbox in [self.thumbnail1event, self.thumbnail2event, self.thumbnail3event, self.thumbnail5event, self.thumbnail6event, self.thumbnail7event]:
            eventbox.set_events(gtk.gdk.BUTTON1_MASK)
            eventbox.connect("button_press_event", self.eventbox_move_to_thumbnail, dx)
            dx+=1
            if dx==0: dx+=1

        #colorize status_line
        self.statusline.modify_fg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#eeeeec'))
        self.statusline_eventbox.modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#729fcf'))
        self.parent = parent

    def eventbox_move_to_thumbnail(self, widget, event, number):
        self.move_to_thumbnail(number)

    def getThumbnailFromNode(self, node):
        if not node.file in self._thumbnails_cache:
            size = 32
            pb = node.getThumb()
            w,h = node.getThumbSize()
            if w < h:
                pb = pb.subpixbuf((h - w)/2, 0, w, h)
            else:
                pb = pb.subpixbuf(0, (w - h)/2, w, h)

            print pb.get_width(), pb.get_height()
            w = pb.get_width()
            h = pb.get_height()
            if w > h:
                pb = pb.scale_simple(w*size/h, size, gtk.gdk.INTERP_HYPER)
            else:
                pb = pb.scale_simple(size, h*size/w, gtk.gdk.INTERP_HYPER)

            pb = pb.subpixbuf(0,0,size, size)
            print pb.get_width(), pb.get_height()
            self._thumbnails_cache[node.file] = pb
        return self._thumbnails_cache[node.file]

    def updateThumbnailsBar(self):
        if self.index!=None:
            for i in xrange(-3,4):
                if 0<= self.index+i < len(self.imagesList):
                    self.thumbnails[i+3].set_from_pixbuf(self.getThumbnailFromNode(self.imagesList[self.index+i]))
                    #self.thumbnails[i+3].show()
                else:
                    #self.thumbnails[i+3].hide()
                    self.thumbnails[i+3].set_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_BUTTON)

    def init_data(self, imagesList, index, selected=[]):
        self.imagesList = imagesList
        self.index = index
        self.selected = selected
        self.updateThumbnailsBar()


    def unload(self):
        self.imagesList = None
        self.index = None
        self.selected = None

    def on_library_back_button_clicked(self, event):
        #TODO
        self.parent.notebook2.set_current_page(0)
        self.unload()

    def updateStatusLine(self):
        d = self.current.getInfo()
        #print d['exifdate']
        #print typeof(d['exifdate'])
        t = [
            self.current.file,
            PhotoView.humanReadableDate(d['exifdate']),
            str(d['resolution'])+' pixels',
            PhotoView.humanReadableByteCound(d['filesize'], False),
            '('+str(self.index+1)+'/'+str(len(self.imagesList))+')'
        ]

        self.statusline.set_text('    '.join(t))


    def updateMainImageData(self):
        pb = self.imagesList[self.index].getImage()
        self.image.set_from_pixbuf(pb)

    def move_to_thumbnail(self, dx):
        if 0<= self.index+dx < len(self.imagesList):
            self.index+=dx
            self.current = self.imagesList[self.index]

            self.updateThumbnailsBar()
            #self.updateMainImageData()
            self.updateStatusLine()

    def on_prev_button_clicked(self, event):
        self.move_to_thumbnail(-1)

    def on_next_button_clicked(self, event):
        self.move_to_thumbnail(1)


if __name__ == "__main__":
    x = PhotoView({'config': 123})
    x.loop()
    #gtk.main()


