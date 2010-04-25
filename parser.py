from lxml import etree
from time import strptime
from os.path import splitext
from urlparse import urlparse
from datetime import datetime, timedelta

def doif(func, *args, **kwargs):
    if args[0] or kwargs[0]:
        try:
            return func(*args, **kwargs)
        except:
            pass

class InvalidMetalink(Exception):
    def __init__(self, tree):
        self.tree = tree
    def __str__(self):
        return "Invalid Metalink file"
    
class Version(object):
    def __init__(self, string):
        self.string = string
        self.__str__ = self.string.__str__
        try:
            parts = map(int,string.split('.'))
            vsdct = dict((n, parts[n]) for n in xrange(len(parts)))
            self.major = vsdct.get(0)
            self.minor = vsdct.get(1)
            self.revision = vsdct.get(2)
            self.patch = vsdct.get(3)
            self.build = vsdct.get(4)
            try:
                self.tail = parts[5:]
            except IndexError:
                self.tail = None
        except:
            self.major,self.minor,self.revision,self.patch,self.build,self.tail=(None,)*6
    def __getitem__(self, name):
        strct = {
            0:self.major,
            1:self.minor,
            2:self.revision,
            3:self.patch,
            4:self.build
            }.get(name)
        if strct is None:
            try:
                return int(self.string.split('.')[name])
            except:
                return
        return strct
                
class Element(object):
    def __init__(self, **kwargs):
        [setattr(self, n, v) for n,v in kwargs.items()]
    _fmdct = lambda self: dict(
        (n,v) for n,v in self.__dict__.items() if not n[0]=='_'
        )
    def __str__(self):
        return ', '.join('{0}:{1!s}'.format(
            n,v) for n,v in self._fmtdct().items())
    def __repr__(self):
        return (name if name!='__main__' else '')+'Element('+', '.join(
            '{0}={1!r}'.format(
            n,v)for n,v in self._fmtdct().items())+')'
    def __contains__(self, item):
        return item in self._fmtdct()
    def __iter__(self):
        return self
         
class Info(Element):
    def __init__(self, elem):
        self.id = elem.tag
        self.name = elem.findtext('name')
        self.url = Url(elem.find('url'))
        self.tinfo=[self.id, self.name, self.url.uri]
        self.__iter__ = self.tinfo.__iter__
    def __str__(self):
        return '{0}: {1} <{2}>'.format(*self.tinfo)

class Tags(Element):
    def __init__(self, elem):
        text = elem.text
        self.tags = [n.strip() for n in text.split(',')]
        self.__contains__ = self.tags.__contains__
        self.__iter__ = self.tags.__iter__
    def __str__(self):
        return ', '.join(self.tags)

class Multimedia(Element):
    def __init__(self, elem):
        self.info = dict()
        for typ in elem:
            typd = dict()
            for attr in typ:
                txt = attr.text
                if txt.isdigit():
                    txt = int(txt)
                elif ':' in txt:
                    try:
                        dtm = txt.split(':')
                        txt = timedelta(minutes=dtm[0],seconds=dtm[1])
                    except:
                        txt = dtm
                elif 'x' in txt:
                    tml = [x.strip() for x in txt.split('x')]
                    if [t.isdigit() for t in tml].all():
                        txt = tml
                typd[attr.tag] = txt
            self.info[typ.tag] = typd
            self.__iter__ = self.info.__iter__
            
class Upgrade(object):
    def __init__(self, actionlist, filename):
        self.actions = (filename, [n.strip() for n in actionlist.split(',')])
    def isvalid(self):
        actions = self.actions[1]
        if actions is ['install']:
            return True
        if actions is ['uninstall', 'install']:
            return True
        if actions is ['uninstall', 'reboot', 'install']:
            return True
        return False
    def __contains__(self, name):
        return self.actions[1].__contains__(name)
    
class Url(Element):
    def __init__(self, elem):
        self.uri = elem.text
        self.type = elem.get('type') or urlparse(self.uri)[0]
        if splitext(self.uri)[1] == '.torrent':
            self.type = 'torrent'
        self.preference = doif(int, elem.get('preference'))
        self.maxconnections = doif(int, elem.get('maxconnections'))
        self.location = elem.get('location')
        self.__iter__ = elem.__iter__

class File(Element):
    def __init__(self, elem):
        self.name = elem.get('name')
        self.id = elem.findtext('identity')
        self.os = elem.findtext('os')
        self.description = elem.findtext('description')
        self.size = int(elem.findtext('size', -1))
        vf = elem.find('verification')
        self.verinfo = list()
        if vf:
            for ver in vf:
                vertp = ver.get('type')
                vertxt = ver.text
                vertg = ver.tag
                self.verinfo.append((vertg, vertp, vertxt))
        self.mimetype = elem.findtext('mimetype')
        self.relations = elem.findtext('relations')
        self.release_date = doif(datetime.strptime,elem.findtext('releasedate'),
            "%Y-%m-%d-%H:%M:%S")
        self.changelog = elem.findtext('changelog')
        self.publisher = doif(Info, elem.find('publisher'))
        self.license = doif(Info, elem.find('license'))
        self.copyright = elem.findtext('copyright')
        self.tags = doif(Tags, elem.findtext('tgs'))
        self.resources = elem.finditer('resources')
    def next(self):
        return Url(self.resources.next)
        
class Metalink(Element):
    def __init__(self, metalink, config={'schema':'metalink.xsd'}):
        self.config = config
        try:
            tree = etree.parse(metalink)
            xmls = lxml.etree.parse(self.config['schema'])
            schema = lxml.etree.XMLSchema(xmls)
            schema.assertValid(tree)
        except:
            raise InvalidMetalink(tree)
        mvs = tree.getroot().get('version')
        self.meta_version = Version(mvs) if mvs else None
        rd = tree.getroot().get('pubdate')
        self.release_date = datetime.strptime(rd, "%Y-%m-%d-%H:%M:%S") if rd else None
        rfshd = tree.getroot().get('refreshdate')
        self.refresh_date = datetime.strptime(rfshd, "%Y-%m-%d-%H:%M:%S") if rfshd else None
        self.isdynamic = tree.getroot().get('type') == 'dynamic'
        self.src = (
            tree.getroot().get('origin'),
            tree.getroot().get('generator')
            )
        self.info = dict()
        for elem in tree.getroot():
            if elem.tag == 'files':
                self.files = elem.finditer('files')
                continue
            if len(elem):
                itm = Info(elem)
            elif elem.tag == 'version':
                itm = Version(elem.text)
            elif elem.tag == 'tags':
                itm = Tags(elem)
            else:
                itm = elem.text
            self.info[elem.tag] = itm
    def next(self):
        return File(self.files.next())
