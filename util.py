from tempfile import NamedTemporaryFile
from anydbm import open as dbopen
from xml.parsers import expat
from urllib2 import urlopen
from zlib import crc32
import collections
import subprocess
import hashlib
import locale
import shlex
import abc

class Hashes(collections.defaultdict):
    def __missing__(self, key):
        if self.default_factory:
            return self.default_factory()
        return hashlib.new(key)
    def __call__(self, name, value):
        if hasattr(self[name], '__call__'):
            return self[name](value)
        hsh = self[name].copy()
        hsh.update(value)
        return hsh.hexdigest()
        

class Verifier(collections.Iterator):
    """Verify a file"""
    def __init__(self, verinfo, fileobj):
        self.vers = iter(verinfo)
        self.ftxt = fileobj.read()
        fileobj.close()
        self.hashes = Hashes(crc32=crc32,
                     md5=hashlib.md5(),
                     sha1=hashlib.sha1(),
                     sha224=hashlib.sha224(),
                     sha256=hashlib.sha256(),
                     sha384=hashlib.sha384(),
                     sha512=hashlib.sha512(),
                     )
        self.signatures = Hashes() # For extension by the user
    def __iter__(self):
        return self
    def next(self):
        """Check the next verification info"""
        ver = self.vers.next()
        if ver[0] == 'hash' or ver[0]=='signature':
            typ = ver[1]
        else:
            typ = ver[0]
        if ver[0]!='signature':
            hsh = self.hashes(typ, self.ftxt)
            return (typ,hsh==ver[2])
        if typ=='pgp':
            try:
                return self.verify_gnupg(ver[2])
            except:
                pass
        return self.signatures('pgp', ver[2])
    def verify_gnupg(self, sig):
        sigfile = NamedTemporaryFile('w',suffix='.sig',prefix='plml',delete=False)
        name = sigfile.name
        sigfile.close()
        gnupg = subprocess.Popen(['gpg', '--verify', name, '-'],
                                 stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 shell=True)
        output = gnupg.communicate(self.ftxt)[1].splitlines()
        return any('Good signature from' in l for l in output)

class Database(collections.Mapping):
    """Base for several classes used here
       Provides a standard mapping interface"""
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def __index__(self):
        """Used to create the hash value and also by some other functions
           Its return value can be any integer, although the hash of a
           given filename is generally perferred for uniqueness sake"""
        pass
    
    def __getattr__(self, name):
        """Fills in the missing attributes
           so derived classes don't have to"""
        if name=='__setitem__' or name=='__delitem__':
            return NotImplemented
        return getattr(self.db, name)
    
    def __hash__(self):
        """Simple hash function
           Should be unique
           in most cases"""
        return len(self.db)*self.__index__()
    # Methods required by the Mapping definition
    def __getitem__(self, name):
        return self.db[name]

    def __len__(self):
        return len(self.db)

    def __iter__(self):
        return iter(self.db)
    
class Config(Database):
    """Get options from a config file
       Uses *nix shell-like syntax
       For each line in the file
       the first token is the key and
       the rest of the line is the value"""
    def __init__(self, name='plml.cfg'):
        fle = open(name)
        self.__hsh = hash(name)
        self.db = dict()
        # With comments, sourcehooks, and GNU-style syntax
        lexers = (shlex.shlex(l, name) for l in fle)
        for lex in lexers:
            lex.whitespace_split = True
            lex.source = '!source'
            key = next(lex,None)
            if not key:
                continue
            options = list(lex)
            self.db[key] = options
        def __index__(self):
            return self.__hsh

class Langs(Database):
    """Provides for a database of
       ISO 3166-1 country codes
       thanks to the guys and gals
       at the Singularity confrence"""
    def __init__(self, name='lang.db'):
        self.db = dbopen(name, 'c')
        self.__hsh = hash(name)
        self.__index__ = name.__hash__
        locale.setlocale(locale.LC_CTYPE)
    def _doupdate(self, name, attrs):
        """Helper function used by the expat parser"""
        if name == 'country':
            self.db[attrs['code']] = attrs['name']
    def getcurloc(self):
        """Parse a locale string to get the current country"""
        return locale.getlocale()[0].split('_')[1]
    def update(url="http://opencountrycodes.appspot.com/xml"):
        """Update the code database from opencountrycodes
           Expat is used here for performance reasons rather
           than lxml, as this is a very simple procedure"""
        page = urlopen(url)
        parser = expat.ParserCreate()
        parser.StartElementHandler = self._doupdate
        parser.ParseFile(page)
        page.close()
    def __index__(self):
        return self.__hsh
