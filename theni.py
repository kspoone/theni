#!/usr/bin/env python

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import xml.etree.ElementTree as ET
import base64
import pysvn
import logging as log
import os
import urlparse
import time
from wsgiref.handlers import format_date_time


log.basicConfig(level=log.INFO, format='%(levelname)s %(message)s')

user_db = {
    'loeffler' : ('Karsten Loeffler', '...'),
    'testuser' : ('Test User', '...'),
    }


object_type_db = {
    '{9A9A3E90-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys POU', 'pou'),
    '{9A9A3E91-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Data Unit Type', 'dut'),
    '{9A9A3E92-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Global Variable List', 'gvl'),
    '{9A9A3E93-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Visualisation', 'vis'),
    '{9A9A3E94-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys CNC List', 'cnc'),
    '{9A9A3E95-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Library Manager', 'lim'),
    '{9A9A3E96-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Target Settings', 'trs'),
    '{9A9A3E97-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Tool Instance', 'tio'),
    '{9A9A3E98-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Tool Manager', 'tmo'),
    '{9A9A3E99-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Object Dictionary', 'od'),
    '{9A9A3E9A-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys PLC Configuration', 'pcf'),
    '{9A9A3E9B-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Project Information', 'pin'),
    '{9A9A3E9C-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Task Configuration', 'tco'),
    '{9A9A3E9D-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Trace', 'tce'),
    '{9A9A3E9E-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Watch Manager', 'wen'),
    '{9A9A3E9F-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Symbol Information', 'sym'),
    '{9A9A3EA0-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Symbol Information', 'sdb'),
    '{9A9A3EA1-D363-11d5-823E-0050DA6124B7}' : ('CoDeSys Boot Project', 'bop'),
    }

class SvnClient:
    def __init__(self, base = '.'):
        if not base.endswith('/'):
            base += '/'
        log.info('started svn client on wcbase "%s"' % base)
        self.wcbase = base
        self.svn = pysvn.Client()

    def ls(self, path):
        path = urlparse.urljoin(self.wcbase, path)
        log.info('svn ls %s' % path)
        entry_list = self.svn.ls(path)
        return [self._shortpath(i.name) for i in entry_list]

    def mkfile(self, object_path, object_type, content, comment):
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn mkfile: write %s' % wcpath)
        with open(wcpath, 'wb') as f:
            f.write(content)
        try:
            log.info('svn mkfile: add %s' % wcpath)
            self.svn.add(wcpath)
            log.info('svn mkfile: propset %s = %s' % ('eni:object-type', object_type))
            self.svn.propset('eni:object-type', object_type, wcpath)
        except Exception, e:
            log.warn(str(e))
        log.info('svn mkfile: checkin %s' % wcpath)
        self.svn.checkin([wcpath], comment)

    def mkdir(self, folder_path, comment):
        wcpath = self._wcpath(folder_path)
        log.info('svn mkdir %s' % wcpath)
        if os.path.exists(wcpath):
            return
        try:
            self.svn.mkdir(wcpath, comment, make_parents=True)
        except Exception, e:
            log.warn(str(e))
        self.svn.checkin([wcpath], comment)

    def cat(self, object_path, object_type, rev = None):
        self.update_wc()
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn cat: cat %s' % wcpath)
        return self.svn.cat(wcpath, self._rev(rev))

    def checkin(self, object_path, object_type, content, comment):
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn checkin: write %s' % wcpath)
        with open(wcpath, 'wb') as f:
            f.write(content)
        log.info('svn checkin: checkin %s' % wcpath)
        self.svn.checkin([wcpath], comment)
        self.unlock(object_path, object_type)

    def checkout(self, object_path, object_type, comment):
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn checkout: lock %s' % wcpath)
        self.lock(object_path, object_type, comment)
        log.info('svn mkfile: propset %s = %s' % ('eni:check-out-comment', comment))
        self.svn.propset('eni:object-type', object_type, wcpath)

    def lock(self, object_path, object_type, comment):
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn unlock: unlock %s' % wcpath)
        self.svn.lock(wcpath, comment) #, force=True)

    def unlock(self, object_path, object_type):
        wcpath = self._wcpath(object_path) + '.xml'
        log.info('svn unlock %s' % wcpath)
        self.svn.unlock(wcpath) #, force=True)

    def log(self, object_path, object_type = ''):
        self.update_wc()
        wcpath = self._wcpath(object_path) + '.xml'
        return self.svn.log(wcpath)

    def update_wc(self):
        log.info('svn update %s' % self.wcbase)
        self.svn.update(self.wcbase)

    def info(self, object_path, object_type = '', rev = None):
        self.update_wc()
        wcpath = self._wcpath(object_path) + '.xml'
        return self.svn.info2(wcpath, self._rev(rev))[0][1]

    def _rev(self, rev):
        if rev:
            return pysvn.Revision( pysvn.opt_revision_kind.number, int(rev))
        return pysvn.Revision( pysvn.opt_revision_kind.head)

    def _wcpath(self, object_path, object_type = None):
        ext = object_type_db.get(object_type)
        return os.path.join(self.wcbase, object_path) + ('.' + ext) if ext else ''

    def _shortpath(self, path):
        short_path = path[len(self.wcbase):]
        if short_path[0] == '/':
            short_path = short_path[1:]
        return short_path


#svn = SvnClient('https://svn.wind-direct.eu/wd30sw/wiplc/trunk/eni/')
svn = SvnClient('../eni/')


class EniAccess:
    def __init__(self, access):
        self.access = 0x0000;
        if isinstance(access, str):
            if 'r' in access:
                self.access |= 0x0100
            if 'w' in access:
                self.access |= 0x0200
            if 'd' in access:
                self.access |= 0x0400
        else:
            self.access = access;

    def __str__(self):
        return '0x%04x' % self.access


class EniHandshake:
    def __init__(self, req_etree):
        self.etree = req_etree
        self.username = self.etree.attrib['user-name']
        log.info('HANDSHAKE, username: %s' % self.username)

    def response(self):
        fingerprint1 = '00000000000000000000000000000000'
        fingerprint2 = '00000000000000000000000000000000'
        return '<handshake user-name="%s" fingerprint-1="%s" fingerprint-2="%s"/>' % (self.username, fingerprint1, fingerprint2)


class EniError:
    def __init__(self, eni_cmd, error_code, error_text = ''):
        self.eni_cmd = eni_cmd
        self.error_code = error_code
        self.error_text = error_text

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<error>\n'
        s += '<error-code>%s</error-code>\n' % self.error_code
        s += '<error-text>%s (%s)</error-text>\n' % (self.error_text, self.error_code)
        s += '</error>\n'
        s += '<data/>\n'
        s += '</response>'
        return s


class BaseEniCmd:
    def __init__(self, eni_cmd, req_etree):
        log.info('REQUEST command: %s' % (eni_cmd,))
        #log.info('REQUEST command: %s (user-name: %s)' % (eni_cmd, req_etree.attrib['user-name']))
        self.etree = req_etree
        self.eni_cmd = eni_cmd

    def do(self):
        return self._do()

    def _do(self):
        return None

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += self._response()
        s += '</response>'
        return s

    def _response(self):
        s = ''
        s += '<%s/>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_check_in_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.comment = a.find('comment').text if a.find('comment').text else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' comment: %s' % self.comment)

        d = self.etree.find('data')
        self.text = base64.b64decode(d.text) if d.text else ''
        log.debug(self.text)

    def _do(self):
        svn.checkin(self.object_path, self.object_type, self.text, self.comment)


class EniCmd_check_out_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.comment = a.find('comment').text if a.find('comment').text else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' comment: %s' % self.comment)

    def _do(self):
        svn.checkout(self.object_path, self.object_type, self.comment)


class EniCmd_create_folder(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text

        log.info(' folder-path: %s' % self.folder_path)

    def _do(self):
        svn.mkdir(self.folder_path, 'Initial check-in (commit)')


class EniCmd_create_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.no_history = a.find('no-history').text

        d = self.etree.find('data')
        self.text = base64.b64decode(d.text) if d.text else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' no-history: %s' % self.no_history)

        log.debug(self.text)

    def _do(self):
        svn.mkfile(self.object_path, self.object_type, self.text, 'Initial check-in (commit)')

class EniCmd_delete_folder(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text

        log.info(' folder-path: %s' % self.folder_path)


class EniCmd_delete_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)


class EniCmd_dir(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.root_path = a.find('root-path').text
        self.recursive = a.find('recursive').text
        self.folders_only = a.find('folders-only').text
        self.no_change_date = a.find('no-change-date').text

        log.info(' root-path: %s' % self.root_path)
        log.info(' recursive: %s' % self.recursive)
        log.info(' folders-only: %s' % self.folders_only)
        log.info(' no-change-date: %s' % self.no_change_date)

    def _do(self):
        try:
            self.dir_entries = svn.ls(self.root_path)
        except:
            return EniError(self.eni_cmd, 2054, 'path "%s" not found' % self.root_path)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        for e in self.dir_entries:
            s += '<object-info>\n'
            s += '<folder-path>%s</folder-path>\n' % e
            s += '<access>%s</access>\n' % EniAccess(0x0FFF)
            s += '</object-info>\n'
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_reset_version(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' label: %s' % self.label)
        log.info(' version: %s' % self.version)


class EniCmd_set_folder_label(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text
        self.label = a.find('label').text
        self.comment = a.find('comment').text if a.find('comment').text else ''

        log.info(' folder-path: %s' % self.folder_path)
        log.info(' label: %s' % self.label)
        log.info(' comment: %s' % self.comment)


class EniCmd_get_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.checksum = a.find('checksum').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' checksum: %s' % self.checksum)
        log.info(' label: %s' % self.label)
        log.info(' version: %s' % self.version)

    def _do(self):
        self.text = svn.cat(self.object_path, self.object_type, self.version)
        self.info = svn.info(self.object_path, self.object_type, self.version)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % format_date_time(self.info.last_changed_date)
        if self.info.lock:
            s += '<checked-out-by>%s</checked-out-by>\n' % self.info.lock.owner
            s += '<check-out-comment>%s</check-out-comment>\n' % self.info.lock.comment
        else:
            s += '<checked-out-by></checked-out-by>\n'
            s += '<check-out-comment></check-out-comment>\n'
        s += '<access>%s</access>\n' % EniAccess(0x0700)
        s += '</%s>\n' % self.eni_cmd
        s += '<data>%s</data>\n' % base64.b64encode(self.text)
        return s

class EniCmd_get_object_info(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)
        log.info(' label: %s' % self.label)
        log.info(' version: %s' % self.version)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % ''
        s += '<checked-out-by>%s</checked-out-by>\n' % ''
        s += '<check-out-comment>%s</check-out-comment>\n' % ''
        s += '<access>%s</access>\n' % EniAccess(0x0700)
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_object_type(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.guid = a.find('guid').text

        log.info(' guid: %s' % self.guid)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<guid>%s</guid>\n' % self.guid
        s += '<extension>%s</extension>\n' % object_type_db.get(self.guid, '')[1]
        s += '<description>%s</description>\n' % object_type_db.get(self.guid, '')[0]
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_object_type_list(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        for guid in object_type_db.keys():
            s += '<guid>%s</guid>\n' % guid
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_register_object_types(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)


class EniCmd_get_server_settings(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<comm-timeout>%s</comm-timeout>\n' % ''
        s += '<idle-interval>%s</idle-interval>\n' % ''
        s += '<allow-anonymous>%s</allow-anonymous>\n' % ''
        s += '<client-expiration>%s</client-expiration>\n' % ''
        s += '<max-trials>%s</max-trials>\n' % ''
        s += '<active-driver>%s</active-driver>\n' % ''
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_users(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        for user, info in user_db.items():
            s += '<user>\n'
            s += '<name>%s</name>\n' % user
            s += '<full-name>%s</full-name>\n' % info[0]
            s += '<description>%s</description>\n' % info[1]
            s += '<active>%s</active>\n' % 'true'
            s += '<logged-in>%s</logged-in>\n' % 'true'
            s += '</user>\n'
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_driver_info(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_object_history(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)

    def _do(self):
        self.versions = svn.log(self.object_path, self.object_type)
        self.info = svn.info(self.object_path, self.object_type)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<object-info>\n'
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % format_date_time(self.info.last_changed_date)
        if self.info.lock:
            s += '<checked-out-by>%s</checked-out-by>\n' % self.info.lock.owner
            s += '<check-out-comment>%s</check-out-comment>\n' % self.info.lock.comment
        else:
            s += '<checked-out-by></checked-out-by>\n'
            s += '<check-out-comment></check-out-comment>\n'
        s += '</object-info>\n'
        for v in self.versions:
            s += '<version>\n'
            s += '<version>%s</version>\n' % v.revision.number
            #s += '<label>%s</label>\n' % 'xxx'
            s += '<date>%s</date>\n' % format_date_time(v.date)
            s += '<comment>%s</comment>\n' % v.message
            s += '<action>%s</action>\n' % 'undefined'
            s += '<user-name>%s</user-name>\n' % v.author
            s += '<pinned>false</pinned>\n'
            s += '</version>\n'
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_get_folder_history(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.folder_path = a.find('folder-path').text

        log.info(' folder-path: %s' % self.folder_path)

    def _response(self):
        s = ''
        s += '<%s>\n' % self.eni_cmd
        s += '<object-info>\n'
        s += '<folder-path>%s</folder-path>\n' % self.folder_path
        s += '<access>%s</access>\n' % EniAccess(0x00FF)
        s += '</object-info>\n'
        s += '<version>\n'
        s += '<version>%s</version>\n' % '1.1'
        s += '<label>%s</label>\n' % 'xxx'
        s += '<date> Sun, 06 Nov 1994 08:49:37 GMT </date>\n'
        s += '<comment> Implementing the super feature </comment>\n'
        s += '<action>created</action>\n'
        s += '<user-name> Otto </user-name>\n'
        s += '<pinned> false </pinned>\n'
        s += '</version>\n'
        s += '<version>\n'
        s += '<version>%s</version>\n' % '1.2'
        s += '<label>%s</label>\n' % 'xxxx'
        s += '<date> Sun, 06 Nov 1994 09:49:37 GMT </date>\n'
        s += '<comment> Implementing the super feature </comment>\n'
        s += '<action>created</action>\n'
        s += '<user-name>testuser</user-name>\n'
        s += '<pinned> false </pinned>\n'
        s += '</version>\n'
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        return s


class EniCmd_undo_check_out_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        a = self.etree.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info(' object-path: %s' % self.object_path)
        log.info(' object-type: %s' % self.object_type)

    def _do(self):
        svn.unlock(self.object_path, self.object_type)


eni_commands = {
    'check-in-object' : EniCmd_check_in_object,
    'check-out-object' : EniCmd_check_out_object,
    'create-folder' : EniCmd_create_folder,
    'create-object' : EniCmd_create_object,
    'delete-folder' : EniCmd_delete_folder,
    'delete-object' : EniCmd_delete_object,
    'dir' : EniCmd_dir,
    'get-object' : EniCmd_get_object,
    'get-object-info' : EniCmd_get_object_info,
    'get-object-type' : EniCmd_get_object_type,
    'get-object-type-list' : EniCmd_get_object_type_list,
    'register-object-types' : EniCmd_register_object_types,
    'get-server-settings' : EniCmd_get_server_settings,
    'get-users' : EniCmd_get_users,
    'get-object-history' : EniCmd_get_object_history,
    'get-folder-history' : EniCmd_get_folder_history,
    'reset-version' : EniCmd_reset_version,
    'set-folder-label' : EniCmd_set_folder_label,
    'undo-check-out-object' : EniCmd_undo_check_out_object,
    'get-driver-info' : EniCmd_get_driver_info,
    'login' : BaseEniCmd,
    'logout' : BaseEniCmd,
    }


class EniHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        log.debug("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))

    protocol_version = 'HTTP/1.1'
    firsttime = True

    def do_POST(self):
        try:
            if EniHandler.firsttime:
                EniHandler.firsttime = False
                log.info('request_version: %s' % self.request_version)
                log.info('server_version: %s' % self.server_version)
                log.info('sys_version: %s' % self.sys_version)

            content_len = int(self.headers.getheader('content-length'))
            #log.debug('content-length: %s', content_len)
            content_rawxml = self.rfile.read(content_len)

            req_etree = ET.fromstring(content_rawxml)

            if req_etree.tag == 'handshake':
                req = EniHandshake(req_etree)

            elif req_etree.tag == 'request':
                eni_cmd_name = req_etree.attrib['command']

                log.debug('eni command: %s', eni_cmd_name)
                #log.debug('xml xmlroot attrib: %s', req_etree.attrib)
                log.debug('raw request: %s', content_rawxml)

                if eni_cmd_name in eni_commands:
                    EniCmd = eni_commands[eni_cmd_name]
                    req = EniCmd(eni_cmd_name, req_etree)
                    err = req.do()
                    if err:
                       req = err

                else:
                    req = EniError(eni_cmd_name, 16390, 'command "%s" not supported' % eni_cmd_name)
                    log.error('Unsupported request command: %s' % eni_cmd_name)
                    ET.dump(req_etree)

            else:
                log.error('Unsupported ENI request: %s (neither "handshake" nor "request")' % req_etree.tag)
                self.send_response(500)
                return

            rsp_content_xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            rsp_content_xml += req.response()

            self.send_response(200)
            self.send_header('content-length', len(rsp_content_xml))
            self.end_headers()
            self.wfile.write(rsp_content_xml)

            log.debug('=== OK ===')

        except Exception, e:
            log.error('EXCEPT %s' % str(e))
            self.send_response(500)
            raise e


def main():
    HOST, PORT = '', 80
    try:
        server = HTTPServer((HOST, PORT), EniHandler)
        log.info('started eni svn server (%s:%s)' % (HOST, PORT))
        server.serve_forever()
    except KeyboardInterrupt:
        log.warn('^C received, shutting down server')
    finally:
        server.socket.close()


if __name__ == '__main__':
    main()

