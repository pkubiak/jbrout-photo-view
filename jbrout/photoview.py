__author__ = 'solmyr'

import gtk
import os
import time
import gobject
from math import log, exp
from jbrout.commongtk import InputQuestion
from jbrout.conf import JBrout
from jbrout.db import PhotoNode
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
    def get_image_from_name(name, size):
        assert isinstance(name, str), "Image name must be a string"

        icon = None
        if gtk.stock_lookup(name):
            icon = gtk.image_new_from_stock(name, size)
        elif gtk.icon_theme_get_default().has_icon(name):
            icon = gtk.image_new_from_icon_name(name, size)
        else:
            path = os.path.join('..', os.path.dirname(os.path.dirname(__file__)), 'data', 'gfx', name+'.png')
            if os.path.exists(path):
                try:
                    size = gtk.icon_size_lookup(size)
                    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(path, size[0], size[1])
                    icon = gtk.image_new_from_pixbuf(pixbuf)
                except:
                    icon = gtk.image_new_from_stock(gtk.STOCK_MISSING_IMAGE)
            else:
                icon = gtk.image_new_from_stock(gtk.STOCK_MISSING_IMAGE)
        return icon

    @staticmethod
    def create_stock_button(image = None, text = None, icon_size = gtk.ICON_SIZE_BUTTON, text_position = "right"):
        assert (image is not None) or (text is not None), "Cannot create empty stock button"

        if type(image) == str:
            icon = Utils.get_image_from_name(image, icon_size)
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

class TagEditorDialog(GladeApp, object):
    glade = os.path.join('..', os.path.dirname(os.path.dirname(__file__)), 'data', 'tageditor.glade')
    window = 'dialog1'
    photo = None

    def run(self):
        self.main_widget.show_all()
        result =  self.main_widget.run()

        if result == gtk.RESPONSE_OK and self.photo:
            tags = sorted(self.get_tags_from_list())
            if tags != self.start_tags:
                print 'Saving Tags', tags

                #FIXME: something more atomic
                self.photo.clearTags()
                self.photo.addTags(tags)

                JBrout.tags.updateImportedTags(tags)

                self.main_widget.destroy()
                return True
            else:
                print 'Tags don\'t changed'

        self.main_widget.destroy()
        return False

    def get_tags_from_list(self):
        tags = []
        for row in self.tags_store:
            tags.append(unicode(row[0], 'utf-8'))

        return tags

    def get_tag_name(self, column, cell, model, iter):
        #cell.set_property('markup', model.get_value(iter, 0))
        cell.set_property('text', model.get_value(iter, 0))
        return False

    def init(self, photo):
        assert isinstance(photo, PhotoNode), "TagEditor can be initialized only from jbrout.db.PhotoNode"

        self.photo = photo

        self.main_widget.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.main_widget.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)


        #all tags for autocompletion purpose
        all_tags = sorted([x[0] for x in JBrout.tags.getAllTags()])
        all_tags = reduce(lambda x,y: x if y in x else x+[y], all_tags, []) #remove duplicates
        print all_tags

        #store for all tags in database
        all_tags_store = gtk.ListStore(gobject.TYPE_STRING)
        for tag in all_tags:
            all_tags_store.append([tag])

        completion = gtk.EntryCompletion()
        self.input_tag.set_completion(completion)
        completion.set_model(all_tags_store)
        completion.set_text_column(0)


        #list of tags for current photo
        self.tags_store = gtk.ListStore(gobject.TYPE_STRING)

        self.start_tags = sorted(photo.tags)
        for tag in photo.tags:
            self.tags_store.append([tag])

        self.tags_list.set_model(self.tags_store)

        #column display tag icon and name
        col1 = gtk.TreeViewColumn('Tag')
        icon = Utils.get_image_from_name('tag', gtk.ICON_SIZE_SMALL_TOOLBAR)
        if icon!=None:
            icon_renderer = gtk.CellRendererPixbuf()

            #FIXME: icon may not be init from pixbuf -> exception
            icon_renderer.set_property('pixbuf', icon.get_pixbuf())
            col1.pack_start(icon_renderer, False)

        name_renderer = gtk.CellRendererText()
        col1.set_expand(True)
        col1.pack_end(name_renderer, True)
        col1.set_cell_data_func(name_renderer, self.get_tag_name)

        self.tags_list.append_column(col1)

        #column displaing close button for tag delete
        col2 = gtk.TreeViewColumn('close')
        col2.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        delete_renderer = gtk.CellRendererPixbuf()
        delete_renderer.set_property('stock-id', gtk.STOCK_CLOSE)
        col2.pack_start(delete_renderer, False)

        self.tags_list.append_column(col2)

    def _add_tag(self, tag_name):
        assert isinstance(tag_name, str), "Tag must be a string"
        tag_name = tag_name.strip()

        for row in self.tags_store:
            if row[0] == tag_name:
                return False

        self.tags_store.append([tag_name])
        return True

    @debug
    def on_input_tag_activate(self, widget):
        """
        Get tag from input and store them for future save.
        @param widget:
        """
        tag = self.input_tag.get_text().strip()
        self._add_tag(tag)
        self.input_tag.set_text("")
        print tag

    @debug
    def on_add_tag_clicked(self, widget):
        self.input_tag.emit('activate')


    def on_tags_list_button_press_event(self, widget, event):
        pos = self.tags_list.get_path_at_pos(int(event.x), int(event.y))
        if event.type == gtk.gdk.BUTTON_PRESS and pos and pos[1].get_title() == 'close':
            print pos
            self.tags_store.remove(self.tags_store.get_iter(pos[0]))
            return True
        return False

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
            if 0 <= value < len(self.images_list):# and self._index != value:
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

        self.selection_add_button.add(Utils.create_stock_button(gtk.STOCK_ADD, icon_size=gtk.ICON_SIZE_MENU))
        self.selection_remove_button.add(Utils.create_stock_button(gtk.STOCK_REMOVE, icon_size=gtk.ICON_SIZE_MENU))
        self.selection_clear_button.add(Utils.create_stock_button(gtk.STOCK_CLEAR, icon_size=gtk.ICON_SIZE_MENU))

        self.star_button.remove(self.star_button.get_child())
        self.star_button.add(Utils.create_stock_button("unstarred"))
        self.star_button.set_property('orientation', gtk.ORIENTATION_HORIZONTAL)
        self.rotate_left_button.add(Utils.create_stock_button("object-rotate-left"))
        self.rotate_right_button.add(Utils.create_stock_button("object-rotate-right"))
        self.add_tag_button.add(Utils.create_stock_button("tag"))

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

        self.image_viewport.connect("button_release_event", self.on_image_viewport_button_release_event)
        self.caption_text.get_buffer().connect_after('changed', self.on_caption_text_changed_event)
        self.caption_text.get_buffer().connect('insert-text', self.on_caption_text_insert_text_event)


    def move_to_thumbnail(self, widget, event, number):
        self.index += number


    def _get_thumbnail_from_node(self, node, refresh = False):
        """
        Return square miniature of image (e.g. for thumbnail bar or for
        @param node:
        @return:
        """

        if not node.file in self._thumbnails_cache or refresh == True:
            size = 32
            pb = node.getOriginalThumbnail()
            w,h = (pb.get_width(), pb.get_height())

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
            os.path.split(self.current.file)[1],
            Utils.get_human_readable_date(d['exifdate']),
            str(d['resolution'])+' pixels',
            Utils.get_human_readable_byte_count(d['filesize'], False),
        ]

        #if photo has tags display it
        if len(self.current.tags)>0:
            t.append('tags: '+', '.join(self.current.tags))

        #add position of current photo (e.g 5/12)
        t.append('('+str(self.index+1)+'/'+str(len(self.images_list))+')')

        self.statusline.set_text('    '.join(t))

    def _update_main_image(self):
        self.image = self.current.getOriginalThumbnail()

        if self.image is not None:
            self._apply_zoom_on_image(0.0)

    @debug
    def _update_comment(self):
        print 'Comment: '+str()
        x = self.current.comment
        if x == '':
            x = 'Make a Caption!'
        self.caption_text.get_buffer().set_text(x)

    def _update_view(self):
        self._update_thumbnails_bar()
        self._update_main_image()
        self._update_status_line()
        self._update_zoom_scale()
        self._update_comment()

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
            #print (dx, dy, ratio, self._zoom_origin_x, self._zoom_origin_y)

            self.image_viewport.get_bin_window().freeze_updates()
            self.display_image.set_from_pixbuf(
                self.image.scale_simple(
                    int(zoomed.width),
                    int(zoomed.height),
                    gtk.gdk.INTERP_NEAREST #gtk.gdk.INTERP_HYPER
                )
            )

            alloc = self._get_allocation_size()
            #print (dx*ratio-x, dy*ratio-y)
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


    def on_scrolled_viewport_scroll_event(self, widget, event):
        alloc = self._get_allocation_size()
        #zoomed = self._get_zoomed_size()

        print (event.x, event.y)

        orig_x = float(event.x)/float(alloc.width)
        orig_y = float(event.y)/float(alloc.height)

        #orig_x = float(event.x)/float(zoomed.width)
        #orig_y = float(event.y)/float(zoomed.height)

        # print (orig_x, orig_y)

        if event.direction == gtk.gdk.SCROLL_UP:
            self._zoom_origin_x = orig_x
            self._zoom_origin_y = orig_y
            self.zoom += self.zoom_step
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            self._zoom_origin_x = orig_x
            self._zoom_origin_y = orig_y
            self.zoom -= self.zoom_step

        return True


    def on_scrolled_viewport_motion_notify_event(self, widget, event):
        return False


    def on_image_viewport_button_press_event(self, widget, event):
        print (event.x, event.y, event.button, )
        return False

    def on_image_viewport_button_release_event(self, widget, event):
        print (event.x, event.y, event.button, )
        return False

    def _save_comment(self, comment):
        if type(comment) == str:
            comment = unicode(comment)
        print 'Setting comment: '+comment+' '+str(type(comment))
        self.current.setComment(comment)

    def on_caption_text_focus_in_event(self, widget, event):
        """
        On focus-in update caption
        @param widget:
        @param event:
        @return:
        """
        widget.get_buffer().set_text(self.current.comment)
        return False

    def on_caption_text_focus_out_event(self, widget, event):
        """
        On focus-out save caption as jpeg comment
        @param widget:
        @param event:
        @return:
        """
        buffer = widget.get_buffer()
        caption = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter()).strip()
        self._save_comment(caption)
        if caption == '':
            buffer.set_text('Make a caption!')

        return False

    @debug
    def on_caption_text_insert_text_event(self, buffer, iter, text, length):
        """
        If user pressed enter, leave focus
        @param buffer:
        @param iter:
        @param text:
        @param length:
        """
        if text == '\n':
            print 'Entered: '+buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())

            self.caption_text.get_toplevel().child_focus(gtk.DIR_TAB_FORWARD)


    #@debug
    def on_caption_text_changed_event(self, buffer):#, iter, text, length):
        """
        Remove new lines "\n" and multiple spaces from caption text
        @param buffer:
        @return:
        """
        old_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter()) #get caption text

        if old_text.find('\n') != -1 or old_text.find('  ') != -1: #is something to update?
            old_text = old_text.replace('\n', '') #replace newline

            import re
            old_text = re.compile('[ ]{2,}').subn(' ', old_text)[0] #replace multiple spaces

            print old_text
            buffer.set_text(old_text) #update caption text

        return True

    @debug
    def on_caption_remove_eventbox_button_press_event(self, widget, event):
        if event.button == 1: #detect left button press
            if self.current.comment != "":
                ans = InputQuestion(self.parent.main_widget,
                                    "Do you want to remove comment?",
                                    buttons = (gtk.STOCK_NO, gtk.RESPONSE_CANCEL, gtk.STOCK_YES, gtk.RESPONSE_OK))
                if ans:
                    self.current.setComment(u"")
                    self._update_comment()

    @debug
    def on_add_tag_button_clicked(self, widget):
        tag_editor = TagEditorDialog(self.current)
        if tag_editor.run():
            self._update_status_line()

    def on_rotate_right_button_clicked(self, widget):
        self.current.rotate('R')
        self._get_thumbnail_from_node(self.current, True)
        self._update_view()

    def on_rotate_left_button_clicked(self, widget):
        self.current.rotate('L')
        self._get_thumbnail_from_node(self.current, True)
        self._update_view()


if __name__ == "__main__":
    pass
    #x = PhotoView({'config': 123})
    #x.loop()
    #gtk.main()


