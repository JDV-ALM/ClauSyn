{
    'name': 'Base de Vendedores con Comisión',
    'version': '18.0.1.0.1',
    'category': 'Sales/Commission',
    'summary': 'Módulo base para la gestión de vendedores con comisión',
    'description': """
        Módulo Base de Vendedores con Comisión
        =======================================
        
        Este módulo proporciona la base para la gestión de comisiones mediante:
        * Gestión de vendedores con comisión a través de registros de contacto
        * Seguimiento de vendedores en pagos, facturas y órdenes de venta
        * Agregar fecha de recepción a facturas para cálculos futuros de comisiones
        
        Parte de Commission Suites por Almus Dev (JDV-ALM)
    """,
    'author': 'Almus Dev (JDV-ALM)',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'sale',
        'account_payment',
    ],
    'data': [
        # Security
        'security/commission_seller_security.xml',
        'security/ir.model.access.csv',
        
        # Views - Must be loaded before menus
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/sale_order_views.xml',
        
        # Wizard
        'wizard/account_payment_register_views.xml',
        
        # Data - Load menus after views
        'data/menu_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}