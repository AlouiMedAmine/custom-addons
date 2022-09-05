# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, api, _
import jinja2
import os
import json
from odoo import exceptions, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

path = os.path.realpath(os.path.join(os.path.dirname(__file__), '../views'))
loader = jinja2.FileSystemLoader(path)
jinja_env = jinja2.Environment(loader=loader, autoescape=True)
jinja_env.filters["json"] = json.dumps

qry_list_template = jinja_env.get_template('query_list.html')


class SqlQuery(models.Model):
    _name = 'sql.query'
    _inherit = ["mail.thread"]
    _description = 'SQL QUERY'
    _order = 'sequence,id'

    def _get_default_require_query_help(self):
        return self.env.company.sql_query_help

    def _get_default_restricted_model_ids(self):
        return self.env.company.model_ids.ids

    def get_restricted_model_ids(self):
        for query in self:
            query.restricted_model_ids = self.env.company.model_ids.ids


    name = fields.Char('Statment Name',states={'confirm': [('readonly', True)]},tracking=True)
    query = fields.Text(string='Select Query',states={'confirm': [('readonly', True)]},tracking=True)
    result = fields.Html(string='Result', readonly="1")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    restricted_model_ids = fields.Many2many('ir.model',compute='get_restricted_model_ids',default=_get_default_restricted_model_ids,string="Models")
    model_id = fields.Many2one('ir.model', string="Model", )
    field_ids = fields.Many2many('ir.model.fields', string="Fields")
    all_fields = fields.Boolean('All stored field',default=False)
    active = fields.Boolean('Active', default=True,tracking=True)
    sequence = fields.Integer()
    sucess_query = fields.Boolean('Success', default=False)
    is_success = fields.Boolean('Is Success', default=False)
    state = fields.Selection([
        ('draft', 'Not Confirmed'),
        ('confirm', 'Confirmed'),
    ], string='Status', index=True, tracking=True, readonly=True, copy=False, default='draft')
    require_query_help = fields.Boolean('Setting Help', default=_get_default_require_query_help,
                                           help='')

    def action_need_help(self):
        self.require_query_help = not self.require_query_help

    def action_draft(self):
        self.write({'state': 'draft','is_success':False})

    def action_confirm(self):
        self.execute_qry()
        self.write({'state': 'confirm','result':'','is_success':True})


    def clear_result(self):
        self.result = ''

    @api.onchange('all_fields','model_id')
    def get_all_stored_fields(self):
        if self.all_fields and self.model_id:
            field_ids = self.env['ir.model.fields'].search([('model_id','=',self.model_id.id),('store','=',True),('ttype','not in',('one2many','many2many','binary'))]).ids
            self.field_ids = [(6,0,field_ids)] or []
        else:
            self.field_ids = False

    @api.onchange('field_ids')
    def onchange_field_ids(self):
        sql_query = ""
        fields = ""
        if self.field_ids and self.model_id:
            for line in self.field_ids:
                fields = ', '.join([line.name for line in self.field_ids])
            model = self.model_id.model.replace('.','_')
            sql_query = "select %s from %s"%(fields,model)
        self.query = sql_query



    def execute_qry(self):
        if not self.query:
            raise exceptions.UserError(_('There are no select query to be validate !!!!: '))
        quey_word = ['delete ','update ','create ','drop ']
        for quey in quey_word:
            if quey in self.query:
                self.result = ''
                raise exceptions.UserError(_('You cannot accept %s query.'%(quey)))
        exception_happened =True
        query_result = []
        try:
            self.env.cr.execute(self.query)
            query_result = self.env.cr.dictfetchall()
            self.is_success = True
            exception_happened = False
        except Exception as e:
            raise exceptions.UserError(_('Query Exeption :  %s.' % (str(e))))
        results = []
        columns = []
        if query_result:
            vals = []
            Flag = False
            for val in query_result:
                for k, v in val.items():
                    vals.append(v)

                results.append(vals)
                vals = []

                if not Flag:
                    for k, v in val.items():
                        columns.append(k)
                    Flag = True

        type = 'success'
        if not results:
            type = 'failed'
        self.result = qry_list_template.render({
            'type': type,
            'columns': columns,
            'results': results,
            'empty_query': 'no recorded is selected !!!!!!'

        })
        return True


    def unlink(self):
        for query in self:
            if not query.state == 'draft':
                raise UserError(_('In order to delete a database config, you must cancel it first.'))
        return super(SqlQuery, self).unlink()