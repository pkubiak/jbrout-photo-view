#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pygtk
pygtk.require("2.0")
import gtk
import gtk.glade

class HellowWorldGTK:

	def create_box(self,text):
		# Create box for xpm and label
		box1 = gtk.VBox(False, 0)
		box1.set_border_width(2)
		
		# Now on to the image stuff
		image = gtk.Image()
		image.set_from_stock('gtk-missing-image', gtk.ICON_SIZE_MENU)
		
		# Create a label for the button
		label = gtk.Label(text)
		# Pack the pixmap and label into the box
		box1.pack_start(image, False, False, 3)
		box1.pack_start(label, False, False, 3)
		
		image.show()
		label.show()
		return box1
		
	def __init__(self):
		self.gladefile = "view-gtk2.glade" 
		self.glade = gtk.Builder()
		self.glade.add_from_file(self.gladefile)
		self.glade.connect_signals(self)
		self.glade.get_object("window1").show_all()
		
		self.glade.get_object('eventbox1').modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#729fcf'))
		self.glade.get_object('label4').modify_fg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#eeeeec'))
		self.glade.get_object('viewport1').modify_bg(gtk.STATE_NORMAL,  gtk.gdk.color_parse('#888A85'))
		x = """File name       : ./DSCF4329.JPG
File size       : 4986725 Bytes
MIME type       : image/jpeg
Image size      : 3648 x 2736
Camera make     : FUJIFILM
Camera model    : FinePix S1500     
Image timestamp : 2013:05:24 11:02:59
Image number    : 
Exposure time   : 1/25 s
Aperture        : F2.8
Exposure bias   : 0 EV
Flash           : No, compulsory
Flash bias      : 
Focal length    : 5.9 mm
Subject distance: 
ISO speed       : 800
Exposure mode   : Auto
Metering mode   : Multi-segment
Macro mode      : Off
Image quality   : FINE   
Exif Resolution : 3648 x 2736
White balance   : Auto
Thumbnail       : image/jpeg, 8617 Bytes
Copyright       : 
Exif comment    : 
"""

		
		#dodaj tabelkę z danymi exif
		self.tvcol = gtk.TreeViewColumn('Attribute')
		self.tvcol1 = gtk.TreeViewColumn('Value')

		self.glade.get_object('treeview1').append_column(self.tvcol)
		self.glade.get_object('treeview1').append_column(self.tvcol1)

		X = x.split('\n')
		for i in X:
			y = i.split(':')
			if len(y)==2:
				self.glade.get_object('liststore1').append([y[0].strip(),y[1].strip()])
		
		self.cell = gtk.CellRendererText()
		self.cell1 = gtk.CellRendererText()

		self.tvcol.pack_start(self.cell, True)
		self.tvcol1.pack_start(self.cell1, True)

		self.tvcol.set_attributes(self.cell, text=0)
		self.tvcol1.set_attributes(self.cell1, text=1)
                                      
		#dodaj obrazki do filtrów
		filters = ['Sharpen', 'Blur', 'Posterize', 'Sepia', 'B&W', 'Embose', 'Cubism', 'Auto contrast', 'White balance', 'Normalize', 'Colorize', 'Good luck!']
		ile = 0
		for filter in filters:
			butt = gtk.Button()
			x = self.create_box(filter)
			x.show()
			butt.add(x)
			butt.show()
			self.glade.get_object('table3').attach(butt, ile%3, (ile%3)+1,ile//3,ile//3+1)
			ile+=1
		
		
		
	def on_MainWindow_delete_event(self, widget, event):
		gtk.main_quit()

if __name__ == "__main__":
	try:
		a = HellowWorldGTK()
		gtk.main()
	except KeyboardInterrupt:
		pass
