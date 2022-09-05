# -*- coding: utf-8 -*-

import os
import datetime
import time
import shutil
import json
import tempfile
import stat
from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, AccessDenied,UserError, ValidationError


import logging
_logger = logging.getLogger(__name__)

import base64
from io import BytesIO
from odoo import api, fields, models


try:
    import paramiko
except ImportError:
    raise ImportError(
        'This module needs paramiko to automatically write new conf for logstash  to the FTP through SFTP. '
        'Please install paramiko on your system. (sudo pip3 install paramiko)')


class JdbcPostgresqlImport(models.TransientModel):
    """ Import Module """
    _name = "jdbc.postgresql.import"
    _description = "Import jdbc.postgresql"

    module_file = fields.Binary(string='postgresql-xx-x-xx.jar', required=True)
    url = fields.Char('jdbc.postgresql download',default="https://jdbc.postgresql.org/download.html", readonly="1")
    state = fields.Selection([('init', 'init'), ('done', 'done')], string='Status', readonly=True, default='init')
    path = fields.Char('folder for jdbc')
    filename = fields.Char()

    def import_module(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id', False)
        elastic_server = self.env['elasticsearch.server'].browse(active_id)
        s = elastic_server.sftp_connection()
        sftp = s.open_sftp()
        zip_data = base64.decodestring(self.module_file)
        fp = open('/tmp/' + self.filename, 'wb')
        #fp = BytesIO()
        fp.write(zip_data)
        fp.close()

        try:
            sftp.chdir(self.path.strip())
        except IOError as e:
            # Create directory and subdirs if they do not exist.
            elastic_server.is_defined_sftp_jdbc_path = False
            current_directory = ''
            for dirElement in self.path.strip().split('/'):
                current_directory += dirElement + '/'
                try:
                    sftp.chdir(current_directory)
                except:
                    try:
                        _logger.info(
                            '(Part of the) path didn\'t exist. Creating it now at ' + current_directory)
                        # Make directory and then navigate into it
                        sftp.mkdir(current_directory, 0o777)
                        sftp.chdir(current_directory)
                        pass
                    except Exception as e:
                        _logger.critical('There was a problem to create folder' + str(e))
                        raise ValidationError(
                            _('folder for jdbc class is not defined ,we cannot create new folder %s') % (str(e)))

        try:
            sftp.put('/tmp/' + self.filename, os.path.join(self.path.strip(), self.filename))
            sftp.chmod(os.path.join(self.path.strip(), self.filename),0o777)
            elastic_server.sftp_jdbc_driver_library_path = os.path.join(self.path.strip(), self.filename)
            elastic_server.is_defined_sftp_jdbc_path = False
            sftp.close()
        except Exception as e:
            raise ValidationError(_(
                'jdbc driver is not defined !!, you can download from the jdbc.postgresql.org and upload in your remote server , use the upload button  %s') % (
                                      str(e)))


