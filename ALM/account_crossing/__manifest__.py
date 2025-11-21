# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Account Crossing',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Cruce contable de facturas con motivos configurables',
    'description': """
        Módulo de cruce contable para facturas
        ========================================
        
        Permite realizar cruces contables en facturas mediante un wizard,
        similar al registro de pagos, con motivos de cruce configurables
        por empresa.
        
        Características:
        - Motivos de cruce con cuenta y diario configurables
        - Soporte multi-empresa
        - Trazabilidad completa de cruces
        - Integración con facturas de cliente y proveedor
    """,
    'author': 'Almus Dev (JDV-ALM)',
    'website': 'https://www.almus.dev',
    'depends': ['account', 'commission_seller_base'],
    'data': [
        'security/account_crossing_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/account_crossing_wizard_views.xml',
        'views/account_crossing_reason_views.xml',
        'views/account_crossing_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}