# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from datetime import date


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    database_setting_help = fields.Boolean(related='company_id.database_setting_help',string='Database setting help', readonly=False)
    elasticserver_setting_help = fields.Boolean(related='company_id.elasticserver_setting_help',string='ElasticServer setting help', readonly=False)
    sql_query_help = fields.Boolean(related='company_id.sql_query_help',string='Sql Query help', readonly=False)
    index_setting_help = fields.Boolean(related='company_id.index_setting_help',string='Index setting help', readonly=False)
    #Index
    is_tracking_column = fields.Boolean(related='company_id.is_tracking_column',string='Activate tracking column', readonly=False)
    use_column_value = fields.Char(related='company_id.use_column_value',string='Use column Value',help="true or false")
    tracking_column = fields.Char(related='company_id.tracking_column', string='Tracking column', help="write_date or id or other fields" ,readonly=False)
    tracking_column_type = fields.Char(related='company_id.tracking_column_type',string='Tracking column type',help="timestamp or numeric",readonly=False)
    schedule = fields.Char(related='company_id.schedule',string='schedule', help='will execute on the 0 th minute of every hour every day.',readonly=False)
    #logs
    size_logfile = fields.Integer(related='company_id.size_logfile',string='size_logfile',help="10000 bytes",readonly=False)
    nb_ligne_logfile =  fields.Integer(related='company_id.nb_ligne_logfile',string='size_logfile',help="100 liges",readonly=False)
    #models
    group_show_fields = fields.Boolean(related='company_id.group_show_fields',string='Show menu fields',readonly=False)
    model_ids = fields.Many2many(related='company_id.model_ids',string="Models",readonly=False)

    @api.onchange('is_tracking_column')
    def onchange_is_tracking_column(self):
        if self.is_tracking_column:
            self.use_column_value = 'true'
        else:
            self.use_column_value = False
            self.tracking_column_type = False
            self.tracking_column = False

    @api.onchange('group_show_fields')
    def onchange_group_show_fields(self):
        if not self.group_show_fields:
            self.model_ids = False