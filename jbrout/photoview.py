__author__ = 'solmyr'

import gtk
import os
import time
from math import log, exp
from __main__ import GladeApp


def debug(f):
    def debug_f(*args, **kwargs):
        print 'enter: '+f.__name__+" "+str(args)+' '+str(kwargs)
        x = f(*args, **kwargs)
        print 'exit: '+f.__name__
        return x
    return debug_f

class Utils():

    @staticmethod
    def get_human_readable_byte_count(count, si = True):
        unit = 1000 if si else 1024
        if count < unit:
            return str(count)+'B'

        exp = max([(i if unit**i <= count else 0) for i in xrange(1, 6)])
        return '%.1f %s%sB' % (float(count)/unit**exp, ('kMGTPE' if si else 'KMGTPE')[exp-1], '' if si else 'i')

    @staticmethod
    def get_human_readable_date(date):
        #import time
        #return time.strftime("%d/%m/%Y %I:%M:%S%p", time.gmtime(seconds))
        return date[6:8]+' / '+date[4:6]+' / '+date[0:4]+' '+date[8:10]+':'+date[10:12]+':'+date[12:14]

    @staticmethod
    def create_expander(label = "Expander", widget = None, start_expanded = False):
        assert isinstance(widget, gtk.Widget), "widget must be gtk.Widget"

        def expander_active(expander_, event, obj):
            if expander_.get_expanded():
                obj.show()
            else:
                obj.hide()

        def button_press(widget_, event, expander_):
            expander.emit('activate')

        vbox = gtk.VBox()

        button = gtk.Button()
        expander = gtk.Expander()

        expander.set_label(label)
        button.add(expander)
        vbox.pack_start(button, False, False)
        vbox.pack_start(widget, False, False)

        if start_expanded:
            expander.set_expanded(True)
            widget.show()
        else:
            expander.set_expanded(False)
            widget.hide()

        expander.connect('notify::expanded', expander_active, widget)
        button.connect('button-press-event', button_press, expander)
        button.show_all()
        vbox.show()
        return vbox

    @staticmethod
    def create_stock_button(image = None, text = None, icon_size = gtk.ICON_SIZE_BUTTON, text_position = "right"):
        assert (image is not None) or (text is not None), "Cannot create empty stock button"

        if type(image) == str:
            icon = gtk.image_new_from_stock(image, icon_size)
        else:
            return gtk.Label(text)
        icon.show()

        if text is None:
            return icon

        label = gtk.Label(text)
        label.show()

        if text_position in ('left', 'right'):
            box = gtk.HBox(spacing=4)
        else:
            box = gtk.VBox(spacing=4)

        if text_position in ('left', 'up'):
            box.add(label)
        box.add(icon)
        if text_position in ('right', 'down'):
            box.add(label)

        box.show()
        return box

class PhotoView(GladeApp, object):
    class Size():
        def __init__(self, width, height):
            self.width = width
            self.height = height

    glade = os.path.join('..', os.path.dirname(os.path.dirname(__file__)), 'data', 'photoview.glade')
    window = "vbox1"

    _zoom = 0.0
    _zoom_min = log(0.01)
    _zoom_max = log(8.00)
    _zoom_fit = log(0.1)

    _zoom_origin_x = 0.5
    _zoom_origin_y = 0.5
    zoom_step = 0.1

    images_list = []
    _thumbnails_cache = {}
    parent = None
    thumbnails = []
    selected = []
    _allocation = None
    #image zoom
    def _get_zoom(self):
        return self._zoom

    def _set_zoom_with_callback(self, value, callback = True):
        if value == 'fit':
            value = self._zoom_fit

        if value < self._zoom_min:
            value = self._zoom_min
        if value > self._zoom_max:
            value = self._zoom_max

        if value != self._zoom:
            old = self._zoom
            self._zoom = value
            if value < self._zoom_fit:
                self._zoom_origin_x = 0.5
                self._zoom_origin_y = 0.5

            if callback:
                self.zoom_scale.set_value(value)

            self._apply_zoom_on_image(exp(-old+value))

    def _set_zoom(self, value):
        self._set_zoom_with_callback(value)

    zoom = property(_get_zoom, _set_zoom)

    #currently displayed image
    _image = None
    def _get_image(self):
        return self._image

    def _set_image(self, value):
        self._image = value
        self._compute_fit_zoom()
        self.zoom = 'fit'
        #self._apply_zoom_on_image() #show new image in widget

    image = property(_get_image, _set_image)

    #image index (now displayed) in images_list
    _index = 0
    def _get_index(self):
        return self._index

    def _set_index(self, value):
        if type(value) == int:
            if 0 <= value < len(self.images_list) and self._index != value:
                self._index = value
                self.image = self.current.getOriginalThumbnail()
                self._update_view()

    index = property(_get_index, _set_index)


    #current image node
    def _get_current(self):
        return self.images_list[self.index]
    current = property(_get_current)

    def init(self, parent, params = {}):
        #connect buttons with icons
        self.zoom_fit_button.add(Utils.create_stock_button(gtk.STOCK_ZOOM_FIT))
        self.zoom_100_button.add(Utils.create_stock_button(gtk.STOCK_ZOOM_100))
        self.library_back_button.add(Utils.create_stock_button(gtk.STOCK_GO_BACK, "Back to Library"))
        self.play_slideshow_button.add(Utils.create_stock_button(gtk.STOCK_MEDIA_PLAY, "Play"))
        self.prev_button.add(Utils.create_stock_button(gtk.STOCK_MEDIA_PREVIOUS))
        self.next_button.add(Utils.create_stock_button(gtk.STOCK_MEDIA_NEXT))

        self.selection_add_button.add(Utils.create_stock_button(gtk.STOCK_ADD))
        self.selection_remove_button.add(Utils.create_stock_button(gtk.STOCK_REMOVE))
        self.selection_clear_button.add(Utils.create_stock_button(gtk.STOCK_CLEAR))

        self.add_tag_button.add(Utils.create_stock_button(gtk.STOCK_ADD))

        self.thumbnails = [self.thumbnail1, self.thumbnail2, self.thumbnail3, self.thumbnail4, self.thumbnail5, self.thumbnail6, self.thumbnail7 ]
        self.image_viewport.modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#888A85'))

        #connect eventboxes to thumbnails
        dx = -3
        for eventbox in [self.thumbnail1event, self.thumbnail2event, self.thumbnail3event, self.thumbnail5event, self.thumbnail6event, self.thumbnail7event]:
            eventbox.set_events(gtk.gdk.BUTTON1_MASK)
            eventbox.connect("button_press_event", self.move_to_thumbnail, dx)
            dx+=1
            if dx==0: dx+=1

        #colorize status_line
        self.statusline.modify_fg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#eeeeec'))
        self.statusline_eventbox.modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#5590ba'))
        self.parent = parent

        #connect change-value signals to scrollbars of main image
        #self.scrolled_viewport.get_vscrollbar().connect('change-value', self.change_zoom_origin_x)

        label = gtk.Label("Hello World\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nHello")
        x = Utils.create_expander("QuickFix", label, False)
        self.plugins_box.pack_start(x, False, False)

    def move_to_thumbnail(self, widget, event, number):
        self.index += number


    def _get_thumbnail_from_node(self, node):
        """
        Return square miniature of image (e.g. for thumbnail bar or for
        @param node:
        @return:
        """

        if not node.file in self._thumbnails_cache:
            size = 32
            pb = node.getOriginalThumbnail()
            w,h = (pb.get_width(), pb.get_height())

            #if w < h:
            #    pb = pb.subpixbuf((h - w)/2, 0, w, h)
            #else:
            #    pb = pb.subpixbuf(0, (w - h)/2, w, h)

            #print pb.get_width(), pb.get_height()
            #w = pb.get_width()
            #h = pb.get_height()
            if w > h:
                pb = pb.scale_simple(w*size/h, size, gtk.gdk.INTERP_HYPER)
            else:
                pb = pb.scale_simple(size, h*size/w, gtk.gdk.INTERP_HYPER)

            pb = pb.subpixbuf(0,0,size, size)
            #print pb.get_width(), pb.get_height()
            self._thumbnails_cache[node.file] = pb
        return self._thumbnails_cache[node.file]


    def _update_thumbnails_bar(self):
        if self.index is not None:
            for i in xrange(-3,4):
                if 0<= self.index+i < len(self.images_list):
                    self.thumbnails[i+3].set_from_pixbuf(self._get_thumbnail_from_node(self.images_list[self.index+i]))
                else:
                    self.thumbnails[i+3].set_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_BUTTON)

    def init_data(self, images_list, index, selected=[]):
        self.images_list = images_list
        self.selected = selected
        self.index = index

        self._update_view()


    def unload(self):
        self.images_list = None
        self.index = None
        self.selected = None



    def _update_status_line(self):
        d = self.current.getInfo()
        t = [
            self.current.file,
            Utils.get_human_readable_date(d['exifdate']),
            str(d['resolution'])+' pixels',
            Utils.get_human_readable_byte_count(d['filesize'], False),
            '('+str(self.index+1)+'/'+str(len(self.images_list))+')'
        ]

        self.statusline.set_text('    '.join(t))

    def _update_main_image(self):
        pass
        #if self.image is not None:
        #    self._apply_zoom_on_image()

    def _update_view(self):
        self._update_thumbnails_bar()
        self._update_main_image()
        self._update_status_line()
        self._update_zoom_scale()

    @debug
    def _update_zoom_scale(self):
        """
        Refresh zoom_scale (HScale) widget according to zoom properties
        """
        if self.image is not None:
            self.zoom_scale.clear_marks()
            print (self._zoom_min, self._zoom_max)
            self.zoom_scale.set_range(self._zoom_min, self._zoom_max)

            self.zoom_scale.add_mark(self._zoom_fit, gtk.POS_BOTTOM, "fit")
            self.zoom_scale.add_mark(0.0, gtk.POS_BOTTOM, "100%")
            self.zoom_scale.set_value(self.zoom)

    @debug
    def _compute_fit_zoom(self):
        """
        Set _zoom_fit according to viewport size
        """
        if self.image is None:
            return

        #TODO: change to _get_allocation_size()
        bounds = self._get_allocation_size()
        width, height = bounds.width, bounds.height

        #add some margin
        width-=16
        height-=16

        set_zoom_fit = True if self._zoom_fit == self._zoom else False
        x = width*self.image.get_height()/height

        if x >= self.image.get_width():
            self._zoom_fit = log(float(height)/float(self.image.get_height())) #fill height
        else:
            self._zoom_fit = log(float(width)/float(self.image.get_width())) #fill width

        #TODO: add better values
        self._zoom_min = min( 0.0, self._zoom_fit-2.0)
        self._zoom_max = max(self._zoom_fit+2.0, 0.0)

        #If zoom was fitted, then restore them to 'fit'
        if set_zoom_fit:
            self.zoom = 'fit'

        self._update_zoom_scale()

    def _get_zoomed_size(self):
        if self.image is not None:
            return PhotoView.Size(self.image.get_width()*exp(self.zoom), self.image.get_height()*exp(self.zoom))
        return PhotoView.Size(0,0)

    def _get_allocation_size(self):
        if self._allocation is None:
            self._allocation = self.image_viewport.get_allocation()
        bounds = self._allocation#self.image_viewport.get_allocation()
        return PhotoView.Size(bounds.width, bounds.height)

    @debug
    def _update_adjustments(self):
        zoomed = self._get_zoomed_size()
        alloc = self._get_allocation_size()

        self.image_viewport.get_vadjustment().set_value(max(0.0, self._zoom_origin_y*zoomed.height-0.5*alloc.height))
        self.image_viewport.get_hadjustment().set_value(max(0.0, self._zoom_origin_x*zoomed.width-0.5*alloc.width))
        #self.scrolled_viewport.set_hadjustment(hadj)

    @debug
    def _apply_zoom_on_image(self, ratio):
        """
        Set display_image with applying current zoom property
        """
        if self.image is not None and ratio != 1.0:
            zoomed = self._get_zoomed_size()
            alloc = self._get_allocation_size()

            off_x = -self.image_viewport.get_bin_window().get_position()[0]
            x = alloc.width*self._zoom_origin_x
            dx = off_x+x

            off_y = -self.image_viewport.get_bin_window().get_position()[1]
            y = alloc.height*self._zoom_origin_y
            dy = off_y+y
            print (dx, dy, ratio, self._zoom_origin_x, self._zoom_origin_y)

            self.image_viewport.get_bin_window().freeze_updates()
            self.display_image.set_from_pixbuf(
                self.image.scale_simple(
                    int(zoomed.width),
                    int(zoomed.height),
                    gtk.gdk.INTERP_NEAREST #gtk.gdk.INTERP_HYPER
                )
            )

            alloc = self._get_allocation_size()
            print (dx*ratio-x, dy*ratio-y)
            self.image_viewport.get_hadjustment().set_value(dx*ratio-x)

            self.image_viewport.get_vadjustment().set_value(dy*ratio-y)


            self.image_viewport.get_bin_window().thaw_updates()

    def on_prev_button_clicked(self, event):
        self.index -= 1

    def on_next_button_clicked(self, event):
        self.index += 1

    def on_library_back_button_clicked(self, event):
        #TODO
        self.parent.notebook2.set_current_page(0)
        self.unload()


    @debug
    def on_image_viewport_size_allocate(self, widget, allocation):
        alloc = self._get_allocation_size()

        if alloc.width != allocation.width or alloc.height != allocation.height:
            self._allocation = allocation

            if self.image is not None:
                self._compute_fit_zoom()

        return False


    def on_zoom_fit_button_clicked(self, event):
        self._zoom_origin_x = self._zoom_origin_y = 0.5
        self.zoom = 'fit'

    def on_zoom_100_button_clicked(self, event):
        self._zoom_origin_x = self._zoom_origin_y = 0.5
        self.zoom = 0.0

    def on_zoom_out_eventbox_button_press_event(self, widget, event):
        self._zoom_origin_x = self._zoom_origin_y = 0.5
        self.zoom -= self.zoom_step

    def on_zoom_in_eventbox_button_press_event(self, widget, event):
        self._zoom_origin_x = self._zoom_origin_y = 0.5
        self.zoom += self.zoom_step

    def on_zoom_scale_change_value(self, widget, scroll, value):
        self._zoom_origin_x = self._zoom_origin_y = 0.5
        self._set_zoom_with_callback(value, False)

    @debug
    def on_image_viewport_scroll_event(self, widget, event):
        alloc = self._get_allocation_size()

        orig_x = float(event.x)/float(alloc.width)
        orig_y = float(event.y)/float(alloc.height)

        print (orig_x, orig_y)

        if event.direction == gtk.gdk.SCROLL_UP:
            self._zoom_origin_x = orig_x
            self._zoom_origin_y = orig_y
            self.zoom += self.zoom_step
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            self._zoom_origin_x = orig_x
            self._zoom_origin_y = orig_y
            self.zoom -= self.zoom_step

        return True

if __name__ == "__main__":
    x = PhotoView({'config': 123})
    x.loop()
    #gtk.main()


