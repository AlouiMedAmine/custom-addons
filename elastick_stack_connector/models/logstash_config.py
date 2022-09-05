# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
import itertools
from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning, AccessDenied, UserError, ValidationError
import os
import base64
import pytz
from odoo.tools.misc import str2bool, xlsxwriter, file_open
from odoo.addons.base.models.res_partner import _tz_get

try:
    import elasticsearch
except ImportError:
    raise ImportError(
        'This module needs search API for the Python Elasticsearch Client '
        'Please install elasticsearch on your system. (sudo pip3 install elasticsearch)')

from elasticsearch import Elasticsearch


class Tag(models.Model):
    """ class Tag """
    # pylint: disable=too-few-public-methods
    _name = "logstash.tag"
    _description = "Logstash Tag"

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class LogstashConfig(models.Model):
    _name = 'logstash.config'
    _inherit = ["mail.thread"]
    _description = 'Logstash Config'
    _rec_name = "index"
    _order = 'sequence,id'

    def _get_default_require_index_help(self):
        return self.env.company.index_setting_help

    def _get_default_require_use_column(self):
        return self.env.company.use_column_value

    def _get_default_require_column_type(self):
        return self.env.company.tracking_column_type

    def _get_default_require_column(self):
        return self.env.company.tracking_column

    def _get_default_require_schedule(self):
        return self.env.company.schedule

    def _get_default_nb_ligne_logfile(self):
        return self.env.company.nb_ligne_logfile

    def _get_default_size_logfile(self):
        return self.env.company.size_logfile

    @api.model
    def _default_user(self):
        return self.env.context.get('user_id', self.env.user.id)

    @api.model
    def _jdbc_tz_get(self):
        return [(x, x) for x in pytz.all_timezones]

    name = fields.Char('Name', copy=False)
    user_id = fields.Many2one('res.users', string='User', default=_default_user, tracking=True)
    state = fields.Selection([
        ('draft', 'Not Confirmed'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validate')
    ], string='Status', index=True, tracking=True, readonly=True, copy=False, default='draft')
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer()
    color = fields.Integer('Color Index')
    tag_ids = fields.Many2many(
        'logstash.tag',
        'logstash_tags_rel',
        'index_id',
        'tag_id',
        string='Tags')
    elastic_server_id = fields.Many2one('elasticsearch.server', string="Elastic Server", tracking=True)
    db_setting_id = fields.Many2one('database.config', string="Odoo server (Database)", tracking=True)
    statement_id = fields.Many2one('sql.query', string="Statement", tracking=True)

    ######  jdbc  ########
    schedule = fields.Char(string='schedule', default=_get_default_require_schedule, )
    statement = fields.Text(string='statement')
    use_column_value = fields.Char(string='use_column_value', default=_get_default_require_use_column, )
    tracking_column = fields.Char(string='tracking_column', default=_get_default_require_column, )
    tracking_column_type = fields.Char(string='tracking_column_type', default=_get_default_require_column_type, )
    last_run_metadata_path = fields.Char(string='last_run')
    jdbc_paging_enabled = fields.Char(string='jdbc_paging_enabled')
    jdbc_page_size = fields.Char(string='jdbc_page_size')
    jdbc_default_timezone = fields.Selection('_jdbc_tz_get', string='Timezone',
                                             default=lambda self: self.env.context.get('tz') or self.user_id.tz)

    ###### output #########
    hosts = fields.Char(string='hosts')
    index = fields.Char(string='index', copy=False, tracking=True, help="Should be in lowercase !!")
    document_id = fields.Char(string='document_id')
    require_index_help = fields.Boolean('Setting Help', default=_get_default_require_index_help,
                                        help='')
    ## Result #####
    setting_data = fields.Text('Settings')
    filename = fields.Char(string='filename')
    file = fields.Binary(string='Config file', readonly="1")
    hits_count = fields.Integer("Total values #Hits", readonly=1, tracking=True)
    is_info_kibana = fields.Boolean('Info Kibana')
    is_info_elastic = fields.Boolean('Info elastic')
    is_info_logstash = fields.Boolean('Info logstash')

    #### logs
    update_log_info = fields.Boolean('Update log info', )
    nb_ligne_logfile = fields.Integer(string=' Logfile size (lines)', default=_get_default_nb_ligne_logfile, )
    size_logfile = fields.Integer(string='Logfile size (bytes)', default=_get_default_size_logfile,
                                  help='This is the number of bytes to be read from the log file')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Logstashconfig name already exists!'),
        ('index_uniq', 'unique (index)', 'Index name already exists!'),
    ]

    @api.onchange('db_setting_id')
    def onchange_db_setting_id(self):
        if self.db_setting_id:
            self.jdbc_default_timezone = self.db_setting_id.jdbc_default_timezone

    @api.onchange('statement_id')
    def onchange_statement_id(self):
        if self.statement_id:
            self.statement = self.statement_id.query

    def action_need_help(self):
        self.require_index_help = not self.require_index_help

    def info_kibana(self):
        self.is_info_kibana = not self.is_info_kibana

    def info_elastic(self):
        self.is_info_elastic = not self.is_info_elastic

    def info_logstash(self):
        self.is_info_logstash = not self.is_info_logstash

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel_validate(self):
        # delete your pipeline.conf from your logstash settings and delete this index from kibana
        if not self.active:
            self.delete_setting_index()
        self.write({'state': 'confirm'})

    def log_info(self, output):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log info'),
            'res_model': 'log.info',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id,
                        'default_log_info': output,
                        },
            'views': [[False, 'form']]
        }

    def get_data(self, output_type):
        setting_data = self.setting_data
        if output_type == 'json':
            json_line = " \n  output {stdout { codec => json_lines }}"
            # option schedule is ignored when you run json test
            setting_data = self.setting_data.replace('schedule', '#schedule')
            setting_data = setting_data.split('output')
            setting_data = setting_data[0] + json_line
        elif output_type == 'index':
            setting_data = self.setting_data.replace('jdbc_driver_library', '#jdbc_driver_library')
        return setting_data

    def elastic_connection(self):
        hosts = self.elastic_server_id.elastic_url.strip()
        user = self.elastic_server_id.elastic_login.strip()
        password = self.elastic_server_id.elastic_password.strip()
        if hosts and user and password:
            try:
                elastic = Elasticsearch(hosts=[hosts], http_auth=(user, password))
                return elastic
            except Exception as e:
                raise ValidationError(_('Connection denied !!!,') % (str(e)))

    def delete_index(self):
        elastic = self.elastic_connection()
        try:
            indices = elastic.indices.get_alias().keys()
            elastic.indices.delete(index=self.index.strip().lower(), ignore=[400, 404])
            self.message_post(body=_('(%s) has been deleted with success from kibana') % (self.index.strip().lower()))
            self.hits_count = 0
            if self.schedule:
                self.info_delete = ''
        except Exception as e:
            raise ValidationError(_('Action deleted index from kibana is failed !!!, %s') % (str(e)))

    def delete_setting_index(self):
        #### delete from your Configuration file conf.d
        sftp_path = self.elastic_server_id.sftp_path.strip()
        filename = self.filename
        # ssh connection
        s = self.elastic_server_id.sftp_connection()
        sftp = s.open_sftp()
        try:
            sftp.chdir(sftp_path)
        except IOError as e:
            raise ValidationError(
                _('Path configuration file is not defined ,define this path in your elasticserver  %s'
                  'Exeption: %s') % (self.elastic_server_id.name, str(e)))
        try:
            sftp.remove(os.path.join(sftp_path, filename))
        except IOError as e:
            raise ValidationError(
                _("you don't have access to remove the config file %s  \n"
                  "from your remote server ,%s \n"
                  "Exeption: %s") % (filename, sftp_path, str(e)))
        self.message_post(body=_('(%s) has been deleted with success from logstash conf.d') % (filename))
        #### delete from kibana
        self.delete_index()

    def recreate_index(self):
        self.action_run('index')
        # self.get_hits()

    def get_log_info(self):
        s = self.elastic_server_id.sftp_connection()
        sftp = s.open_sftp()
        logfile = self.elastic_server_id.sftp_logstash_log_path
        nb_ligne = self.nb_ligne_logfile
        cmd = 'tail -%s %s' % (nb_ligne, logfile)
        try:
            get_pid = 'echo $$ ; exec '
            stdin, stdout, stderr = s.exec_command(get_pid + cmd, timeout=60, get_pty=True)
            pid = stdout.readline().strip()
            size = self.size_logfile
            output = stdout.read()
            # _, stdout, _ = s.exec_command("ps -eo pid,command | grep %s" % pid)
            s.exec_command("kill -s SIGINT %s" % pid)
            s.exec_command("ps aux | grep - i /tmp/" + self.filename + " | awk {'print $2'} | xargs kill - 9")
            s.close()

            return self.log_info(output)
        except Exception as e:
            raise ValidationError(_(
                'This action take more than 3 minutes,it will be blocked,please make the test in your remote server %s') % (
                                      str(e)))

    def get_hits(self):
        try:
            elastic = self.elastic_connection()
            res = elastic.search(index=self.index.strip().lower(), body={"query": {"match_all": {}}})
            if res['hits']['total']['value']:
                self.hits_count = int(res['hits']['total']['value'])
        except Exception as e:
            raise ValidationError(_('     There is an exception !!     \n %s ') % (str(e)))

    def action_run(self, output_type):
        self.ensure_one()
        setting_data = self.get_data(output_type)
        filename = self.index.strip().lower() + '.conf'
        self.filename = filename
        sftp_path = self.elastic_server_id.sftp_path.strip()
        # ssh connection
        s = self.elastic_server_id.sftp_connection()
        sftp = s.open_sftp()

        # create file in /tmp (Local)
        try:
            fp = open('/tmp/' + 'local_' + filename, 'w')
            fp.write(setting_data)
            fp.close()
        except IOError:
            print("you can't create %s in /tmp to run json test !!!" % (filename))
        # Validate your index ==> result: create index in kibana
        # in logtsash.yaml ==> config.reload.automatic: true

        # create your index.conf
        try:
            f = open('/tmp/' + 'local_' + filename, 'rb')
            sftp.chmod(os.path.join('/tmp/', 'local' + filename), 0o777)
            self.file = base64.encodestring(f.read())
            f.close()
            self.message_post(body=_('(%s) has been created with success') % (filename))
        except IOError:
            print('error')

        # put the file.conf in conf.d
        try:
            sftp.chdir(sftp_path)
        except IOError as e:
            raise ValidationError(
                _('Path configuration file is not defined ,define this path in your elasticserver  %s'
                  'Exeption: %s') % (self.elastic_server_id.name, str(e)))
        try:
            if output_type == 'index':
                sftp.put('/tmp/' + 'local_' + filename, os.path.join(sftp_path, filename))
                sftp.chmod(os.path.join(sftp_path, filename), 0o777)
            else:
                sftp.put('/tmp/' + 'local_' + filename, os.path.join('/tmp/', filename))

        except IOError as e:
            raise ValidationError(
                _("you don't have access to put the new config file %s  \n"
                  "In your remote server run this cmd: sudo chmod 777 -R %s \n"
                  "Exeption: %s") % (filename, sftp_path, str(e)))

        if output_type == 'index':
            # put the .jdbc_last_run_indexName in Last run metadata folder
            last_run_metadata_path = self.elastic_server_id.sftp_last_run_metadata_path
            last_run_file = '.jdbc_last_run_' + self.index.strip().lower()
            try:
                sftp.chdir(last_run_metadata_path)
            except IOError as e:
                raise ValidationError(
                    _('Path Last run metadata folder is not defined ,define this path in your elasticserver  %s'
                      'Exeption: %s') % (self.elastic_server_id.name, str(e)))
            try:
                ### if you click in "RUN LOGSTASH TEST" , the file last run metadata 'll be create by the user used in sftp connection
                ### you should delete this file, but when you validate your index, logstash 'll create the new file with the user logstash
                sftp.remove(os.path.join(last_run_metadata_path, last_run_file))

            except IOError as e:
                pass

        # Run Test ==> resultat: json lines
        elif output_type == 'json':
            # check the path logstash/bin
            try:
                sftp.chdir(self.elastic_server_id.sftp_logstash_bin_path.strip())
            except Exception as e:
                raise ValidationError(_('Please check this required setting !!!!!! '
                                        'bin =>Binary scripts, including logstash to start Logstash. The location of the bin directory varies by platform %s') % (
                                          str(e)))
            # run your file with logstash/bin cmd
            bin = self.elastic_server_id.sftp_logstash_bin_path.strip() + '/logstash'
            cmd = bin + ' -f ' + os.path.join('/tmp', filename)
            try:
                get_pid = 'echo $$ ; exec '
                stdin, stdout, stderr = s.exec_command(get_pid + cmd, timeout=60, get_pty=True)
                pid = stdout.readline().strip()
                size = self.size_logfile
                output = stdout.read(size)
                # _, stdout, _ = s.exec_command("ps -eo pid,command | grep %s" % pid)
                s.exec_command("kill -s SIGINT %s" % pid)

                #### kill service ,if we have in ussue in your test
                cmd = "ps aux  |  grep -i %s  |  awk '{print $2}'  |  xargs kill -9" % (os.path.join('/tmp', filename))
                stdin, stdout, stderr = s.exec_command(cmd, timeout=60, get_pty=True)
                s.close()

                return self.log_info(output)
            except Exception as e:
                raise ValidationError(_(
                    'This action take more than 3 minutes,it will be blocked,please make the test in your remote server %s') % (
                                          str(e)))

    def action_run_validate(self):
        self.action_run('index')
        self.write({'state': 'validate'})
        # self.get_hits()

    def action_run_test(self):
        return self.action_run('json')
        # ps aux  |  grep -i /tmp/partner
        # ps aux  |  grep -i /tmp/partner  |  awk '{print $2}'  |  xargs kill -9

    def update_option(self, input, key, val):
        if not val:
            if ('#' + key) not in input:
                input = input.replace(key, '#' + key)
        else:
            if ('#' + key) in input:
                input = input.replace('#' + key, key)
        return input

    def action_confirm(self):
        options = {}
        schedule = ""
        if self.schedule:
            schedule = self.schedule
        options['schedule'] = schedule

        use_column_value = ""
        if self.use_column_value:
            use_column_value = self.use_column_value
        options['use_column_value'] = use_column_value

        tracking_column = ""
        if self.tracking_column:
            tracking_column = self.tracking_column
        options['tracking_column'] = tracking_column

        tracking_column_type = ""
        if self.tracking_column_type:
            tracking_column_type = self.tracking_column_type
        options['tracking_column_type'] = tracking_column_type

        #### info from elastic server #####
        jdbc_driver_library = self.elastic_server_id.sftp_jdbc_driver_library_path
        last_run_metadata_path = self.elastic_server_id.sftp_last_run_metadata_path
        last_run_file = '.jdbc_last_run_' + self.index.strip().lower()
        if last_run_metadata_path:
            last_run_metadata_path = os.path.join(last_run_metadata_path, last_run_file)
        #### info from odoo server (database config) ####
        jdbc_driver_class = self.db_setting_id.jdbc_driver_class
        jdbc_connection_string = self.db_setting_id.jdbc_connection_string
        jdbc_user = self.db_setting_id.jdbc_user
        jdbc_password = self.db_setting_id.jdbc_password
        jdbc_paging_enabled = self.db_setting_id.jdbc_paging_enabled
        jdbc_page_size = self.db_setting_id.jdbc_page_size
        jdbc_default_timezone = self.jdbc_default_timezone

        ##### info from your statement #######
        statement = self.statement_id.query

        ##### update statement #####
        #### add ==> WHERE use_column_value > :sql_last_value
        #### WEHRE, where, Where, ....
        keyword_where = False
        if use_column_value and tracking_column:
            all_combinaison = map(''.join, itertools.product(*((c.upper(), c.lower()) for c in 'where')))
            tracking_sql = " WHERE %s > :sql_last_value" % (tracking_column)
            for key in all_combinaison:
                if key in statement and 'sql_last_value' not in statement:
                    statement.replace(key, tracking_sql + ' and ')
                    keyword_where = True
                    break
            if not keyword_where:
                statement += tracking_sql

        input = """
        input {

            jdbc {
            
                jdbc_driver_library => "%s"
                
                jdbc_driver_class => "%s"
                
                jdbc_connection_string => "%s"
                
                jdbc_user => "%s"
                
                jdbc_password => "%s"
                
                schedule => "%s"
                
                statement => "%s"
               
                use_column_value => %s
                
                tracking_column => "%s"
                
                tracking_column_type => "%s"
                
                last_run_metadata_path => "%s"
                
                jdbc_paging_enabled => "%s"
                
                jdbc_page_size => %s
                
                jdbc_default_timezone => "%s"
            
            }
            
        }
        
        """ % (jdbc_driver_library, jdbc_driver_class, jdbc_connection_string
                               , jdbc_user, jdbc_password, schedule, statement
                               , use_column_value, tracking_column, tracking_column_type, last_run_metadata_path
                               , jdbc_paging_enabled, jdbc_page_size, jdbc_default_timezone)

        ##### update options  ####
        for key, val in options.items():
            input = self.update_option(input, key, val)

        ######## output #########
        hosts = self.elastic_server_id.elastic_url
        index = self.index
        document_id = self.document_id
        user = self.elastic_server_id.elastic_login
        password = self.elastic_server_id.elastic_password
        output = """
        output
        { 
            elasticsearch
            {
                hosts => "%s"
                index => "%s"
                document_id => "%s"
                user => %s
                password => %s
            }
        }
        """ % (hosts, index, document_id, user, password)

        self.setting_data = input + output
        self.write({'state': 'confirm', 'require_index_help': False})

    def unlink(self):
        for index in self:
            if index.active and not index.state == 'draft':
                raise UserError(_('In order to delete an index, you must be Archived  or in draft state !!'))
        return super(LogstashConfig, self).unlink()
