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
        self.zoom_fit_button.add(self.createStockButton(gtk.STOCK_ZOOM_FIT))
        self.zoom_100_button.add(self.createStockButton(gtk.STOCK_ZOOM_100))
        self.library_back_button.add(self.createStockButton(gtk.STOCK_GO_BACK, "Back to Library"))
        self.play_slideshow_button.add(self.createStockButton(gtk.STOCK_MEDIA_PLAY, "Play"))
        self.prev_button.add(self.createStockButton(gtk.STOCK_MEDIA_PREVIOUS))
        self.next_button.add(self.createStockButton(gtk.STOCK_MEDIA_NEXT))

        self.add_tag_button.add(self.createStockButton(gtk.STOCK_ADD))

        self.parent = parent

    def on_library_back_button_clicked(self, event):
        #TODO
        self.parent.notebook2.set_current_page(0)




if __name__ == "__main__":
    x = PhotoView({'config': 123})
    x.loop()
    #gtk.main()


