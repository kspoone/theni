#!/usr/bin/env python

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import xml.etree.ElementTree as ET
import base64
import pysvn
import logging as log
import os


log.basicConfig(level=log.INFO, format='%(levelname)s %(message)s')

WCBASE='../eni'
os.chdir(WCBASE)

client = pysvn.Client()
entry_list = client.ls('.')
print entry_list
print entry_list[0].name

#short_path = path[len((WCBASE):]
#if short_path[0] == '/':
#    short_path = short_path[1:]
#print short_path


FOO = """<?xml version="1.0" encoding="ISO-8859-1"?>

<pou>
        <path>\/=APP</path>
        <name>TASK_SLOW</name>
        <flags>2048</flags>
        <interface>
                <![CDATA[PROGRAM TASK_SLOW
VAR
END_VAR]]>
        </interface>
        <st>
                <body>
                        <![CDATA[(* Read from various process images ---------------------------------------- *)

PRG_UpdatePiiTaskS_In();
PRG_SplitToSubTypesS_In();
PRG_RotationalUpdate();

(* BEGIN: Actual code ------------------------------------------------------ *)

PRG_CabinetCooling();

(* END: Actual code -------------------------------------------------------- *)

(* Write to various process images ----------------------------------------- *)

PRG_SplitToSubTypesS_Out();
PRG_UpdatePiiTaskS_Out();
PRG_UpdateModbusTaskS_TX();
]]>
                </body>
        </st>
</pou>"""

class Handshake:
    def __init__(self, request_xml):
        self.root = request_xml
        self.username = self.root.attrib['user-name']
        log.info('HANDSHAKE, username: %s' % self.username)

    def response(self):
        s = '<handshake user-name="%s" fingerprint-1="00000000000000000000000000000000" fingerprint-2="00000000000000000000000000000000"/>' % self.username
        return s


class Request:
    def __init__(self, eni_cmd, request_xml):
        log.info('REQUEST command: %s (user-name: %s)' % (eni_cmd, self.root['user-name']))
        self.root = request_xml
        self.eni_cmd = eni_cmd

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s/>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_check_in_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.comment = a.find('comment').text

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)
        log.info('comment: %s' % self.comment)

        d = self.root.find('data')
        self.text = base64.b64decode(d.text) if d.text else ''
        log.debug(self.text)


class EniCmd_check_out_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.comment = a.find('comment').text

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)
        log.info('comment: %s' % self.comment)


class EniCmd_create_folder(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text

        log.info('folder-path: %s' % self.folder_path)


class EniCmd_create_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        log.info('object-path: %s' % a.find('object-path').text)
        log.info('object-type: %s' % a.find('object-type').text)
        log.info('no-history: %s' % a.find('no-history').text)

        d = self.root.find('data')
        self.text = base64.b64decode(d.text) if d.text else ''
        log.debug(self.text)


class EniCmd_delete_folder(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text

        log.info('folder-path: %s' % self.folder_path)


class EniCmd_delete_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)


class EniCmd_dir(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        self.root_path = a.find('root-path').text
        self.recursive = a.find('recursive').text
        self.folders_only = a.find('folders-only').text
        self.no_change_date = a.find('no-change-date').text

        log.info('object-path: %s' % self.root_path)
        log.info('recursive: %s' % self.recursive)
        log.info('folders-only: %s' % self.folders_only)
        log.info('no-change-date: %s' % self.no_change_date)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<object-info>\n'
        s += '<folder-path> Projects/New1 </folder-path>\n'
        s += '<access> 0x0FFF </access>\n'
        s += '</object-info>\n'
        s += '<object-info>\n'
        s += '<folder-path> New2 </folder-path>\n'
        s += '<access> 0x0FFF </access>\n'
        s += '</object-info>\n'
        s += '<%s/>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_reset_version(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)
        log.info('label: %s' % self.label)
        log.info('version: %s' % self.version)


class EniCmd_set_folder_label(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)
        self.folder_path = a.find('folder-path').text
        self.label = a.find('label').text
        self.comment = a.find('comment').text

        log.info('folder-path: %s' % self.folder_path)
        log.info('label: %s' % self.label)
        log.info('comment: %s' % self.comment)


class EniCmd_get_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.checksum = a.find('checksum').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)
        log.info('checksum: %s' % self.checksum)
        log.info('label: %s' % self.label)
        log.info('version: %s' % self.version)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % 'Sun, 06 Nov 1994 08:49:37 GMT'
        s += '<checked-out-by>%s</checked-out-by>\n' % 'testuser'
        s += '<check-out-comment>%s</check-out-comment>\n' % ''
        s += '<access>%s</access>\n' % 0x0700
        s += '</%s>\n' % self.eni_cmd
        s += '<data>%s</data>\n' % base64.b64encode(FOO)
        s += '</response>'
        return s

class EniCmd_get_object_info(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text
        self.label = a.find('label').text if a.find('label') is not None else ''
        self.version = a.find('version').text if a.find('version') is not None else ''

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)
        log.info('label: %s' % self.label)
        log.info('version: %s' % self.version)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date>%s</change-date>\n' % ''
        s += '<checked-out-by>%s</checked-out-by>\n' % ''
        s += '<check-out-comment>%s</check-out-comment>\n' % ''
        s += '<access>%s</access>\n' % 0x0700
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_get_object_type(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.guid = a.find('guid').text

        log.info('guid: %s' % self.guid)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<guid>%s</guid>\n' % self.guid
        s += '<extension>%s</extension>\n' % ''
        s += '<description>%s</description>\n' % ''
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_get_object_type_list(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.guid = a.find('guid').text

        log.info('guid: %s' % self.guid)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<guid>%s</guid>\n' % self.guid
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_get_server_settings(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<comm-timeout>%s</comm-timeout>\n' % ''
        s += '<idle-interval>%s</idle-interval>\n' % ''
        s += '<allow-anonymous>%s</allow-anonymous>\n' % ''
        s += '<client-expiration>%s</client-expiration>\n' % ''
        s += '<max-trials>%s</max-trials>\n' % ''
        s += '<active-driver>%s</active-driver>\n' % ''
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_get_users(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<user>\n'
        s += '<name>%s</name>\n' % 'testuser'
        s += '<full-name>%s</full-name>\n' % 'Test User'
        s += '<description>%s</description>\n' % '...'
        s += '<active>%s</active>\n' % 'true'
        s += '<logged-in>%s</logged-in>\n' % 'true'
        s += '</user>\n'
        s += '</%s>\n' % self.eni_cmd
        s += '<data/>\n'
        s += '</response>'
        return s


class EniCmd_get_object_history(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<object-info>\n'
        s += '<object-path>%s</object-path>\n' % self.object_path
        s += '<object-type>%s</object-type>\n' % self.object_type
        s += '<change-date> Sun, 06 Nov 1994 08:49:37 GMT </change-date>\n'
        s += '<checked-out-by> Otto </checked-out-by>\n'
        s += '<check-out-comment> Implementing the super feature </check-out-comment>\n'
        s += '<access> 0x00FF </access>\n'
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
        s += '</response>'
        return s


class EniCmd_get_folder_history(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.folder_path = a.find('folder-path').text

        log.info('folder-path: %s' % self.folder_path)

    def response(self):
        s = '<response command="%s">\n' % self.eni_cmd
        s += '<success/>\n'
        s += '<%s>\n' % self.eni_cmd
        s += '<object-info>\n'
        s += '<folder-path>%s</folder-path>\n' % self.folder_path
        s += '<access> 0x00FF </access>\n'
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
        s += '</response>'
        return s


class EniCmd_undo_check_out_object(Request):
    def __init__(self, eni_cmd, request_xml):
        Request.__init__(self, eni_cmd, request_xml)

        a = self.root.find(self.eni_cmd)

        self.object_path = a.find('object-path').text
        self.object_type = a.find('object-type').text

        log.info('object-path: %s' % self.object_path)
        log.info('object-type: %s' % self.object_type)


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
    'get-server-settings' : EniCmd_get_server_settings,
    'get-users' : EniCmd_get_users,
    'get-object-history' : EniCmd_get_object_history,
    'get-folder-history' : EniCmd_get_folder_history,
    'reset-version' : EniCmd_reset_version,
    'set-folder-label' : EniCmd_set_folder_label,
    'undo-check-out-object' : EniCmd_undo_check_out_object,
    'login' : Request,
    'logout' : Request,
    }


class EniHandler(BaseHTTPRequestHandler):
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

            xmlroot = ET.fromstring(content_rawxml)

            req = None

            if xmlroot.tag == 'handshake':
                req = Handshake(xmlroot)

            elif xmlroot.tag == 'request':
                eni_cmd = xmlroot.attrib['command']

                log.debug('xml xmlroot tag: %s', xmlroot.tag)
                log.debug('eni command: %s', eni_cmd)
                #log.debug('xml xmlroot attrib: %s', xmlroot.attrib)
                log.debug('raw request: %s', content_rawxml)

                if eni_cmd in eni_commands:
                    req = eni_commands[eni_cmd](eni_cmd, xmlroot)
                else:
                    log.error('Unsupported request command: %s' % eni_cmd)
                    ET.dump(xmlroot)

            else:
                log.error('Unsupported: %s' % xmlroot.tag)

            rsp_content_xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            if req:
                rsp_content_xml += req.response()

            self.send_response(200)
            self.send_header('content-length', len(rsp_content_xml))
            self.end_headers()
            self.wfile.write(rsp_content_xml)

            log.debug('=== OK ===')

        except Exception, e:
            log.error('EXCEPT %s' % str(e))
            self.send_response(500)
            #self.end_headers()

    def log_message(self, format, *args):
        log.debug("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))

def main():
    HOST, PORT = '', 80
    try:
        server = HTTPServer((HOST, PORT), EniHandler)
        log.info('started ENI SVN server (%s:%s) ...' % (HOST, PORT))
        server.serve_forever()
    except KeyboardInterrupt:
        log.warn('^C received, shutting down server')
    finally:
        server.socket.close()

if __name__ == '__main__':
    main()

