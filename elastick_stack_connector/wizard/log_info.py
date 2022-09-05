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

from odoo import api, fields, models


class LogInfo(models.TransientModel):
    """ Import Module """
    _name = "log.info"
    _description = "log info logstash"

    note = fields.Text('Note',defualt='this test is running without options  schedule ==> "" ,in order to reduce response time ')
    log_info = fields.Text()




