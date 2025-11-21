# -*- coding: utf-8 -*-
{
    'name': 'Bank Tesote Integration',
    'version': '1.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Sync bank statements from Tesote API with retry logic and rate limiting',
    'description': """
        Integration with Tesote API v2 for automatic bank statement import.
        
        Features:
        - Automatic rate limiting (max 200 requests/minute)
        - Retry logic with exponential backoff
        - Enhanced error handling
        - Smart pagination support
        
        Developed by Almus Dev (JDV-ALM) - www.almus.dev
    """,
    'author': 'Almus Dev',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'account_accountant',
        'account_bank_statement_import'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_views.xml',
        'wizard/tesote_sync_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}