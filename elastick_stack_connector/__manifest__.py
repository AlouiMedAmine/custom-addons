# -*- encoding: utf-8 -*-
{
    'name': "Elastic Stack Connector",
    'summary': """Users can use Elasticsearch, Kibana and Logstash (also known as the ELK Stack). 
    Reliably and securely take data from Odoo, in any format, then search, analyze, and visualize it in real time.""",
    'description': """
        
    """,
    'version': '1.0',
    'category': 'Dashboard',
    'license': 'OPL-1',
    'author': "Aloui Mohamed Amine",
    'live_test_url': 'https://youtu.be/Mc4MfqeHi74',
    'website': "",
    'contributors': [
    ],
    'support': '',
    'depends': [
        'base',
        'web',
        'mail'
    ],
    'data': [

        #### security ####
        'security/ir.model.access.csv',
        'security/elk_security.xml',

        #### Wizard ####
        'wizard/upload_postgresql_view.xml',
        'wizard/log_info_view.xml',

        #### views ####
        'views/menu_root.xml',
        'views/database_config.xml',
        'views/elasticsearch_server.xml',
        'views/logstash_config.xml',
        'views/sql_query.xml',
        'views/ir_model_fields.xml',
        'views/res_config_settings_views.xml',

    ],
     'images': [
        'static/images/main_screenshot.gif'
    ],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 150,
    'currency': 'EUR',

}
