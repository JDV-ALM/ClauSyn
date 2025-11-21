# -*- coding: utf-8 -*-
{
    'name': 'Product Cost USD',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Resguarda costos de productos en USD',
    'author': 'Almus Dev',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'stock_account',
    ],
    'data': [
        'views/product_views.xml',
    ],
    'installable': True,
    'application': False,
}
