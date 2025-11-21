# -*- coding: utf-8 -*-
{
    'name': 'Account Alternate Amounts USD',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Agrega campos de débito y crédito en USD en líneas de asientos contables',
    'description': """
        Módulo que agrega campos de débito y crédito en USD
        en las líneas de asientos contables (account.move.line).
        
        Características:
        - Conversión automática a USD usando la tasa del día de la transacción
        - Campos almacenados para reportes futuros
        - Recálculo automático cuando cambia la fecha
        - Campos de solo lectura
        - Muestra la tasa de cambio USD
    """,
    'author': 'Almus Dev (JDV-ALM)',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/account_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
