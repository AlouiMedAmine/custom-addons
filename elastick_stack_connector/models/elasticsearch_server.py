# -*- coding: utf-8 -*-

import os
import datetime
import time
import shutil
import json
import tempfile
import stat
from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, AccessDenied, UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:
    raise ImportError(
        'This module needs paramiko to automatically write new conf for logstash  to the FTP through SFTP. '
        'Please install paramiko on your system. (sudo pip3 install paramiko)')


class ElasticSearchServer(models.Model):
    _name = 'elasticsearch.server'
    _inherit = ["mail.thread"]
    _description = 'ElasticSearch Server'
    _order = 'sequence,id'

    def _get_default_require_elasticserver_help(self):
        return self.env.company.elasticserver_setting_help

    name = fields.Char('Name',copy=False,)
    state = fields.Selection([
        ('draft', 'Not Confirmed'),
        ('confirm', 'Confirmed'),
    ], string='Status', tracking=True, index=True, readonly=True, copy=False, default='draft')
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer()
    is_success = fields.Boolean('Is Success', default=False)
    sftp_host = fields.Char('IP Address SFTP Server',
                            help='The IP address from your remote server. For example 192.168.0.1',states={'confirm': [('readonly', True)]},tracking=True)
    sftp_port = fields.Integer('SFTP Port', help='The port on the FTP server that accepts SSH/SFTP calls.', default=22,states={'confirm': [('readonly', True)]})
    sftp_user = fields.Char('SFTP Username',states={'confirm': [('readonly', True)]},
                            help='The username where the SFTP connection should be made with. This is the user on the '
                                 'external server.',tracking=True)
    sftp_password = fields.Char('Password User',states={'confirm': [('readonly', True)]},
                                help='The password from the user where the SFTP connection should be made with. This '
                                     'is the password from the user on the external server.',tracking=True)

    sftp_jdbc_driver_library_path = fields.Char(string='jdbc driver file',states={'confirm': [('readonly', True)]},tracking=True)
    is_defined_sftp_jdbc_path = fields.Boolean('Defined jdbc driver', default=False)

    sftp_last_run_metadata_path = fields.Char(string='Last run metadata folder',states={'confirm': [('readonly', True)]},tracking=True)
    is_defined_last_run = fields.Boolean('Defined last_run', default=False)

    sftp_logstash_bin_path = fields.Char(string='Binary scripts path folder', default='/usr/share/logstash/bin',states={'confirm': [('readonly', True)]},tracking=True)
    is_sftp_logstash_bin_path = fields.Boolean('Defined Logstash bin path', default=False)

    sftp_logstash_log_path = fields.Char(string='Log file', default='/var/log/logstash/logstash-plain.log',help="update permession , sudo chmod 777"
                                         ,states={'confirm': [('readonly', True)]}, tracking=True)
    is_sftp_logstash_log_path = fields.Boolean('Defined Logstash log path', default=False)

    sftp_path = fields.Char('Path configuration folder',default='/etc/logstash/conf.d',states={'confirm': [('readonly', True)]},tracking=True,  help='The location to the folder where the file.conf should be written to. For example '
                                 '/etc/logstash/conf.d/.\nFiles will then be written to /etc/logstash/conf.d/ on your remote server.')
    is_sftp_path = fields.Boolean('Defined last_run', default=False)

    is_installed = fields.Boolean('Is logstash installed', default=False)

    elastic_login = fields.Char(string='Elastic User',states={'confirm': [('readonly', True)]})
    elastic_password = fields.Char(string='Elastic Password',states={'confirm': [('readonly', True)]})
    elastic_url = fields.Char(string='try to connect on elastic',help='http://localhost:9200/' ,states={'confirm': [('readonly', True)]} )
    kibana_url = fields.Char(string='try to connect on kibana', help='http://localhost:5601/', states={'confirm': [('readonly', True)]} )
    require_elasticserver_help = fields.Boolean('Setting Help', default=_get_default_require_elasticserver_help,
                                                help='')

    note = fields.Text(string='Note !!!',tracking=True)
    check_access = fields.Boolean('Check access', default=False)
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'ElasticServer name already exists!'),
    ]

    def action_need_help(self):
        self.require_elasticserver_help = not self.require_elasticserver_help

    @api.onchange('sftp_host', 'sftp_port', 'sftp_user', 'sftp_password')
    def check_connection(self):
        if self.is_success:
            self.is_success = False

    @api.onchange('sftp_last_run_metadata_path', 'sftp_jdbc_driver_library_path', 'sftp_logstash_bin_path','sftp_path','is_sftp_logstash_log_path')
    def is_check_access(self):
        if self.check_access:
            self.check_access = False

    @api.onchange('sftp_host')
    def get_elastic_url(self):
        if self.sftp_host:
            self.elastic_url = 'http://' + self.sftp_host.strip() + ':9200'
            self.kibana_url = 'http://' + self.sftp_host.strip() + ':5601'

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_confirm(self):
        connection = self.sftp_connection()
        access_path = self.test_access_file()
        if connection and access_path:
            self.write({'state': 'confirm', 'is_success': True})

    def import_jdbc_postgresql(self):
        if not self.sftp_jdbc_driver_library_path:
            raise UserError(_('set path to upload jdbc_driver_library ex: /etc/logstash '))

        return {
            'type': 'ir.actions.act_window',
            'name': _('jdbc.postgresql import'),
            'res_model': 'jdbc.postgresql.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id,
                        'default_path': self.sftp_jdbc_driver_library_path,
                        },
            'views': [[False, 'form']]
        }

    def sftp_connection(self):
        self.ensure_one()
        # Check if there is a success or fail and write messages
        message_title = ""
        message_content = ""
        error = ""
        has_failed = False

        ip_host = self.sftp_host.strip()
        port_host = self.sftp_port
        username_login = self.sftp_user.strip()
        password_login = self.sftp_password.strip()
        self.is_success = False
        # Connect with external server over SFTP, so we know sure that everything works.
        sftp = False
        try:
            s = paramiko.SSHClient()
            s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # allow_agent=False,look_for_keys=False
            s.connect(ip_host, port_host, username_login, password_login, allow_agent=False, look_for_keys=False,
                      timeout=10)
            sftp = s.open_sftp()
            self.is_success = True
            message_title = _("Connection Test Succeeded!\nEverything seems properly set up for FTP back-ups!")
        except Exception as e:
            _logger.critical('There was a problem connecting to the remote ftp: ' + str(e))
            error += str(e)
            has_failed = True
            message_title = _("Connection Test Failed!")
            if len(self.sftp_host) < 8:
                message_content += "\nYour IP address seems to be too short.\n"
            message_content += _("Here is what we got instead:\n")
        finally:
            if has_failed:
                raise Warning(message_title + '\n\n' + message_content + "%s" % str(error))
            else:
                return s

    def test_sftp_connection(self):
        con = self.sftp_connection()
        if con:
            con.close()
            return True

    def test_access_file(self):
        #### 1st control :folder #####
        self.check_access = True
        if not self.note:
            self.note = ' '
        s = self.sftp_connection()
        sftp = s.open_sftp()

        #### 2sd control :last run metadata #####
        self.is_defined_last_run = True
        try:
            if self.sftp_last_run_metadata_path:
                sftp.chdir(self.sftp_last_run_metadata_path.strip())
        except IOError as e:
            # Create directory and subdirs if they do not exist.
            self.is_defined_last_run = False
            self.note += 'Create new directory {}'.format(self.sftp_last_run_metadata_path)
            current_directory = ''
            if self.sftp_last_run_metadata_path:
                for dirElement in self.sftp_last_run_metadata_path.strip().split('/'):
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
                                _('last run metadata path is not defined ,we cannot create new folder %s') % (str(e)))

        #### 3rd control :PostgreSQL JDBC Driver #####
        if self.sftp_jdbc_driver_library_path:
            remotePath = os.path.dirname(self.sftp_jdbc_driver_library_path)
            base_file = os.path.basename(self.sftp_jdbc_driver_library_path)
            if not len(base_file.split('.jar'))>1:
                raise ValidationError(_(
                    'jdbc driver is not defined !!, you can download from the jdbc.postgresql.org and upload in your remote server , use the upload button'))
            self.is_defined_sftp_jdbc_path = False
            try:
                for file in sftp.listdir(remotePath):
                    if file == base_file:
                        self.is_defined_sftp_jdbc_path = True
            except Exception as e:
                # _logger.critical('There was a problem to create folder' + str(e))
                raise ValidationError(_(
                    'jdbc driver is not defined !!, you can download from the jdbc.postgresql.org and upload in your remote server , use the upload button  %s') % (
                                          str(e)))
            if not self.is_defined_sftp_jdbc_path:
                raise UserError(_("jdbc driver is not defined"))

        #### 4th control :Path Log file #####
        remotePath = os.path.dirname(self.sftp_logstash_log_path)
        base_file = os.path.basename(self.sftp_logstash_log_path)
        if not len(base_file.split('.log')) > 1:
            raise ValidationError(_(
                'log file is not defined !!, extension file must be .log'))
        self.is_sftp_logstash_log_path = False
        try:
            for file in sftp.listdir(remotePath):
                if file == base_file:
                    self.is_sftp_logstash_log_path = True
        except Exception as e:
            # _logger.critical('There was a problem to create folder' + str(e))
            raise ValidationError(_('Please check this required setting !!!!!! '
                                    'Logs =>The location of the log file varies by platform %s') % (
                                      str(e)))
        if not self.is_sftp_logstash_log_path:
            raise UserError(_("Log file is not defined"))
        #### 4th control :Path configuration file #####
        try:
            sftp.chdir(self.sftp_logstash_bin_path.strip())
            self.is_sftp_logstash_bin_path = True
        except Exception as e:
            raise ValidationError(_( 'Please check this required setting !!!!!! '
                'bin =>Binary scripts, including logstash to start Logstash. The location of the bin directory varies by platform %s') % (
                                      str(e)))
        if not self.is_sftp_logstash_bin_path:
            raise UserError(_("Bin is not defined"))
        #### 5th control :Path binary scripts #####
        try:
            sftp.chdir(self.sftp_path.strip())
            self.is_sftp_path = True
        except Exception as e:
            raise ValidationError(_('Please check this required setting !!!!!!'
                                    'conf =>Logstash pipeline configuration files, /etc/logstash/conf.d/*.conf %s') % (
                                      str(e)))


        return self.is_sftp_logstash_log_path and self.is_defined_last_run and self.is_defined_sftp_jdbc_path and self.is_sftp_logstash_bin_path


    def unlink(self):
        for elastic in self:
            if not elastic.state == 'draft':
                raise UserError(_('In order to delete a ElasticServer config, you must cancel it first.'))
        return super(ElasticSearchServer, self).unlink()