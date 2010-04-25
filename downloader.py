import subprocess
import shlex
from os import remove
from zlib import crc32
from hashlib import new

try: # See if this is a POSIX machine
    import posix
except:
    POSIX = False
else:
    POSIX = True
    
if not POSIX:
    try:
        import win32api
    except:
        win32api = None
        from os import system
    
def gpgverify(filename, sig):
    """Verify OpenPGP signatures"""
    gpg = subprocess.Popen(
        ['gpg', '--verify', '-', filename],
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        shell=True
        )
    output = gpg.communicate(sig)[1]
    return True if output.search("gpg: Good signature from")!=-1 else False

def hashcheck(filename, hashtype, hashtext):
    try:
        hasher = new(hashtype)
    except:
        if hashtype == 'crc32':
            hasher = CRCWrapper(hashtext)
        else:
            return False
    fle = open(filename)
    txt = fle.read()
    fle.close()
    hashsum = hasher(txt).hexdigest()
    return hashsum == hashtext
    
class CRCWrapper(object):
    """Give a hashlib interface to crc32"""
    def __init__(self, value):
        self.value = value
    def hexdigest(self):
        return crc32(self.value)

class Config(object):
    def __init__(self, configuration):
        self.entries = configuration
        try:
            for line in configuration:
                parts = shlex.split(line, True, False)
                self.entries[parts[0]] = parts[1:]
        except:
            return
    def __getitem__(self, name):
        return self.entries.get(name)
    def __setitem__(self, name, value):
        self.entries[name] = value

class Installer(object):
    def __init__(self, info):
            self.actions = info
    def reboot(self, conf=None):
        if conf and not conf():
                return
        with open('plml.session', 'w') as session:
            session.write(prepSessionString(self.actions))
        if POSIX:
            subprocess.Popen('halt').communicate()
        else:
            if win32api:
                win32api.InitiateSystemShutdown(None, '', 0, True, True)
            else:
                subprocess.Popen('shutdown /r /t 0').communicate()
    def uninstall(file_list):
        for fle in file_list:
            remove(fle)
    def install(file_pairs):
        for n, f in file_pairs:
            with open(n, 'w') as fle:
                fle.write(f)
