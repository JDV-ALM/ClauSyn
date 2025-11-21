{
    'name': 'Aged Receivable Report Filter per Salesperson',
    'version': '1.0.1',
    'category': 'Accounting',
    'summary': """Aged Receivable Report Filter per Salesperson
    filter aged receivable per Salesperson
    filter aged receivable by Salesperson
    Odoo aged receivable filter per salesperson
    salesperson filter
    aged receivable group by salesperson
    aged receivable Salesperson
    aged receivable by Salesperson
    aged receivable Salesperson filter
    """,
    'description': """ Aged Receivable Report Filter per Salesperson
    """,
    'author': 'Waleed Mohsen',
    'license': 'OPL-1',
    'currency': 'USD',
    'price': 45.0,
    'support': 'mohsen.waleed@gmail.com',
    'depends': ['account_reports'],
    "data": [
        'data/accounts_report_data.xml',
        'data/accounts_report_column.xml',
        'views/search_template_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wm_ar_salesperson_filter/static/src/**/*',
        ],
    },
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
}
