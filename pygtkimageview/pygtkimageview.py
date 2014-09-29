#! /usr/bin/python2
__author__ = 'pkubiak'

try:
    import gtk
    import gobject
    from gtk import gdk
except:
    raise SystemExit


import pygtk


class GtkImageView(gtk.Widget):
    @property
    def _viewport_width(self):
        return self._zoom_width#+2*self._padding+2*(self._border_size if self._show_border else 0)+(self._shadow_size if self._show_shadow else 0)

    @property
    def _viewport_height(self):
        return self._zoom_height#+2*self._padding+2*(self._border_size if self._show_border else 0)+(self._shadow_size if self._show_shadow else 0)

    @property
    def _zoom_width(self):
        return int(self._image_width*self._zoom)

    @property
    def _zoom_height(self):
        return int(self._image_height*self._zoom)

    @property
    def zoom(self):
        return self._zoom

    @zoom.setter
    def zoom(self, value):
        self._zoom = min(1000.0, max(0.01, value))

    __gproperties__ = {
        'min-zoom': (gobject.TYPE_FLOAT, 'minimum zoom', '', 0.0, 1.0, 0.02, gobject.PARAM_READWRITE),
        'max-zoom': (gobject.TYPE_FLOAT, 'maximum zoom', '', 1.0, 1000.0, 20.0, gobject.PARAM_READWRITE),
        'show-scrollbars' : (gobject.TYPE_BOOLEAN, 'show scrollbars', '', True, gobject.PARAM_READWRITE),
        'show-shadow' : (gobject.TYPE_BOOLEAN, 'show shadow around the image', '', False, gobject.PARAM_READWRITE),
        'show-border' : (gobject.TYPE_BOOLEAN, 'show border around the image', '', True, gobject.PARAM_READWRITE),
        #TODO: make it unbounded
        'fit-zoom': (gobject.TYPE_FLOAT, 'fit zoom', 'zoom when image fit viewport', 0.00, 1e20, 1.0, gobject.PARAM_READABLE),
        'zoom': (gobject.TYPE_FLOAT, 'current zoom', '', 0.0, 1000.0, 1.0, gobject.PARAM_READWRITE),
        'horizontal-center' : (gobject.TYPE_FLOAT, 'horizontal center', '', 0.0, 1.0, 0.5, gobject.PARAM_READWRITE),
        'vertical-center' : (gobject.TYPE_FLOAT, 'vertical center', '', 0.0, 1.0, 0.5, gobject.PARAM_READWRITE),
        'padding-size' : (gobject.TYPE_INT, 'padding around image', '', 0, 100, 8, gobject.PARAM_READWRITE),
    }

    __gsignals__ = {
        'zoom-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_FLOAT, )),
        'zoom-scale-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_FLOAT, gobject.TYPE_FLOAT, gobject.TYPE_FLOAT,)),
        'image-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),

    }

    def __init__(self):
        gtk.Widget.__init__(self)

        #initialize properties
        self._border_size = 1
        self._shadow_size = 1

        self._min_zoom = 0.02
        self._max_zoom = 20.0
        self._show_scrollbars = True
        self._show_shadow = False
        self._show_border = False

        #other parameters
        self._fit_zoom = -1.0 #zoom when image fill whole view
        self._zoom = 1.0 #current image zoom
        self._hcenter = 0.5 #horizontal position of viewport center relative to image
        self._vcenter = 0.5 #vertical ....
        self._padding = 0

        self._image = None
        self._image_width = self._image_height = 0
        self._display = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, 1000, 1000)

        #part of zoomed _image currently displayed on _display
        self._viewport = gtk.gdk.Rectangle(0,0,0,0)

        #self._hscroll

    def do_realize(self):
        self.set_flags(self.flags() | gtk.REALIZED)

        self.window = gtk.gdk.Window(
			self.get_parent_window(),
    		width=self.allocation.width,
			height=self.allocation.height,
			window_type=gdk.WINDOW_CHILD,
			wclass=gdk.INPUT_OUTPUT,
			event_mask=self.get_events() | gtk.gdk.ALL_EVENTS_MASK)

        self.window.set_user_data(self)

        self.style.attach(self.window)

        self.style.set_background(self.window, gtk.STATE_NORMAL)
        self.window.move_resize(*self.allocation)

        self.gc = self.style.fg_gc[gtk.STATE_NORMAL]

        self.queue_resize()


    def do_unrealize(self):
        # The do_unrealized method is responsible for freeing the GDK resources
		# De-associate the window we created in do_realize with ourselves
		self.window.destroy()

    def do_get_property(self, property):
        if property.name == 'min-zoom':
            return self._min_zoom
        if property.name == 'max-zoom':
            return self._max_zoom
        if property.name == 'show-scrollbars':
            return self._show_scrollbars
        if property.name == 'show-shadow':
            return self._show_shadow
        if property.name ==' show-border':
            return self._show_border
        if property.name == 'fit-zoom':
            return self._fit_zoom
        if property.name == 'zoom':
            return self._zoom
        if property.name == 'horizontal-center':
            return self._hcenter
        if property.name == 'vertical-center':
            return self._vcenter
        if property.name == 'padding-size':
            return self._padding_size

        raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'min-zoom':
            self._min_zoom = value
        elif property.name == 'max-zoom':
            self._max_zoom = value
        elif property.name == 'show-scrollbars':
            self._show_scrollbars = value
            #self.set_show_scrollbars(value)
        elif property.name == 'show-shadow':
            self._show_shadow = value
        elif property.name == 'show-border':
            self._show_border = value
        elif property.name == 'zoom':
            self.zoom = value
        elif property.name == 'horizontal-center':
            self._hcenter = value
        elif property.name == 'vertical-center':
            self._vcenter = value
        elif property.name == 'padding-size':
            self._padding = value
        else:
            raise AttributeError, 'unknown property %s' % property.name

        self._image_resize()
        self._image_draw()



    # image has been moved, try to uprender new part
    def _image_move(self):
        xpos = self.allocation.width/(2.0*self._zoom_width) #
        if xpos >= 0.5:
            hcenter = 0.5
        else: hcenter = max(min(self._hcenter, 1.0-xpos), xpos)

        ypos = self.allocation.height/(2.0*self._zoom_height) #
        if ypos >= 0.5:
            vcenter = 0.5
        else: vcenter = max(min(self._vcenter, 1.0-ypos), ypos)

        x0 = max(0, int(self._zoom_width * hcenter)-self.allocation.width/2)
        x1 = min(x0+self.allocation.width-1, self._zoom_width - 1)

        y0 = max(0, int(self._zoom_height * vcenter) - (self.allocation.height / 2) + 1)
        y1 = min(int(self._zoom_height * vcenter) + ((self.allocation.height+1) / 2), self._zoom_height - 1)

        viewport = gtk.gdk.Rectangle(#x,y,w,h
            x0, y0, x1-x0+1, y1-y0+1
        )

        # TODO: move some visible part on right place

        self._viewport = viewport
        #self._image.scale(self._display, 0, 0, viewport.width, viewport.height, min(0.0,(self.allocation.width-self._zoom_width)/2.0), min(0.0,(self.allocation.height-self._zoom_height)/2.0), self._zoom, self._zoom, gtk.gdk.INTERP_NEAREST)
        self._image.scale(self._display, 0, 0, viewport.width, viewport.height, -viewport.x, -viewport.y, self._zoom, self._zoom, gtk.gdk.INTERP_NEAREST)
        #self._image.scale(self._display, 0, 0, int(self._image_width*self._fit_zoom), int(self._image_height*self._fit_zoom), 0, 0, self._zoom, self._zoom, gtk.gdk.INTERP_NEAREST)
        pass

    # zoom has changed
    def _image_resize(self):
        if self._image is not None:
            self._viewport = gtk.gdk.Rectangle(0,0,0,0)
            self._image_move()
            #self.queue_draw()

    def _image_draw(self):
        if self.window is not None:
            if self._zoom_width < self.allocation.width:
                overx = self.allocation.width-self._zoom_width
                self.window.clear_area(0, 0, overx/2, self.allocation.height)
                self.window.clear_area(self.allocation.width-overx/2, 0, overx/2, self.allocation.height)
            if self._zoom_height < self.allocation.height:
                overy = self.allocation.height-self._zoom_height
                self.window.clear_area(0, 0, self.allocation.width, overy/2)
                self.window.clear_area(0, self.allocation.height-overy/2, self.allocation.width, overy/2)


            self.window.draw_pixbuf(None, self._display, 0, 0, (self.allocation.width-self._viewport.width)/2, (self.allocation.height-self._viewport.height)/2, self._viewport.width, self._viewport.height, gtk.gdk.RGB_DITHER_NONE, 0, 0)

    def do_size_allocate(self, allocation):
        print allocation
        if self.flags() & gtk.REALIZED:
            self.set_allocation(allocation)
            self.window.move_resize(*allocation)

            if self._image is not None:
                if allocation.width > self._display.get_width() or allocation.height > self._display.get_height():
                    self._display = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, int(1.5*self._display.get_width()), int(1.5*self._display.get_height()))
                old_fit_zoom = self._fit_zoom

                self._fit_zoom = min(
                    float(allocation.height - self._viewport_width + self._zoom_width) / self._image_height,
                    float(allocation.width - self._viewport_height + self._zoom_height) / self._image_width
                )

                if self._zoom == old_fit_zoom:
                    self.zoom = self._fit_zoom

                self._image_resize()


    def do_size_request(self, requisition):
        requisition.height = 300
        requisition.width = 300

    def do_expose_event(self, event):
        assert isinstance(self.allocation, gtk.gdk.Rectangle)

        xoffset = self.allocation.width/2-int(self._vcenter*self._viewport_width)
        yoffset = self.allocation.height/2-int(self._hcenter*self._viewport_height)

        self._image_draw()

    def _event_to_viewport(self, event):
        xgap = self._viewport.x-(self.allocation.width-self._viewport.width)/2
        ygap = self._viewport.y-(self.allocation.height-self._viewport.height)/2
        x = xgap + event.x # in zoom_image coordinate
        y = ygap + event.y # ----- || -------
        return (x,y)

    def do_button_press_event(self, event):
        if event.button ==  1:
            x, y = self._event_to_viewport(event)

            if 0 <= x < self._zoom_width and 0 <= y < self._zoom_height:
                self._drag = (x, y)
            else: self._drag = None
        if event.button == 3:
            self.zoom *= 2.0
            self._image_resize()
            self._image_draw()

    def do_button_release_event(self, event):
        if event.button ==  1:
            self._drag = None

    def do_motion_notify_event(self, event):
        if (event.state & gtk.gdk.BUTTON1_MASK != 0) and self._drag is not None:
            x, y = self._event_to_viewport(event)
            event.x = float(self.allocation.width/2)
            event.y = float(self.allocation.height/2)
            x2,y2 = self._event_to_viewport(event)# p

            self._hcenter = min(1.0, max(0.0, float(self._drag[0] - x + x2)/self._zoom_width))
            self._vcenter = min(1.0, max(0.0, float(self._drag[1] - y + y2)/self._zoom_height))

            self._image_move()
            self._image_draw()



    def do_scroll_event(self, event):
        x, y = self._event_to_viewport(event)

        old = self._zoom
        if event.direction == gtk.gdk.SCROLL_DOWN:
            self.zoom *= 0.5

        if event.direction == gtk.gdk.SCROLL_UP:
            self.zoom *= 2.0

        if old != self._zoom:
            self._hcenter = (x*self._zoom/old-event.x+self.allocation.width/2)/self._zoom_width
            self._vcenter = (y*self._zoom/old-event.y+self.allocation.height/2)/self._zoom_height
            self._image_resize()
            self._image_draw()

    def set_image(self, image):
        """
        Set currently display image to `image` and reset view properties (zoom, centers, ..)

        @param image: new image
        @return: None
        """
        self._image = image
        self._image_width = image.get_width()
        self._image_height = image.get_height()
        self.queue_resize()


    def set_image_seamless(self, image):
        """
        Set current image to `image`, but try to adjust view properties in the way that if new image is better version
        of old one than change should be seamleas.

        @param image: new image
        @return: None
        """
        pass

    def set_zoom(self, zoom):
        """
        @param zoom:
        @return:
        """
        pass

    def center_at(self, xpos, ypos):
        pass



gobject.type_register(GtkImageView)

if __name__ == "__main__":
    import sys

    window = gtk.Window()
    window.set_size_request(300, 200)
    window.connect('destroy-event', gtk.mainquit)
    giv = GtkImageView()
    if len(sys.argv)>1:
        giv.set_image(gtk.gdk.pixbuf_new_from_file(sys.argv[1]))
    window.add(giv)
    window.show_all()

    #print dir(giv)
    gtk.main()

    #create single window with images
