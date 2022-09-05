# -*- coding: utf-8 -*-

import logging
from odoo.osv import expression
from odoo import fields, models, api, _
_logger = logging.getLogger(__name__)


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # TDE FIXME: strange
        models = []
        context = self._context or {}
        if context.get('selected_object') and self.env.company.group_show_fields:
            for model_id in self.env.company.model_ids:
                models.append(model_id.model)
            args.append((('model_id', 'in',models)))
        return super(IrModelFields, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                                   access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        context = self._context or {}
        models = []
        context = self._context or {}
        if context.get('selected_object') and self.env.company.group_show_fields:
            for moodel_id in self.env.company.model_ids:
                models.append(moodel_id.model)
            domain = expression.AND([domain, [('model_id', 'in',models)]])
        return super(IrModelFields, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                     orderby=orderby,
                                                     lazy=lazy)
