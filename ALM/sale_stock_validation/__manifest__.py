# -*- coding: utf-8 -*-
{
    'name': 'Sale Stock Validation',
    'version': '18.0.1.0.3',
    'category': 'Sales',
    'summary': 'Previene confirmación de órdenes sin stock suficiente',
    'description': """
        Control de Stock en Confirmación de Ventas
        ===========================================
        
        Evita confirmar cotizaciones cuando:
        * Un producto no tiene stock disponible
        * La cantidad disponible es insuficiente
        
        Desarrollado por Almus Dev (JDV-ALM)
        www.almus.dev
    """,
    'author': 'Almus Dev (JDV-ALM)',
    'website': 'https://www.almus.dev',
    'depends': [
        'sale_stock',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
