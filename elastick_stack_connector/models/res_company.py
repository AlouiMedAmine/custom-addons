# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    database_setting_help = fields.Boolean('Database setting help')
    elasticserver_setting_help = fields.Boolean('ElasticServer setting help')
    sql_query_help = fields.Boolean('Sql Query help')
    index_setting_help = fields.Boolean('Index setting help')
    #Index
    is_tracking_column = fields.Boolean(string='Activate tracking column',  default=False)
    use_column_value = fields.Char(string='use_column_value', default="true")
    tracking_column = fields.Char(string='tracking_column', default='write_date')
    tracking_column_type = fields.Char(string='tracking_column_type', default="timestamp")
    schedule = fields.Char(string='schedule')
    #logs
    size_logfile = fields.Integer(string='size_logfile',default=10000,)
    nb_ligne_logfile = fields.Integer(string='size_logfile',default=100)
    # models
    group_show_fields = fields.Boolean(string='Show menu fields',implied_group='elastick_stack_connector.group_show_fields')
    model_ids = fields.Many2many('ir.model','res_company_ir_model_rel','company_id','model_id',string="Models",related_sudo=False)
