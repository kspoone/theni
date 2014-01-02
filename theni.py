#!/usr/bin/env python

import base64
import getpass
import logging as log
import os
import pysvn
import time
import urlparse
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from wsgiref.handlers import format_date_time
from xml.etree import ElementTree as ET
from mhlib import Folder


log.basicConfig(level=log.INFO, format='%(levelname)s %(message)s')


class SvnDB:
    def __init__(self, base = '.'):
        if not base.endswith('/'):
            base += '/'
        self.wcbase = base
        self.svn = pysvn.Client()

        self.object_type_db1 = {}
        self.object_type_db2 = {}
        info = self.info('')

        log.info('started vcs client on wcbase "%s"', base)
        log.info(' user: "%s"', getpass.getuser())
        log.info(' url: "%s"', info.URL)

        thenisvn_conf = os.path.join(self.wcbase, 'enisvndb.conf')
        if not os.path.exists(thenisvn_conf):
            raise Exception('Not a proper ENI/SVN working capy.')

        log.info('reading enisvn db config from "%s"', thenisvn_conf)
        self.users = {}
        for line in open(thenisvn_conf):
            line = line.split('#')[0].strip()
            if not line: continue
            k, v = line.split('=')
            if k == 'user':
                user, info = v.split(',')
                log.info(' added user %s, %s', user, info)
                self.users[user] = info

    def ls(self, path, recursive, folders_only):
        path = urlparse.urljoin(self.wcbase, path)
        log.info('vcs ls %s', path)
        entry_list = self.svn.ls(path.strip(), recurse=recursive)
        if folders_only:
            entry_list = filter(lambda e: e.kind == pysvn.node_kind.dir, entry_list)
        return map(lambda e: (self._shortpath(e.name), e.kind), entry_list)

    def mkfile(self, object_path, object_type, content, comment):
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs mkfile: write %s', wcpath)
        with open(wcpath, 'wb') as f:
            f.write(content)
        try:
            log.info('vcs mkfile: add %s', wcpath)
            self.svn.add(wcpath)
            log.info('vcs mkfile: propset %s = %s', 'eni:object-type', object_type)
            self.svn.propset('eni:object-type', object_type, wcpath)
        except Exception, e:
            log.warn(str(e))
        log.info('vcs mkfile: checkin %s', wcpath)
        self.svn.checkin([wcpath], comment)

    def mkdir(self, folder_path, comment):
        wcpath = self._wcpath(folder_path)
        log.info('vcs mkdir %s', wcpath)
        if os.path.exists(wcpath):
            return
        try:
            self.svn.mkdir(wcpath, comment, make_parents=True)
        except Exception, e:
            log.warn(str(e))
        self.svn.checkin([wcpath], comment)

    def cat(self, object_path, object_type, rev = None):
        self.update_wc()
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs cat %s', wcpath)
        return self.svn.cat(wcpath, self._rev(rev))

    def checkin(self, object_path, object_type, content, comment):
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs checkin: write %s', wcpath)
        with open(wcpath, 'wb') as f:
            f.write(content)
        log.info('vcs checkin: checkin %s', wcpath)
        self.svn.checkin([wcpath], comment)
        self.unlock(object_path, object_type)

    def checkout(self, object_path, object_type, comment):
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs checkout: lock %s', wcpath)
        self.lock(object_path, object_type, comment)
        log.info('vcs mkfile: propset %s = %s', 'eni:check-out-comment', comment)
        self.svn.propset('eni:object-type', object_type, wcpath)

    def lock(self, object_path, object_type, comment):
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs lock: lock %s', wcpath)
        self.svn.lock(wcpath, comment) #, force=True)

    def unlock(self, object_path, object_type):
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs unlock %s', wcpath)
        self.svn.unlock(wcpath) #, force=True)

    def set_rev_prop(self, folder_path, label):
        url = self.get_url()
        log.info('vcs propset --revprop %s', url)
        rev = self.svn.revpropset(
                'eni:label', label,
                url,
                revision = pysvn.Revision(pysvn.opt_revision_kind.head),
                )
        return rev.number

    def log(self, object_path, object_type = None):
        self.update_wc()
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs log %s', wcpath)
        return self.svn.log(wcpath, revprops=['vcs:author', 'vcs:date', 'vcs:log', 'eni:label',])
        return self.svn.log(wcpath)

    def info(self, object_path, object_type = None, rev = None):
        self.update_wc()
        wcpath = self._wcpath(object_path, object_type)
        log.info('vcs info %s', wcpath)
        return self.svn.info2(wcpath, self._rev(rev))[0][1]

    def update_wc(self):
        log.info('vcs update %s', self.wcbase)
        self.svn.update(self.wcbase)

    def add_object_type_info(self, guid, ext, desc):
        log.info('add object type: %s .%-3s "%s"', guid, ext, desc)
        self.object_type_db1[guid] = (desc, ext)
        self.object_type_db2[ext] = guid

    def get_object_type_info(self, object_type):
        return self.object_type_db1.get(object_type, ('', ''))

    def get_object_type(self, ext):
        return self.object_type_db2.get(ext, '')

    def get_object_types(self):
        return self.object_type_db1.keys()

    def _rev(self, rev):
        if rev:
            return pysvn.Revision( pysvn.opt_revision_kind.number, int(rev))
        return pysvn.Revision( pysvn.opt_revision_kind.head)

    def _wcpath(self, object_path, object_type = None):
        ext = self._get_object_ext(object_type)
        return os.path.join(self.wcbase, object_path) + ext

    def get_url(self):
        return self.info(self.wcbase).URL

    def _get_object_ext(self, object_type):
        desc, ext = self.get_object_type_info(object_type)
        return '.%s' % ext if ext else ''

    def _shortpath(self, path):
        short_path = path[len(self.wcbase):]
        if short_path[0] == '/':
            short_path = short_path[1:]
        return short_path


vcs = SvnDB('../eni/')

object_types = (
        ('{9A9A3E90-D363-11d5-823E-0050DA6124B7}', 'pou', 'CoDeSys POU'),
        ('{9A9A3E91-D363-11d5-823E-0050DA6124B7}', 'dut', 'CoDeSys Data Unit Type'),
        ('{9A9A3E92-D363-11d5-823E-0050DA6124B7}', 'gvl', 'CoDeSys Global Variable List'),
        ('{9A9A3E93-D363-11d5-823E-0050DA6124B7}', 'vis', 'CoDeSys Visualization'),
        ('{9A9A3E94-D363-11d5-823E-0050DA6124B7}', 'cnc', 'CoDeSys CNC List'),
        ('{9A9A3E95-D363-11d5-823E-0050DA6124B7}', 'lim', 'CoDeSys Library Manager'),
        ('{9A9A3E96-D363-11d5-823E-0050DA6124B7}', 'trs', 'CoDeSys Target Settings'),
        ('{9A9A3E97-D363-11d5-823E-0050DA6124B7}', 'tio', 'CoDeSys Tool Instance'),
        ('{9A9A3E98-D363-11d5-823E-0050DA6124B7}', 'tmo', 'CoDeSys Tool Manager'),
        ('{9A9A3E99-D363-11d5-823E-0050DA6124B7}', 'od', 'CoDeSys Object Dictionary'),
        ('{9A9A3E9A-D363-11d5-823E-0050DA6124B7}', 'pcf', 'CoDeSys PLC Configuration'),
        ('{9A9A3E9B-D363-11d5-823E-0050DA6124B7}', 'pin', 'CoDeSys Project Information'),
        ('{9A9A3E9C-D363-11d5-823E-0050DA6124B7}', 'tco', 'CoDeSys Task Configuration'),
        ('{9A9A3E9D-D363-11d5-823E-0050DA6124B7}', 'tce', 'CoDeSys Trace'),
        ('{9A9A3E9E-D363-11d5-823E-0050DA6124B7}', 'wen', 'CoDeSys Watch Manager'),
        ('{9A9A3E9F-D363-11d5-823E-0050DA6124B7}', 'sym', 'CoDeSys Symbol Information'),
        ('{9A9A3EA0-D363-11d5-823E-0050DA6124B7}', 'sdb', 'CoDeSys Symbol Information'),
        ('{9A9A3EA1-D363-11d5-823E-0050DA6124B7}', 'bop', 'CoDeSys Boot Project'),
        ('{9A9A3EA2-D363-11d5-823E-0050DA6124B7}', 'acf', 'CoDeSys Alarm Configuration'),
        ('{9A9A3EA3-D363-11d5-823E-0050DA6124B7}', 'cam', 'CoDeSys CAM list'),
        )

for object_type in object_types:
    vcs.add_object_type_info(*object_type)


#for i in vcs.log(''):
#    try:
#        print '%s eni:label %s' % (i.revision, i.revprops['eni:label'])
#    except:
#        pass
#vcs.set_rev_prop('', 'label')

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
        return '0x%04X' % self.access


class EniHandshake:
    def __init__(self, req_etree):
        self.__etree = req_etree
        self.__username = self.__etree.attrib['user-name']
        log.debug('ENI handshake request, username: %s', self.__username)

    def response(self):
        fingerprint1 = '0' * 32
        fingerprint2 = '0' * 32
        return '<handshake user-name="%s" fingerprint-1="%s" fingerprint-2="%s"/>' % (
                self.__username, fingerprint1, fingerprint2
                )


class EniError:
    def __init__(self, eni_cmd, error_code, error_text = ''):
        log.debug('EniError %s %s %s', eni_cmd, error_code, error_text)
        self.__eni_cmd = eni_cmd
        self.__error_code = error_code
        self.__error_text = error_text

    def response(self):
        s = '<response command="%s">\n' % self.__eni_cmd
        s += '<error>\n'
        s += '<error-code>%s</error-code>\n' % self.__error_code
        s += '<error-text>%s (%s)</error-text>\n' % (self.__error_text, self.__error_code)
        s += '</error>\n'
        s += '<data/>\n'
        s += '</response>'
        return s


class BaseEniCmd:
    def __init__(self, eni_cmd, req_etree):
        log.info('ENI service request, command: %s', eni_cmd.upper())
        #log.info('REQUEST command: %s (user-name: %s)' % (__eni_cmd, req_etree.attrib['user-name']))
        self.__eni_cmd = eni_cmd
        self.__etree = req_etree

        self.__eni_cmd_elem = self.__etree.find(self.__eni_cmd)
        d = self.__etree.find('data')
        self.text = base64.b64decode(d.text.strip()) if d is not None else ''

    def get(self, elem, default = ''):
        s = self.__eni_cmd_elem.find(elem)
        return s.text.strip() if s is not None else default

    def get_bool(self, elem, default = 'false'):
        return self.get(elem, default).lower == 'true'

    def do(self):
        try:
            self._do()
        except pysvn.ClientError, e:
            raise EniError(self.__eni_cmd, 0xffff, 'vcs client error: %s' % str(e))

    def _do(self):
        pass

    def response(self):
        s = '<response command="%s">\n' % self.__eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.__eni_cmd
        r = self._response()
        if isinstance(r, str):
            s += r
        elif isinstance(r, dict):
            for k, v in r.items:
                s += '<{0}>{1}<\{0}>\n'.format(k, v)
        else:
            pass
        s += '</%s>\n' % self.__eni_cmd
        s += self._data()
        s += '</response>'
        print s
        return s

    def _response(self):
        return None
        s = ''
        #s += '<%s/>\n' % self.__eni_cmd
        return s

    def _data(self):
        return '<data/>\n'


class EniCmd_login(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)
        log.info(' user-name: %s', req_etree.attrib['user-name'])

    def _do(self):
        vcs.update_wc()


class EniCmd_logout(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)


class EniCmd_check_in_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.comment = self.get('comment')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' comment: %s', self.comment)

        log.debug(self.text)

    def _do(self):
        vcs.checkin(self.object_path, self.object_type, self.text, self.comment)


class EniCmd_check_out_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.comment = self.get('comment')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' comment: %s', self.comment)

    def _do(self):
        vcs.checkout(self.object_path, self.object_type, self.comment)


class EniCmd_create_folder(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.folder_path = self.get('folder-path')

        log.info(' folder-path: %s', self.folder_path)

    def _do(self):
        vcs.mkdir(self.folder_path, 'Initial check-in (commit)')


class EniCmd_create_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.no_history = self.get_bool('no-history')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' no-history: %s', self.no_history)

        log.debug(self.text)

    def _do(self):
        vcs.mkfile(self.object_path, self.object_type, self.text, 'Initial check-in (commit)')


class EniCmd_delete_folder(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.folder_path = self.get('folder-path')

        log.info(' folder-path: %s', self.folder_path)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_delete_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_move_folder(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.source_path = self.get('source-path')
        self.dest_path = self.get('dest-path')

        log.info(' source-path: %s', self.source_path)
        log.info(' dest-path: %s', self.dest_path)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_move_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.source_path = self.get('source-path')
        self.source_type = self.get('source-type')
        self.dest_path = self.get('dest-path')
        self.dest_type = self.get('dest-type')

        log.info(' source-path: %s', self.source_path)
        log.info(' source-type: %s', self.source_type)
        log.info(' dest-path: %s', self.dest_path)
        log.info(' dest-type: %s', self.dest_type)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_dir(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.root_path = self.get('root-path')
        self.recursive = self.get_bool('recursive')
        self.folders_only = self.get_bool('folders-only')
        self.no_change_date = self.get_bool('no-change-date')

        log.info(' root-path: %s', self.root_path)
        log.info(' recursive: %s', self.recursive)
        log.info(' folders-only: %s', self.folders_only)
        log.info(' no-change-date: %s', self.no_change_date)

    def _do(self):
        try:
            self.dir_entries = vcs.ls(self.root_path, self.recursive, self.folders_only)
        except Exception, e:
            raise EniError(self.__eni_cmd, 2054, 'path "%s" not found', self.root_path)

    def _response(self):
        s = ''
        for p, t in self.dir_entries:
            s += '<object-info>\n'
            if t == pysvn.node_kind.dir:
                s += '<folder-path>%s</folder-path>\n' % p
                s += '<access>%s</access>\n' % EniAccess(0x0FFF)
            elif t == pysvn.node_kind.file:
                n, e = os.path.splitext(p)
                e = e[1:] if e.startswith('.') else e
                guid = vcs.get_object_type(e)
                s += '<object-path>%s</object-path>\n' % n
                s += '<object-type>%s</object-type>\n' % guid
                s += '<access>%s</access>\n' % EniAccess(0x00FF)
                #s += '<change-date>%s</change-date>\n' % format_date_time(self.info.last_changed_date)
                #if self.info.lock:
                #    s += '<checked-out-by>%s</checked-out-by>\n' % self.info.lock.owner
                #    s += '<check-out-comment>%s</check-out-comment>\n' % self.info.lock.comment
            else:
                log.error('node kind none or unknown')
            s += '</object-info>\n'

        return s


class EniCmd_reset_version(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.label = self.get('label')
        self.version = self.get('version')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' label: %s', self.label)
        log.info(' version: %s', self.version)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_set_folder_label(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.folder_path = self.get('folder-path')
        self.label = self.get('label')
        self.comment = self.get('comment')

        log.info(' folder-path: %s', self.folder_path)
        log.info(' label: %s', self.label)
        log.info(' comment: %s', self.comment)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)
        vcs.set_rev_prop(self.folder_path, self.label)


class EniCmd_get_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.checksum = self.get('checksum')
        self.label = self.get('label')
        self.version = self.get('version')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' checksum: %s', self.checksum)
        log.info(' label: %s', self.label)
        log.info(' version: %s', self.version)

    def _do(self):
        self.text = vcs.cat(self.object_path, self.object_type, self.version)
        self.info = vcs.info(self.object_path, self.object_type, self.version)

    def _response(self):
        s = ''
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
        return s

    def _data(self):
        return '<data>%s</data>\n' % base64.b64encode(self.text)


class EniCmd_get_object_info(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')
        self.label = self.get('label')
        self.version = self.get('version')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)
        log.info(' label: %s', self.label)
        log.info(' version: %s', self.version)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)

    # XXX
    def _response(self):
        s = ''
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % ''
        s += '<checked-out-by>%s</checked-out-by>\n' % ''
        s += '<check-out-comment>%s</check-out-comment>\n' % ''
        s += '<access>%s</access>\n' % EniAccess(0x0700)
        return s


class EniCmd_get_object_type(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.guid = self.get('guid')

        log.info(' guid: %s', self.guid)

    def _response(self):
        desc, ext = vcs.get_object_type_info(self.guid)
        d = {
            'guid' : self.guid,
            'extension' : ext,
            'description' : desc,
            }
        return d


class EniCmd_get_object_type_list(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        d = {}
        for guid in vcs.get_object_types():
            d['guid'] = guid
        return d


class EniCmd_register_object_types(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_get_server_settings(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        return {
                'comm-timeout' : 10,
                'idle-interval' : 60,
                'allow-anonymous' : 'false',
                'client-expiration' : 10,
                'max-trials' : 10,
                'active-driver' : 'theni:svn',
                }


class EniCmd_get_users(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _response(self):
        s = ''
        for user, info in vcs.users.items():
            s += '<user>\n'
            s += '<name>%s</name>\n' % user
            s += '<full-name>%s</full-name>\n' % info
            s += '<description>%s</description>\n' % '...'
            s += '<active>%s</active>\n' % True
            s += '<logged-in>%s</logged-in>\n' % True
            s += '</user>\n'
        return s


class EniCmd_get_driver_info(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

    def _do(self):
        log.warn('half-implemented cmd: %s', self.__eni_cmd)


class EniCmd_get_object_history(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)

    def _do(self):
        self.versions = vcs.log(self.object_path, self.object_type)
        self.info = vcs.info(self.object_path, self.object_type)

    def _response(self):
        s = ''
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
            try:
                s += '<label>%s</label>\n' % v.revprops['eni:label']
            except KeyError:
                pass
            s += '<date>%s</date>\n' % format_date_time(v.date)
            s += '<comment>%s</comment>\n' % v.message
            s += '<action>%s</action>\n' % 'undefined'
            s += '<user-name>%s</user-name>\n' % v.author
            s += '<pinned>false</pinned>\n'
            s += '</version>\n'
        return s


class EniCmd_get_folder_history(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.folder_path = self.get('folder-path')

        log.info(' folder-path: %s', self.folder_path)

    def _do(self):
        self.versions = vcs.log(self.folder_path)
        self.info = vcs.info(self.folder_path)

    def _response(self):
        #time.sleep(10)
        s = ''
        s += '<folder-version>\n'
        s += '</folder-version>\n'
        if False:
            s += '<object-info>\n'
            s += '<folder-path>%s</folder-path>\n' % self.folder_path
            s += '<object-path>%s</object-path>\n' % '{9A9A3E90-D363-11d5-823E-0050DA6124B7}'
            s += '<access>%s</access>\n' % EniAccess(0x00FF)
            s += '<change-date>%s</change-date>\n' % format_date_time(self.info.last_changed_date)
            s += '<checked-out-by></checked-out-by>\n'
            s += '<check-out-comment></check-out-comment>\n'
            s += '</object-info>\n'
            for v in self.versions[:3]:
                s += '<version>\n'
                s += '<object-path>%s</object-path>\n' % self.folder_path
                s += '<object-type>%s</object-type>\n' % self.folder_path
                s += '<version>%s</version>\n' % v.revision.number
                s += '<label>%s</label>\n' % 'xxx'
                s += '<date>%s</date>\n' % format_date_time(v.date)
                s += '<comment>%s</comment>\n' % v.message
                s += '<action>%s</action>\n' % 'undefined'
                s += '<user-name>%s</user-name>\n' % v.author
                s += '<pinned>false</pinned>\n'
                s += '</version>\n'
        return s


class EniCmd_get_permissions(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)

    def _response(self):
        return {
                'GetObject' : 1,
                'GetObjectInfo' : 1,
                'GetObjectHistory' : 1,
                'GetFolderHistory' : 1,
                'CheckOutObject' : 1,
                'CheckInObject' : 1,
                'CheckInObjectEx' : 1,
                'DeleteObject' : 1,
                'MoveObject' : 1,
                'SetVersionComment' : 1,
                'ResetVersion' : 1,
                'Dir' : 1,
                'DirRecursive' : 1,
                'DeleteFolder' : 1,
                'CreateFolder' : 1,
                'CreateObject' : 1,
                'MoveFolder' : 1,
                'SetFolderLabel' : 1,
                'UndoCheckOutObject' : 1,
                }


class EniCmd_undo_check_out_object(BaseEniCmd):
    def __init__(self, eni_cmd, req_etree):
        BaseEniCmd.__init__(self, eni_cmd, req_etree)

        self.object_path = self.get('object-path')
        self.object_type = self.get('object-type')

        log.info(' object-path: %s', self.object_path)
        log.info(' object-type: %s', self.object_type)

    def _do(self):
        vcs.unlock(self.object_path, self.object_type)


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
                log.debug('request_version: %s', self.request_version)
                log.debug('server_version: %s', self.server_version)
                log.debug('sys_version: %s', self.sys_version)

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

                try:
                    clazz = globals()['EniCmd_%s' % eni_cmd_name.replace('-', '_')]
                    req = clazz(eni_cmd_name, req_etree)
                    err = req.do()
                    if err:
                       req = err

                except KeyError:
                    req = EniError(eni_cmd_name, 16390, 'command "%s" not supported' % eni_cmd_name)
                    log.error('Unsupported request command: %s', eni_cmd_name)
                    ET.dump(req_etree)

                except EniError, e:
                    req = e

                #except Exception, e:
                #    req = EniError(eni_cmd_name, 2048, 'Unknown error')
                #    print e

            else:
                log.error('Unsupported ENI request: %s (neither "handshake" nor "request")', req_etree.tag)
                self.send_response(500)
                return

            rsp_content_xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            rsp_content_xml += req.response().encode('ISO-8859-1')

            self.send_response(200)
            self.send_header('content-length', len(rsp_content_xml))
            self.end_headers()
            self.wfile.write(rsp_content_xml)

            log.debug('=== OK ===')

        except Exception, e:
            log.error('EXCEPT %s', str(e))
            self.send_response(500)
            raise


def main():
    HOST, PORT = 'localhost', 80
    try:
        server = HTTPServer((HOST, PORT), EniHandler)
        log.info('started eni vcs server on %s, port %s', HOST, PORT)
        server.serve_forever()
    except KeyboardInterrupt:
        log.warn('^C received, shutting down server')
    finally:
        server.socket.close()


if __name__ == '__main__':
    main()

