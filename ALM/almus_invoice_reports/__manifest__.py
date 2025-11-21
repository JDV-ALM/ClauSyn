# -*- coding: utf-8 -*-
{
    'name': 'Almus Invoice Reports',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Reportes personalizados de facturas para Almus Dev',
    'description': """
        Módulo de reportes personalizados de facturas para Almus Dev
        ==============================================================
        
        Incluye:
        - Reporte de Proforma en USD (original)
        - Reporte de Proforma en VES (sin logo ni datos de emisor)
        
        Desarrollado por: Almus Dev (JDV-ALM)
        Website: www.almus.dev
    """,
    'author': 'Almus Dev',
    'website': 'https://www.almus.dev',
    'depends': [
        'account',
        'web',
    ],
    'data': [
        # Reportes originales en USD
        'views/report_actions.xml',
        'views/report_invoice_document.xml',
        
        # Nuevos reportes en VES
        'views/report_actions_ves.xml',
        'views/report_invoice_document_ves.xml',
        
        # Reporte mejorado con vendedor, notas y pie de página legal
        'views/report_actions_enhanced.xml',
        'views/report_invoice_document_enhanced.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}