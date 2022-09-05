# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.tools import config, detect_ip_addr
from odoo.exceptions import AccessError, UserError
import pytz


class DatabaseConfig(models.Model):
    _name = 'database.config'
    _inherit = ["mail.thread"]
    _description = 'Database Config'
    _order = 'sequence,id'

    def _get_default_require_database_help(self):
        return self.env.company.sql_query_help

    @api.model
    def _jdbc_tz_get(self):
        return [(x, x) for x in pytz.all_timezones]


    name = fields.Char('Name', )
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer()
    state = fields.Selection([
        ('draft', 'Not Confirmed'),
        ('confirm', 'Confirmed'),
    ], string='Status', tracking=True, index=True, readonly=True, copy=False, default='draft')
    current_db = fields.Boolean('Current Database', default=False, states={'confirm': [('readonly', True)]} )
    jdbc_driver_class = fields.Char(string='jdbc_driver_class', states={'confirm': [('readonly', True)]} )
    jdbc_connection_string = fields.Char(string='jdbc_connection_string', states={'confirm': [('readonly', True)]} ,tracking=True)
    jdbc_user = fields.Char(string='jdbc_user', states={'confirm': [('readonly', True)]} ,tracking=True)
    jdbc_password = fields.Char(string='jdbc_password', states={'confirm': [('readonly', True)]} )
    jdbc_paging_enabled = fields.Char(string='jdbc_paging_enabled', default='true',
                                      states={'confirm': [('readonly', True)]} ,tracking=True)
    jdbc_page_size = fields.Char(string='jdbc_page_size', default=50000, states={'confirm': [('readonly', True)]})
    jdbc_default_timezone = fields.Selection('_jdbc_tz_get', string='Timezone',states={'confirm': [('readonly', True)]} ,
                                             default=lambda self: self.env.context.get('tz'),tracking=True)

    require_database_help = fields.Boolean('Setting Help', default=_get_default_require_database_help,
                                           help='')
    is_success = fields.Boolean('Is Success', default=False)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Database name already exists!'),
    ]


    def action_need_help(self):
        self.require_database_help = not self.require_database_help

    def action_draft(self):
        self.write({'state': 'draft','is_success':False})

    def action_confirm(self):
        self.write({'state': 'confirm','is_success':True})

    @api.onchange('current_db')
    def _onchange_is_current_db(self):
        query = "show timezone;"
        self.env.cr.execute(query)
        for val in self.env.cr.dictfetchall():
            postgress_timezone = val['TimeZone']
        host = detect_ip_addr()
        if self.current_db:
            self.jdbc_driver_class = 'org.postgresql.Driver'
            if config['db_user']:
                self.jdbc_user = config['db_user']
            if config['db_password']:
                self.jdbc_password = config['db_password']
            if postgress_timezone and postgress_timezone != 'localtime':
                self.jdbc_default_timezone = postgress_timezone
            port = '5432'
            if config['db_port']:
                port = config['db_port']
            if host and config['db_name']:
                self.jdbc_connection_string = 'jdbc:postgresql://' + host + ':' + port + '/' + config['db_name']

    def unlink(self):
        for db in self:
            if not db.state == 'draft':
                raise UserError(_('In order to delete a database config, you must cancel it first.'))
        return super(DatabaseConfig, self).unlink()