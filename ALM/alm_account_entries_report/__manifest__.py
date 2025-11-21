# -*- coding: utf-8 -*-
{
    'name': 'Reporte de Apuntes Contables - ALM',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Wizard para reporte de apuntes contables por tipo de cuenta',
    'description': """
        Reporte de Apuntes Contables por Tipo
        ======================================
        
        Permite generar reportes de apuntes contables con filtros:
        
        * Por tipo de cuenta (Por Cobrar/Por Pagar)
        * Por Cliente o Proveedor
        * Por Vendedor
        * Por Rango de fechas
        * Exportación en Excel o PDF
        
        Desarrollado por Almus Dev (JDV-ALM)
        www.almus.dev
    """,
    'author': 'Almus Dev',
    'website': 'https://www.almus.dev',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'sale',
        'commission_seller_base',
        'account_alternate_amounts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/account_entries_wizard_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}