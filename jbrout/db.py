# -*- coding: utf-8 -*-

##
##    Copyright (C) 2005 manatlan manatlan[at]gmail(dot)com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
from lxml.etree import Element, ElementTree
#~ import cElementTree as ElementTree
import gc

import pygtk
pygtk.require('2.0')
import gtk
# WILLNEED import gobject


from common import cd2d
from tools import PhotoCmd, supportedFormats
import os
import shutil
import stat
import os.path
import json

from commongtk import Buffer, rgb, Img, MessageBoxScrolled

from subprocess import Popen, PIPE
import char_utils


def walktree(top=".", depthfirst=True):
    try:
        names = os.listdir(top)
    except WindowsError:  # protected dirs in win
        names = []

    if not depthfirst:
        yield top, names
    for name in names:
        try:
            st = os.lstat(os.path.join(top, name))
        except os.error:
            continue
        if stat.S_ISDIR(st.st_mode) and not name.startswith("."):
            for (newtop, children) in walktree(os.path.join(top, name),
                                               depthfirst):
                yield newtop, children
    if depthfirst:
        yield top, names


def dec(s):  # ensure that a return from etree is in utf-8
    if s is not None:
        return s.decode("utf_8")


class ImportError(Exception):
    def __init__(self, txt, file):
        self.txt = txt
        self.file = file
        Exception.__init__(self, txt)


class DBPhotos:
    """
    """
    normalizeName = False
    autorotAtImport = False

    def __init__(self, file):
        if os.path.isfile(file):
            self.root = ElementTree(file=file).getroot()
        else:
            self.root = Element("db")
        self.file = file

        #==== simple basket convertion (without verification)
        # theses lines could be deleted in the future
        try:
            nodeB = self.root.xpath("/db/basket")[0]
        except:
            nodeB = None

        if nodeB:
            # FIXME unused var ln = nodeB.xpath("""/db/basket/p""")
            nodeB.getparent().remove(nodeB)  # adios old basket !
        #==== simple basket convertion (without verification)

    def setNormalizeName(self, v):
        assert v in (True, False)
        DBPhotos.normalizeName = v

    def setNormalizeNameFormat(self, v):
        assert isinstance(v, basestring)
        PhotoCmd.setNormalizeNameFormat(v)

    def setAutorotAtImport(self, v):
        assert v in (True, False)
        DBPhotos.autorotAtImport = v

    def add(self, path, tags={}):
        assert type(path) == unicode
        assert os.path.isdir(path)
        path = os.path.normpath(path)

        importErrors = {}

        ln = self.root.xpath(u"""//folder[@name="%s"]""" % path)
        assert len(ln) <= 1
        if ln:
            nodeFolder = ln[0]
            filesInBasket = [i.file for i in self.getBasket(nodeFolder)]
            nodeFolder.getparent().remove(nodeFolder)
        else:
            filesInBasket = []

        files = []
        for (basepath, children) in walktree(path, False):
            dir = basepath
            try:
                nodeDir = self.root.xpath(u"""//folder[@name="%s"]""" % dir)[0]
            except:
                nodeDir = None

            if nodeDir is None:
                rep = []
                while True:
                    rep.append(dir)
                    dir, n = os.path.split(dir)
                    if not n:
                        break
                rep.reverse()

                node = self.root
                for r in rep:
                    try:
                        nodeDir = node.xpath(u"""folder[@name="%s"]""" % r)[0]
                    except:
                        nodeDir = Element("folder", name=r)
                        node.append(nodeDir)

                        FolderNode(nodeDir)._updateInfo()  # read comments

                    node = nodeDir
                nodeDir = node

            for child in children:
                if child.split('.')[-1].lower() in supportedFormats:
                    file = os.path.join(basepath, child)
                    if os.path.isfile(file):
                        files.append((file, nodeDir))

        yield len(files)   # first yield is the total number of files

        i = 0
        for (file, nodeDir) in files:
            yield i
            i += 1
            #OLD TOOLS:
            #file = PhotoCmd.prepareFile(file,
            #                needRename=DBPhotos.normalizeName,
            #                needAutoRot=DBPhotos.autorotAtImport,
            #                )
            m = self.__addPhoto(nodeDir, file, tags, filesInBasket)
            if m:
                importErrors[file] = m

        ln = self.root.xpath(u"""//folder[@name="%s"]""" % path)
        if ln:
            yield FolderNode(ln[0])
        else:
            yield None
        if len(importErrors) > 0:
            k = importErrors.keys()
            k.sort()
            msgs = []
            for f in k:
                msgs.append('"%s" adding file: "%s"' % (importErrors[f], f))
            MessageBoxScrolled(None, '\n'.join(msgs), 'Jbrout Import Errors')

    def __addPhoto(self, nodeDir, file, tags, filesInBasket):
        assert type(file) == unicode

        newNode = Element("photo")
        nodeDir.append(newNode)

        node = PhotoNode(newNode)
        if file in filesInBasket:
            node.addToBasket()

        try:
            iii = PhotoCmd(file,
                           needAutoRename=DBPhotos.normalizeName,
                           needAutoRotation=DBPhotos.autorotAtImport,
                           )
            if iii.exifdate == "":
                # exif is not present, and photocmd can't reach
                # to recreate minimal exif tags (because it's readonly ?)
                # we can't continue to import this photo
                raise Exception(
                    "Exif couldn't be set in this picture (readonly?)")
        except Exception, m:
            # remove the bad node
            nodeDir.remove(newNode)

            return m
        else:
            importedTags = node.updateInfo(iii)
            for i in importedTags:
                tags[i] = i  # feed the dict of tags

            return None

    def getRootFolder(self):
        if len(self.root) > 0:
            return FolderNode(self.root[0])

    def redoIPTC(self):
        """ refresh IPTC in file and db """
        ln = self.root.xpath(u"""//photo[t]""")
        for i in ln:
            p = PhotoNode(i)
            print p.name
            pc = PhotoCmd(p.file)
            pc.__maj()              # rewrite iptc in file
            p.updateInfo(pc)      # rewrite iptc in db.xml

    def getMinMaxDates(self):
        """ return a tuple of the (min, max) of photo dates
            or none if no photos
        """
        ln = self.root.xpath("//photo")
        if ln:
            ma = 11111111111111
            mi = 99999999999999
            for i in ln:
                a = int(i.attrib["date"])
                ma = max(a, ma)
                mi = min(a, mi)
            return cd2d(str(mi)), cd2d(str(ma))

    def select(self, xpath, fromNode=None):
        ln = self.root.xpath(xpath)
        if ln:
            return [PhotoNode(i) for i in ln]
        else:
            return []

    def toXml(self):
        """ for tests only """
        from StringIO import StringIO
        fid = StringIO()
        fid.write("""<?xml version="1.0" encoding="UTF-8"?>""")
        ElementTree(self.root).write(fid, encoding="utf-8")
        return fid.getvalue()

    def save(self):
        """ save the db, and a basket.txt file """
        fid = open(self.file, "w")
        fid.write("""<?xml version="1.0" encoding="UTF-8"?>""")
        ElementTree(self.root).write(fid, encoding="utf-8")
        fid.close()

        # save a "simple txt file" of basket'files near db.xml
        # (could be used in another prog ?)
        file = os.path.join(os.path.dirname(self.file), "basket.txt")
        if self.isBasket():
            list = [i.file for i in self.getBasket()]

            fid = open(file, "w")
            if fid:
                fid.write((u"\n".join(list)).encode("utf_8"))
                fid.close()
        else:
            try:
                os.unlink(file)
            except:
                pass

    #------------------------------------------------------------------------
    # basket methods
    #------------------------------------------------------------------------
    def isBasket(self):
        return len(self.root.xpath("//photo[@basket='1']")) > 0

    def clearBasket(self):
        ln = self.getBasket()
        for i in ln:
            i.removeFromBasket()

    def getBasket(self, nodeFrom=None):
        if nodeFrom is not None:
            return [PhotoNode(i) for i in
                    nodeFrom.xpath("//photo[@basket='1']")]
        else:
            return [PhotoNode(i) for i in
                    self.root.xpath("//photo[@basket='1']")]

    def exportBasket(self, basketFile):
        """ Export basket to the specified file as simple txt """
        # save a "simple txt file" of basket'files near db.xml
        if self.isBasket():
            list = [i.file for i in self.getBasket()]

            fid = open(basketFile, "w")
            if fid:
                fid.write((u"\n".join(list)).encode("utf_8"))
                fid.close()

    def importBasket(self, basketFile):
        """ Import basket from the specified file as simple txt """
        # save a "simple txt file" of basket'files near db.xml
        countExisting = 0
        countNew = 0
        countError = 0
        fid = open(basketFile, "r")
        if fid:
            lines = fid.readlines()
            fid.close()
            for iline in lines:
                iline = iline.strip()
                if os.path.isfile(iline):
                    dirname = os.path.dirname(iline)
                    basename = os.path.basename(iline)

                    for inode in self.root.xpath(
                        "//folder[@name='%s']/photo[@name='%s']" %
                            (dirname, basename)):
                        #print inode
                        photo = PhotoNode(inode)
                        #print photo
                        if photo.isInBasket:
                            countExisting = countExisting + 1
                        else:
                            countNew += 1
                            photo.addToBasket()
                else:
                    countError += 1
        msg = "imported [" + str(countNew) + "], [" + str(countExisting) + \
              "] already in basket, [" + str(countError) + "] errors"
        return msg


class FolderNode(object):
    """ A folder node containing photo nodes"""
    commentFile = "album.txt"

    def __init__(self, n):
        assert n.tag in ["folder", "db"]
        self.__node = n

    def __getName(self):
        return os.path.basename(self.__node.attrib["name"])
    name = property(__getName)

    #~ def __getIsReadOnly(self):   return not os.access( self.file, os.W_OK)
    #~ isReadOnly = property(__getIsReadOnly)

    def __getFile(self):
        return self.__node.attrib["name"]
    file = property(__getFile)

    def __getComment(self):
        ln = self.__node.xpath("c")
        if ln:
            return dec(ln[0].text)
        else:
            return ""
    comment = property(__getComment)

    def __getExpand(self):
        if "expand" in self.__node.attrib:
            return (self.__node.attrib["expand"] != "0")
        else:
            return True
    expand = property(__getExpand)

    def _getNode(self):  # special
        return self.__node

    def getParent(self):
        return FolderNode(self.__node.getparent())

    def getFolders(self):
        ln = [FolderNode(i) for i in self.__node.xpath("folder")]
        ln.sort(cmp=lambda x, y: cmp(x.name.lower(), y.name.lower()))
        return ln

    def getPhotos(self):
        return self._select("photo")

    def getAllPhotos(self):
        return self._select("descendant::photo")

    def _select(self, xpath):
        """ 'xpath' should only target photo node """
        class PhotoNodes(list):
            def __init__(self, l, xpath):
                list.__init__(self, l)
                self.xpath = xpath

        ln = self.__node.xpath(xpath)
        ll = [PhotoNode(i) for i in ln]
        return PhotoNodes(ll, "//folder[@name='%s']/%s" %
                          (self.file, xpath))

    def setComment(self, t):
        assert type(t) == unicode
        file = os.path.join(self.file, FolderNode.commentFile)
        if t == "":  # if is the "kill comment"
            if os.path.isfile(file):  # if files exists, kill it
                try:
                    os.unlink(file)
                    return True
                except:
                    return False

            return True
        else:
            fid = open(file, "w")
            if fid:
                fid.write(t.encode("utf_8"))
                fid.close()
                self._updateInfo()
                return True
            else:
                return False

    def _updateInfo(self):
        ln = self.__node.xpath("c")
        assert len(ln) in [0, 1]
        if ln:
            nodeComment = ln[0]
        else:
            nodeComment = None

        comment = None
        file = os.path.join(self.file, FolderNode.commentFile)
        if os.path.isfile(file):
            fid = open(file, "r")
            if fid:
                comment = fid.read().decode("utf_8")
                fid.close()

        if comment:
            if nodeComment is None:
                nodeComment = Element("c")
                nodeComment.text = comment
                self.__node.append(nodeComment)
            else:
                nodeComment.text = comment
        else:
            if nodeComment is not None:
                self.__node.remove(nodeComment)

    def setExpand(self, bool):
        if bool:
            self.__node.attrib["expand"] = "1"
        else:
            self.__node.attrib["expand"] = "0"

    def rename(self, newname):
        assert type(newname) == unicode
        oldname = self.file
        newname = os.path.join(os.path.dirname(oldname), newname)
        if not (os.path.isdir(newname) or os.path.isfile(newname)):
            try:
                shutil.move(oldname, newname)
                moved = True
            except os.error, detail:
                raise Exception(detail)
                moved = False

            if moved:
                self.__node.attrib["name"] = newname

                ln = self.__node.xpath("descendant::folder")
                for i in ln:
                    i.attrib["name"] = newname + \
                        i.attrib["name"][len(oldname):]
                return True

        return False

    def createNewFolder(self, newname):
        assert type(newname) == unicode
        newname = os.path.join(self.file, newname)
        ll = [i for i in self.getFolders() if i.file == newname]
        if len(ll) == 1:
            # folder is already mapped in the db/xml
            # so no creation
            return False
        else:
            if not os.path.isfile(newname):
                # it's not a file

                if os.path.isdir(newname):
                    # but it's an existing folder
                    created = True
                else:
                    # this is a real new folder
                    # let's create it in the FS
                    try:
                        os.mkdir(newname)
                        created = True
                    except os.error, detail:
                        raise Exception(detail)
                        created = False

                if created:
                    #so map the folder to a db node
                    nodeDir = Element("folder", name=newname)
                    self.__node.append(nodeDir)
                    return FolderNode(nodeDir)
        return False

    def remove(self):
        """ delete ONLY node """
        self.__node.getparent().remove(self.__node)

    def delete(self):
        """ delete real folder and node """
        if os.path.isdir(self.file):
            try:
                shutil.rmtree(self.file)
                deleted = True
            except os.error, detail:
                raise Exception(detail)
                deleted = False
        else:
            deleted = True

        if deleted:
            self.remove()
            return True

        return False

    def moveToFolder(self, nodeFolder):
        assert nodeFolder.__class__ == FolderNode
        oldname = self.file
        newname = os.path.join(nodeFolder.file, self.name)
        if not (os.path.isdir(newname) or os.path.isfile(newname)):
            try:
                shutil.move(oldname, newname)
                moved = True
            except os.error, detail:
                raise Exception(detail)
                moved = False

            if moved:
                self.__node.attrib["name"] = newname
                self.remove()
                nodeFolder.__node.append(self.__node)

                ln = self.__node.xpath("descendant::folder")
                for i in ln:
                    i.attrib["name"] = newname + \
                        i.attrib["name"][len(oldname):]
                return self
        return False


#~ def pixbuf_from_data(data):
    #~ loader = gtk.gdk.PixbufLoader ('jpeg')
    #~ loader.write (data, len (data))
    #~ pixbuf = loader.get_pixbuf ()
    #~ loader.close ()
    #~ return pixbuf

#~ def do_gui_operation(function, *args, **kw):
    #~ def idle_func():
        #~ gtk.threads_enter()
        #~ try:
            #~ function(*args, **kw)
            #~ return False
        #~ finally:
            #~ gtk.threads_leave()
    #~ gobject.idle_add(idle_func)

#~ class PhotoFile:
    #~ @staticmethod
    #~ def generate(path):
        #~ list=[]
        #~ for i in os.listdir(path):
            #~ if i[-4:].lower() == ".jpg":
                #~ list.append( PhotoFile(os.path.join(path, i)) )
        #~ return list
    #~ generate = staticmethod(generate)

    #~ def __init__(self, f):
        #~ self.file = f
        #~ self.name = os.path.basename(f)

    #~ def getThumb(self):
        #~ try:
            #~ i=Img(thumb=self.file)
            #~ data = i.resizeC(160).getStreamJpeg().read()
            #~ return pixbuf_from_data(data)
        #~ except:
            #~ return None

class PhotoNode(object):
    """
      Class PhotoNode
      to manipulate a node photo in the dom of album.xml.
    """
    def __init__(self, node):
        assert node.tag == "photo"
        self.__node = node

    def __getName(self):
        return self.__node.attrib["name"]
    name = property(__getName)

    def __getfolderName(self):
        return os.path.basename(self.folder)
    folderName = property(__getfolderName)

    def __getIsReadOnly(self):
        return not os.access(self.file, os.W_OK)
    isReadOnly = property(__getIsReadOnly)

    def __getTags(self):
        l = [dec(i.text) for i in self.__node.xpath("t")]
        l.sort()
        return l
    tags = property(__getTags)

    def __getComment(self):
        ln = self.__node.xpath("c")
        if ln:
            return dec(ln[0].text)
        else:
            return ""
    comment = property(__getComment)

    def __getRating(self):  # 0x4746 18246 IFD0 Exif.Image.Rating Short
            ln = self.__node.xpath("r")  # saved decimal like <r>5</r>
            if ln:
                return int(ln[0].text)
            else:
                return 0
    rating = property(__getRating)

    # if exif -> exifdate else filedate
    def __getDate(self):
        return self.__node.attrib["date"]
    date = property(__getDate)

    def __getResolution(self):
        return self.__node.attrib["resolution"]
    resolution = property(__getResolution)

    # if exifdate -> true else false
    def __getReal(self):
        return self.__node.attrib["real"]
    real = property(__getReal)

    def __getFolder(self):
        na = dec(self.__node.getparent().attrib["name"])
        assert type(na) == unicode
        return na
    folder = property(__getFolder)

    def __getFile(self):
        return dec(os.path.join(self.__getFolder(), self.__getName()))
    file = property(__getFile)

    def getParent(self):
        return FolderNode(self.__node.getparent())

    def __getIsInBasket(self):
        return (self.__node.get("basket") == "1")
    isInBasket = property(__getIsInBasket)

    def addToBasket(self):
        self.__node.set("basket", "1")

    def removeFromBasket(self):
        if self.isInBasket:
            del(self.__node.attrib["basket"])

    #~ def __eq__(self, p):
        #~ assert p.__class__ == PhotoNode
        #~ return self.file == p.file
    # throw a bug in lxml ?!?! ;-(

    def getOriginalThumbnail(self):
        """
        Return original thumbnail from exif
        @return:
        @raise:
        """

        try:
            pb = Img(thumb=self.file).pixbuf
        except IOError:  # 404
            pb = Buffer.pixbufNF
        except KeyError:  # no exif
            pb = Buffer.pixbufNT
        except:
            pb = Buffer.pixbufERR
            raise

        return pb

    def getThumb(self):
        """ Get thumb from exif data"""
        if self.real == "yes":  # real photo (exifdate !)
            backGroundColor = None
            pb_nothumb = Buffer.pixbufNT
            pb_notfound = Buffer.pixbufNF
            pb_error = Buffer.pixbufERR
        else:       # photo with hadn't got exif before (exif setted by jbrout)
            backGroundColor = rgb(255, 0, 0)
            pb_nothumb = Buffer.pixbufNTNE
            pb_notfound = Buffer.pixbufNFNE
            pb_error = Buffer.pixbufERRNE

        try:
            i = Img(thumb=self.file)
            pb = i.resizeC(160, backGroundColor).pixbuf
        except IOError:  # 404
            pb = pb_notfound
        except KeyError:  # no exif
            pb = pb_nothumb
        except:
            pb = pb_error
            raise

        return pb

    def getImage(self):
        file = self.file
        # XXX external call while pyexiv2 can't handle it
        extension = os.path.splitext(file)[1].lower()
        if extension == 'nef':
            data = Popen(["exiftool", "-b", "-JpgFromRaw",
                         "%s" % file], stdout=PIPE).communicate()[0]
            loader = gtk.gdk.PixbufLoader('jpeg')
            loader.write(data, len(data))
            im = loader.get_pixbuf()
            loader.close()
            return im
        else:
            return gtk.gdk.pixbuf_new_from_file(file)

    def moveToFolder(self, nodeFolder):
        assert nodeFolder.__class__ == FolderNode

        name = self.name
        while os.path.isfile(os.path.join(nodeFolder.file, name)):
            name = PhotoCmd.giveMeANewName(name)

        try:
            shutil.move(self.file, os.path.join(nodeFolder.file, name))
            moved = True
        except os.error, detail:
            raise Exception(detail)
            moved = False

        if moved:
            self.__node.attrib["name"] = name
            self.__node.getparent().remove(self.__node)
            nf = nodeFolder._getNode()
            nf.append(self.__node)
            return True

    def rotate(self, sens):
        assert sens in ["R", "L"]

        pc = PhotoCmd(self.file)
        pc.rotate(sens)
        self.updateInfo(pc)

    def transform(self, sens):
        assert sens in ["auto", "rotate90", "rotate180", "rotate270",
                        "flipHorizontal", "flipVertical", "transpose",
                        "transverse"]

        pc = PhotoCmd(self.file)
        pc.transform(sens)
        self.updateInfo(pc)

    def setComment(self, txt):
        assert type(txt) == unicode

        pc = PhotoCmd(self.file)
        if pc.addComment(txt):
            self.updateInfo(pc)

    def setRating(self, val):
        assert type(val) == int

        pc = PhotoCmd(self.file)
        if pc.addRating(val):  # always true
            self.updateInfo(pc)

    def addTag(self, tag):
        assert type(tag) == unicode

        pc = PhotoCmd(self.file)
        if pc.add(tag):
            self.updateInfo(pc)

    def addTags(self, tags):
        assert type(tags) == list

        pc = PhotoCmd(self.file)
        if pc.addTags(tags):
            self.updateInfo(pc)

    def delTag(self, tag):
        assert type(tag) == unicode

        pc = PhotoCmd(self.file)
        if pc.sub(tag):
            self.updateInfo(pc)

    def clearTags(self):
        pc = PhotoCmd(self.file)
        if pc.clear():
            self.updateInfo(pc)

    def rebuildThumbnail(self):
        pc = PhotoCmd(self.file)
        pc.rebuildExifTB()
        self.updateInfo(pc)

    def copyTo(self, path, resize=None, keepInfo=True, delTags=False,
               delCom=False):
        """ copy self to the path "path", and return its newfilename or none
            by default, it keeps IPTC/THUMB/EXIF, but it can be removed by
            setting keepInfo at False. In all case, new file keep its filedate
            system

            image can be resized/recompressed (preserving ratio) if resize
            (which is a tuple=(size, qual)) is provided:
                if size is a float : it's a percent of original
                if size is a int : it's the desired largest side
                qual : is the percent for the quality
        """
        assert type(path) == unicode, "photonod.copyTo() : path is not unicode"
        dest = os.path.join(path, self.name)

        while os.path.isfile(dest):
            dest = os.path.join(path,
                                PhotoCmd.giveMeANewName(
                                    os.path.basename(dest)))

        if resize:
            assert len(resize) == 2
            size, qual = resize
            assert type(size) in [int, float]

            pb = self.getImage()  # a gtk.PixBuf
            (wx, wy) = pb.get_width(), pb.get_height()

            # compute the new size -> wx/wy
            if type(size) == float:
                # size is a percent
                size = int(size * 100)
                wx = int(wx * size / 100)
                wy = int(wy * size / 100)

            else:
                # size is the largest side in pixels
                if wx > wy:
                    # format landscape
                    wx, wy = size, (size * wy) / wx
                else:
                    # format portrait
                    wx, wy = (size * wx) / wy, size

            # 3= best quality (gtk.gdk.INTERP_HYPER)
            pb = pb.scale_simple(wx, wy, 3)
            pb.save(dest, "jpeg", {"quality": str(int(qual))})

            if keepInfo:
                pc = PhotoCmd(self.file)
                pc.copyInfoTo(dest)
            del(pb)
            gc.collect()  # so it cleans pixbufs
        else:
            shutil.copy2(self.file, dest)
            if not keepInfo:
                # we must destroy info
                PhotoCmd(dest).destroyInfo()
        if keepInfo:
            if delCom:
                PhotoCmd(dest).addComment(u"")
            if delTags:
                PhotoCmd(dest).clear()

        return dest

    def getInfoFrom(self, copy):
        """ rewrite info from a 'copy' to the file (exif, iptc, ...)
            and rebuild thumb
            (used to ensure everything is back after a run in another program
             see plugin 'touch')
        """
        pc = PhotoCmd(copy)
        pc.copyInfoTo(self.file)

        #and update infos
        # generally, it's not necessary ... but if size had changed, jhead
        # correct automatically width/height exif, so we need to put back in db
        pc = PhotoCmd(self.file)
        self.updateInfo(pc)

    #~ def repair(self):
        #~ pc = PhotoCmd(self.file)
        #~ pc.repair()                 # kill exif tags ;-(
        # recreate "fake exif tags" with exifutils and thumbnails
        #~ pc.rebuildExifTB()
        #~ self.updateInfo(pc)

    def redate(self, w, d, h, m, s):
        pc = PhotoCmd(self.file)
        pc.redate(w, d, h, m, s)
        self.updateInfo(pc)
        self.updateName()

    def setDate(self, date):
        pc = PhotoCmd(self.file)
        pc.setDate(date)
        self.updateInfo(pc)
        self.updateName()

    def updateName(self):
        #photo has been redated
        #it should be renamed if in config ...
        if DBPhotos.normalizeName:
            pc = PhotoCmd(self.file, needAutoRename=True)
            self.updateInfo(pc)

        return True

    def updateInfo(self, pc):
        """ fill the node with REAL INFOS from "pc"(PhotoCmd)
            return the tags
        """
        assert pc.__class__ == PhotoCmd

        wasInBasket = self.isInBasket

        self.__node.clear()
        self.__node.attrib["name"] = os.path.basename(pc.file)
        self.__node.attrib["resolution"] = pc.resolution

        # OLD PhotoCmd
        #~ if pc.exifdate:
            #~ self.__node.attrib["date"]=pc.exifdate
            #~ self.__node.attrib["real"]="yes"
        #~ else:
            #~ self.__node.attrib["date"]=pc.filedate
            #~ self.__node.attrib["real"]="no"

        # NEW PhotoCmd (always a exifdate)
        self.__node.attrib["date"] = pc.exifdate
        if pc.isreal:
            self.__node.attrib["real"] = "yes"
        else:
            self.__node.attrib["real"] = "no"

        if pc.tags:
            for tag in pc.tags:
                nodeTag = Element("t")
                nodeTag.text = tag
                self.__node.append(nodeTag)
        if pc.comment:
            nodeComment = Element("c")
            try:
                nodeComment.text = char_utils.make_xml_string_legal(pc.comment)
            except ValueError, f:
                print "exception = %s" % f
                print "nodeComment = %s" % nodeComment
                print "pc.comment = %s" % pc.comment
                raise
            self.__node.append(nodeComment)
        if pc.rating:
            nodeRating = Element("r")
            nodeRating.text = str(pc.rating)
            self.__node.append(nodeRating)

        if wasInBasket:
            self.addToBasket()

        return pc.tags

    def getInfo(self):
        """
        get real infos from photocmd
        """
        pc = PhotoCmd(self.file)
        info = {}
        info["tags"] = pc.tags
        info["comment"] = pc.comment
        info["exifdate"] = pc.exifdate
        info["rating"] = pc.rating  # huh, did i use that?
        info["filedate"] = pc.filedate
        info["resolution"] = pc.resolution
        info["readonly"] = pc.readonly
        info["filesize"] = os.stat(self.file)[6]

        return info

    def getThumbSize(self):
        """Get the size (width, height) of the thumbnail"""
        try:
            thumbnail = Img(thumb=self.file)
            return (thumbnail.width, thumbnail.height)
        except IOError:  # 404
            return (-1, -1)

    def delete(self):
        try:
            os.unlink(self.file)
            deleted = True
        except os.error, detail:
            raise Exception(detail)
            deleted = False

        if deleted:
            self.__node.getparent().remove(self.__node)
            return True

        return False


# =============================================================================


class DBTags(object):
    def __init__(self, file):
        self.file = file
        if os.path.isfile(file):
            with open(file, 'r') as f:
                try:
                    struct = json.load(f)
                except:
                    struct = {}
            self._root = CatgNode(struct)
        else:
            self._root = CatgNode({})

    def getAllTags(self):
        return reduce(lambda x,y: x if y in x else x+[y],
            sorted([(tag.name, tag.parent.name) for tag in self._root.getAllTags()]), [])
    def save(self):
        struct = self._root._dump()
        with open(self.file, 'w') as f:
            json.dump(struct, f)

    def getRootTag(self):
        return self._root

    def updateImportedTags(self, imported):
        res = None

        for catg in self._root.getCatgs():
            if catg.name == u'Imported Tags':
                res = catg

        if res is None:
            res = self._root.addCatg(u'Imported Tags')

        inserted = 0
        for tag in imported:
            if res.isUnique('tag', tag):
                res.addTag(tag)
                inserted += 1

        return inserted


class TagNode(object):
    def __init__(self, name, parent = None):
        self._name = name.decode('utf-8')
        self._parent = parent

    def _get_name(self):
        return self._name
    name = property(_get_name)

    def _get_parent(self):
        return self._parent
    def _set_parent(self, v):
        self._parent = v
    parent = property(_get_parent, _set_parent)

    key = "123456"
    def remove(self):
        if self._parent is not None:
            self._parent._remove(self)
            self._parent = None

    def moveToCatg(self, catg):
        if self._parent is not None:
            self._parent._remove(self)
        catg._tags.append(self)
        self._parent = catg




class CatgNode(object):

    def __init__(self, structure):
        self._parent = None
        self._name = structure['name'] if (structure.has_key('name') and isinstance(structure['name'], unicode)) else None
        self._expanded = structure['expanded'] if (structure.has_key('expanded') and isinstance(structure['expanded'], bool)) else True

        self._tags = []
        if structure.has_key('tags') and isinstance(structure['tags'], list):
            self._tags = []
            for tag in structure['tags']:
                if isinstance(tag, unicode):
                    self._tags.append(TagNode(tag, self))

        self._catgs = []
        if structure.has_key('categories') and isinstance(structure['categories'], list):
            for catg in structure['categories']:
                if isinstance(catg, dict):
                    try:
                        x = CatgNode(catg)
                        x.parent = self
                        self._catgs.append(x)
                    except:
                        pass

    def _set_parent(self, parent):
        self._parent = parent
    def _get_parent(self):
        return self._parent

    parent = property(_get_parent, _set_parent)

    def _get_name(self):
        return self._name

    name = property(_get_name)

    def _get_expand(self):
        return self._expanded

    def setExpand(self, bool):
        self.expanded = bool

    expand = property(_get_expand, setExpand)

    def _dump(self):
        """
        @return: Reccurence representation of this node in form suitable for json
        """
        return {
            'name': self._name,
            'expanded': self.expand,
            'tags': [tag.name for tag in self._tags],
            'categories': [catg._dump() for catg in self._catgs]
        }



    def _remove(self, item):
        if isinstance(item, TagNode):
            for i in xrange(len(self._tags)):
                if self._tags[i] is item:
                    del self._tags[i]
                    break

        if isinstance(item, CatgNode):
            for i in xrange(len(self._catgs)):
                if self._catgs[i] is item:
                    del self._catgs[i]
                    break


    def moveToCatg(self, c):
        if c.parent is not None:
            c.parent._remove(c)

        if isinstance(c, TagNode):
            self._tags.append(c)
        else:
            self._catgs.append(c)

        c._set_parent(self)

    def addTag(self, t):
        node = TagNode(t.decode('utf-8'), self)
        self._tags.append(node)
        return node

    def addCatg(self, t):
        node = CatgNode({'name': t.decode('utf-8')})
        node._set_parent(self)
        self._catgs.append(node)
        return node


    def isUnique(self, type, name):
        if type == 'tag':
            for tag in self._tags:
                if tag.name == name:
                    return False
        else:
            for catg in self._catgs:
                if catg.name == name:
                    return False

        return True

    def getCatgs(self):
        return reduce(lambda x,y: x if y in x else x+[y], sorted(self._catgs, cmp = lambda x, y: cmp(x.name, y.name)), [])

    def getTags(self):
        return reduce(lambda x,y: x if y in x else x+[y], sorted(self._tags, cmp = lambda x, y: cmp(x.name, y.name)), [])

    def getAllTags(self):
        tags = self.getTags()

        for catg in self._catgs:
            res = catg.getAllTags()
            tags.extend(res)

        #sort and remove duplicates
        return reduce(lambda x,y: x if y in x else x+[y], sorted(tags, cmp = lambda x, y: cmp(x.name, y.name)), [])

    def rename(self, newName):
        self._name = newName

    def remove(self):
        if self.parent is not None:
            for tag in self._tags:
                tag.parent = None
            for catg in self._catgs:
                catg.parent = None
            self.parent._remove(self)
            self.parent = None




if __name__ == "__main__":
    #~ doc = lxml.etree.fromstring("<foo>fd<bar>kk</bar>oi</foo>")
    #~ r = doc.xpath('/foo/bar')
    #~ print len(r)
    #~ print r[0].tag
    #~ print doc.tag
    #~ print doc.text

    db = DBPhotos()
    #db.clearBasket()
    #~ db.add("/home/manatlan/Desktop/tests")

    #~ print db.cpt()
    #~ db.save()
    #~ print db.getRootBasket()

    #~ db=DBTags()
    #~ r=db.getRootTag()

    #~ for i in r.getTags():
        #~ print type(i), i.name
    #~ for i in r.getCatgs():
        #~ print type(i), i.name

    #~ ln = db.select("//photo")
    #~ for i in ln:
        #~ print i.name, i.file
    #~ print ln[0].getParent()
