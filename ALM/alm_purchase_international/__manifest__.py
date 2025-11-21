# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Compras Internacionales',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Separación de compras nacionales e internacionales',
    'description': """
        Módulo para separar compras nacionales e internacionales
        ==========================================================
        
        Funcionalidades:
        ----------------
        * Campo booleano para identificar compras internacionales
        * Grupo de seguridad específico para compras internacionales
        * Control de visibilidad basado en grupos
        * Indicador visual en vistas
        
        Desarrollado por: Almus Dev (JDV-ALM)
        Web: www.almus.dev
    """,
    'author': 'Almus Dev',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'base',
    ],
    'data': [
        'security/purchase_security.xml',
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}