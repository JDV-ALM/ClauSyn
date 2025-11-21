# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import xlsxwriter
import io
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class AccountEntriesWizard(models.TransientModel):
    """
    Wizard para generar reporte de apuntes contables
    
    Desarrollado por Almus Dev (JDV-ALM)
    www.almus.dev
    """
    _name = 'account.entries.wizard'
    _description = 'Wizard Reporte de Apuntes Contables'
    
    # Campos del wizard
    account_type = fields.Selection([
        ('receivable', 'Cuentas por Cobrar'),
        ('payable', 'Cuentas por Pagar'),
        ('both', 'Ambas')
    ], string='Tipo de Cuenta', required=True, default='receivable')
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente/Proveedor',
        help='Dejar vacío para incluir todos'
    )
    
    # CAMBIO: Usar commission_seller_id en lugar de user_id
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        domain=[('is_commission_seller', '=', True)],
        help='Vendedor responsable de las facturas'
    )
    
    date_from = fields.Date(
        string='Fecha Desde',
        default=fields.Date.today().replace(day=1)
    )
    
    date_to = fields.Date(
        string='Fecha Hasta',
        default=fields.Date.today()
    )
    
    state = fields.Selection([
        ('all', 'Todos'),
        ('posted', 'Confirmados'),
        ('draft', 'Borrador')
    ], string='Estado', default='posted')
    
    output_format = fields.Selection([
        ('excel', 'Excel'),
        ('pdf', 'PDF')
    ], string='Formato', default='excel', required=True)
    
    # Campos para almacenar el archivo generado
    report_file = fields.Binary('Archivo de Reporte', readonly=True)
    report_filename = fields.Char('Nombre del Archivo', readonly=True)
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Incluir movimientos conciliados
    include_reconciled = fields.Boolean(
        string='Incluir Apuntes Conciliados',
        default=True
    )
    
    # Excluir facturas con saldo cero
    exclude_zero_invoices = fields.Boolean(
        string='Excluir Documentos Saldados',
        default=False,
        help='No mostrar facturas pagadas completamente ni pagos totalmente aplicados'
    )
    
    # Agrupar por partner
    group_by_partner = fields.Boolean(
        string='Agrupar por Cliente/Proveedor',
        default=True
    )
    
    @api.onchange('account_type')
    def _onchange_account_type(self):
        """
        Limpia el partner cuando cambia el tipo de cuenta
        """
        self.partner_id = False
        
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Ajusta el tipo de cuenta según el partner seleccionado
        """
        if self.partner_id:
            if self.partner_id.customer_rank > 0 and self.partner_id.supplier_rank == 0:
                self.account_type = 'receivable'
            elif self.partner_id.supplier_rank > 0 and self.partner_id.customer_rank == 0:
                self.account_type = 'payable'
    
    def _get_domain(self):
        """
        Construye el dominio para filtrar los apuntes contables
        """
        domain = [('company_id', '=', self.company_id.id)]
        
        # Filtro por tipo de cuenta
        if self.account_type == 'receivable':
            domain.append(('account_id.account_type', '=', 'asset_receivable'))
        elif self.account_type == 'payable':
            domain.append(('account_id.account_type', '=', 'liability_payable'))
        elif self.account_type == 'both':
            domain.append(('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']))
        
        # FILTRO OBLIGATORIO: Solo diarios de venta
        domain.append(('journal_id.type', '=', 'sale'))
        
        # Filtro por partner - DIRECTO
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        
        # CAMBIO: Filtro por vendedor usando commission_seller_id
        elif self.commission_seller_id:
            # Buscar todas las facturas del vendedor usando el campo commission_seller_id
            invoices = self.env['account.move'].search([
                ('commission_seller_id', '=', self.commission_seller_id.id),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
                ('state', '!=', 'cancel')
            ])
            partner_ids = invoices.mapped('partner_id.commercial_partner_id').ids
            
            # También incluir los partners hijos
            if partner_ids:
                all_partners = self.env['res.partner'].search([
                    '|',
                    ('id', 'in', partner_ids),
                    ('commercial_partner_id', 'in', partner_ids)
                ])
                domain.append(('partner_id', 'in', all_partners.ids))
            else:
                # Si no hay partners, usar un dominio imposible para no mostrar nada
                domain.append(('id', '=', 0))
        
        # Filtro por fechas
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        
        # Filtro por estado
        if self.state != 'all':
            domain.append(('move_id.state', '=', self.state))
        else:
            # Excluir cancelados por defecto
            domain.append(('move_id.state', '!=', 'cancel'))
        
        # Filtro por conciliación
        if not self.include_reconciled:
            domain.append(('full_reconcile_id', '=', False))
        
        # Excluir líneas que no son de balance (como líneas de impuestos automáticas)
        domain.append(('account_id.account_type', '!=', False))
        
        # Log para debug
        _logger.info(f"Domain generado: {domain}")
        _logger.info(f"Partner ID: {self.partner_id.id if self.partner_id else 'None'}")
        _logger.info(f"Commission Seller ID: {self.commission_seller_id.id if self.commission_seller_id else 'None'}")
        _logger.info(f"Journal Type: FIJO en 'sale'")
        
        return domain
    
    def _get_report_data(self):
        """
        Obtiene los datos para el reporte
        """
        domain = self._get_domain()
        
        # Log para debug
        _logger.info(f"Buscando apuntes con dominio: {domain}")
        
        # Obtener apuntes contables ordenados por fecha
        move_lines = self.env['account.move.line'].search(domain, order='partner_id, date, id')
        
        # SIEMPRE filtrar facturas y pagos con saldo cero cuando está marcada la opción
        # Esto debe hacerse DESPUÉS de obtener las líneas, independientemente del tipo de diario
        if self.exclude_zero_invoices:
            filtered_lines = self.env['account.move.line']
            for line in move_lines:
                move = line.move_id
                # Si es una factura o nota de crédito
                if move.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']:
                    # Solo incluir si tiene saldo pendiente
                    if move.amount_residual != 0:
                        filtered_lines |= line
                # Si es un pago (buscar payment asociado al move)
                else:
                    payment = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                    if payment:
                        # Verificar si el pago tiene algún saldo sin aplicar
                        # Un pago está completamente aplicado si su importe es igual a lo reconciliado
                        if abs(payment.amount - sum(payment.reconciled_invoice_ids.mapped('amount_total'))) > 0.01:
                            filtered_lines |= line
                        # Si el pago está completamente aplicado, NO incluir (porque exclude_zero_invoices está activo)
                    else:
                        # Si no es ni factura ni pago, incluir
                        filtered_lines |= line
            
            move_lines = filtered_lines
        
        _logger.info(f"Líneas encontradas después de filtros: {len(move_lines)}")
        
        if not move_lines:
            raise UserError(_('No se encontraron apuntes contables con los criterios especificados.'))
        
        # Procesar datos
        data = []
        
        if self.group_by_partner:
            # Agrupar por partner
            partners = {}
            for line in move_lines:
                partner_key = line.partner_id.id if line.partner_id else 0
                if partner_key not in partners:
                    partners[partner_key] = {
                        'partner': line.partner_id.name if line.partner_id else 'Sin Partner',
                        'partner_vat': line.partner_id.vat if line.partner_id else '',
                        'lines': [],
                        'total_debit_usd': 0.0,
                        'total_credit_usd': 0.0,
                        'total_balance_usd': 0.0,
                    }
                
                # Obtener información adicional del movimiento
                move = line.move_id
                
                # Tipo de documento
                move_type_map = {
                    'out_invoice': 'FAC',
                    'out_refund': 'NC',
                    'in_invoice': 'FAC-P',
                    'in_refund': 'NC-P',
                    'entry': 'ASIENTO',
                }
                move_type = move_type_map.get(move.move_type, 'OTRO')
                # Verificar si es un pago
                payment = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                if payment:
                    move_type = 'PAGO'
                
                # Estado
                state_map = {
                    'draft': 'Borrador',
                    'posted': 'Confirmado',
                    'cancel': 'Cancelado',
                }
                
                # Días de crédito
                dias_credito = None
                if move.invoice_date and move.invoice_date_due:
                    dias_credito = (move.invoice_date_due - move.invoice_date).days
                
                # CAMBIO: Obtener vendedor usando commission_seller_id
                vendedor_name = ''
                if move.commission_seller_id:
                    vendedor_name = move.commission_seller_id.name
                else:
                    # Buscar si hay un pago asociado
                    payment = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                    if payment and payment.commission_seller_id:
                        vendedor_name = payment.commission_seller_id.name
                
                # Notas internas de la factura
                narration = move.narration if move.narration else ''
                
                # Calcular balance en USD usando campos alternos
                balance_usd = line.debit_alternate - line.credit_alternate
                
                # Determinar signo correcto basado en el tipo de cuenta y movimiento
                amount_signed_usd = balance_usd
                # Buscar si hay un pago asociado al move
                payment_rec = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                
                if self.account_type == 'receivable':
                    # Para cuentas por cobrar: débito es positivo (aumenta deuda), crédito es negativo (pago)
                    if move.move_type == 'out_refund':
                        amount_signed_usd = -abs(balance_usd)  # NC siempre negativa
                    elif payment_rec and payment_rec.payment_type == 'inbound':
                        amount_signed_usd = -abs(balance_usd)  # Pagos recibidos siempre negativos
                    else:
                        amount_signed_usd = abs(balance_usd)  # Facturas siempre positivas
                elif self.account_type == 'payable':
                    # Para cuentas por pagar: crédito es positivo (aumenta deuda), débito es negativo (pago)
                    if move.move_type == 'in_refund':
                        amount_signed_usd = -abs(balance_usd)  # NC siempre negativa
                    elif payment_rec and payment_rec.payment_type == 'outbound':
                        amount_signed_usd = -abs(balance_usd)  # Pagos realizados siempre negativos
                    else:
                        amount_signed_usd = abs(balance_usd)  # Facturas siempre positivas
                
                # Para facturas de proveedor, invertir el signo del balance
                if move.move_type in ['in_invoice', 'in_refund']:
                    amount_signed_usd = -amount_signed_usd
                
                # Convertir amount_residual a USD si la moneda de la factura es diferente
                amount_residual_usd = 0.0
                if hasattr(move, 'amount_residual') and hasattr(move, 'currency_id'):
                    if move.currency_id.name == 'USD':
                        amount_residual_usd = move.amount_residual
                    else:
                        # Convertir de VES a USD usando la tasa del move
                        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                        if usd_currency and move.currency_id:
                            date_to_use = move.invoice_date or move.date or fields.Date.today()
                            amount_residual_usd = move.currency_id._convert(
                                move.amount_residual,
                                usd_currency,
                                move.company_id,
                                date_to_use
                            )
                
                line_data = {
                    'date': line.date,
                    'move_name': move.name,
                    'partner': line.partner_id.name if line.partner_id else '',
                    'partner_vat': line.partner_id.vat if line.partner_id else '',
                    'ref': line.ref or move.ref or '',
                    'name': line.name or '',
                    'account_code': line.account_id.code,
                    'account_name': line.account_id.name,
                    'debit_usd': line.debit_alternate,
                    'credit_usd': line.credit_alternate,
                    'balance_usd': balance_usd,
                    'amount_signed_usd': amount_signed_usd,
                    'currency_rate': line.currency_rate_usd,
                    'reconciled': '✓' if line.full_reconcile_id else '',
                    'state': state_map.get(move.state, move.state),
                    'move_type': move_type,
                    'invoice_date': move.invoice_date,
                    'invoice_date_due': move.invoice_date_due,
                    'invoice_origin': move.invoice_origin or '',
                    'invoice_user': vendedor_name,
                    'payment_ref': payment.name if payment else '',
                    'dias_credito': dias_credito,
                    'narration': narration,
                    'invoice_payment_term': move.invoice_payment_term_id.name if move.invoice_payment_term_id else '',
                    'amount_residual_usd': amount_residual_usd,
                }
                
                partners[partner_key]['lines'].append(line_data)
                partners[partner_key]['total_debit_usd'] += line.debit_alternate
                partners[partner_key]['total_credit_usd'] += line.credit_alternate
                partners[partner_key]['total_balance_usd'] += amount_signed_usd
            
            # Convertir a lista
            data = list(partners.values())
            
            # Ordenar partners por nombre
            data.sort(key=lambda x: x['partner'])
        else:
            # Sin agrupar
            for line in move_lines:
                move = line.move_id
                
                # Tipo de documento
                move_type_map = {
                    'out_invoice': 'FAC',
                    'out_refund': 'NC',
                    'in_invoice': 'FAC-P',
                    'in_refund': 'NC-P',
                    'entry': 'ASIENTO',
                }
                move_type = move_type_map.get(move.move_type, 'OTRO')
                # Verificar si es un pago
                payment = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                if payment:
                    move_type = 'PAGO'
                
                # Estado
                state_map = {
                    'draft': 'Borrador',
                    'posted': 'Confirmado',
                    'cancel': 'Cancelado',
                }
                
                # Días de crédito
                dias_credito = None
                if move.invoice_date and move.invoice_date_due:
                    dias_credito = (move.invoice_date_due - move.invoice_date).days
                
                # CAMBIO: Obtener vendedor usando commission_seller_id
                vendedor_name = ''
                if move.commission_seller_id:
                    vendedor_name = move.commission_seller_id.name
                else:
                    # Buscar si hay un pago asociado
                    payment = self.env['account.payment'].search([('move_id', '=', move.id)], limit=1)
                    if payment and payment.commission_seller_id:
                        vendedor_name = payment.commission_seller_id.name
                
                # Notas internas
                narration = move.narration if move.narration else ''
                
                # Calcular balance en USD
                balance_usd = line.debit_alternate - line.credit_alternate
                
                # Convertir amount_residual a USD
                amount_residual_usd = 0.0
                if hasattr(move, 'amount_residual') and hasattr(move, 'currency_id'):
                    if move.currency_id.name == 'USD':
                        amount_residual_usd = move.amount_residual
                    else:
                        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                        if usd_currency and move.currency_id:
                            date_to_use = move.invoice_date or move.date or fields.Date.today()
                            amount_residual_usd = move.currency_id._convert(
                                move.amount_residual,
                                usd_currency,
                                move.company_id,
                                date_to_use
                            )
                
                data.append({
                    'date': line.date,
                    'move_name': move.name,
                    'partner': line.partner_id.name if line.partner_id else 'Sin Partner',
                    'partner_vat': line.partner_id.vat if line.partner_id else '',
                    'ref': line.ref or move.ref or '',
                    'name': line.name or '',
                    'account_code': line.account_id.code,
                    'account_name': line.account_id.name,
                    'debit_usd': line.debit_alternate,
                    'credit_usd': line.credit_alternate,
                    'balance_usd': balance_usd,
                    'currency_rate': line.currency_rate_usd,
                    'reconciled': '✓' if line.full_reconcile_id else '',
                    'state': state_map.get(move.state, move.state),
                    'move_type': move_type,
                    'invoice_date': move.invoice_date,
                    'invoice_date_due': move.invoice_date_due,
                    'invoice_origin': move.invoice_origin or '',
                    'invoice_user': vendedor_name,
                    'payment_ref': payment.name if payment else '',
                    'dias_credito': dias_credito,
                    'narration': narration,
                    'invoice_payment_term': move.invoice_payment_term_id.name if move.invoice_payment_term_id else '',
                    'amount_residual_usd': amount_residual_usd,
                })
        
        return data
    
    def generate_excel_report(self):
        """
        Genera el reporte en formato Excel con formato profesional
        """
        # Obtener datos
        report_data = self._get_report_data()
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Apuntes Contables')
        
        # Definir formatos
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#F5F5F5',
            'border': 1,
            'text_wrap': True,
            'font_size': 10,
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'bg_color': '#2C3E50',
            'font_color': '#FFFFFF',
        })
        
        info_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#E8E8E8',
        })
        
        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 9,
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 9,
            'num_format': '#,##0.00',
        })
        
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 9,
            'num_format': 'dd/mm/yyyy',
        })
        
        total_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 10,
            'bg_color': '#EFEFEF',
            'num_format': '#,##0.00',
        })
        
        partner_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#E0E0E0',
            'border': 1,
        })
        
        # Escribir título
        worksheet.merge_range('A1:M1', f'REPORTE DE APUNTES CONTABLES - {self.company_id.name}', title_format)
        
        # Información de filtros
        row = 2
        worksheet.merge_range(f'A{row}:D{row}', f'Tipo de Cuenta: {dict(self._fields["account_type"].selection).get(self.account_type)}', info_format)
        
        if self.partner_id:
            row += 1
            worksheet.merge_range(f'A{row}:D{row}', f'Cliente/Proveedor: {self.partner_id.name}', info_format)
        
        # CAMBIO: Mostrar vendedor usando commission_seller_id
        if self.commission_seller_id:
            row += 1
            worksheet.merge_range(f'A{row}:D{row}', f'Vendedor: {self.commission_seller_id.name}', info_format)
        
        periodo = f"Desde {self.date_from.strftime('%d/%m/%Y') if self.date_from else 'Inicio'}"
        periodo += f" hasta {self.date_to.strftime('%d/%m/%Y') if self.date_to else 'Hoy'}"
        row += 1
        worksheet.merge_range(f'A{row}:D{row}', f'Período: {periodo}', info_format)
        
        # Espacio
        row += 2
        
        # Encabezados - Estructura mejorada con columnas agrupadas
        header_row = row
        headers = [
            'Tipo',
            'Asiento',
            'Referencia',
            'Etiqueta',
            'Monto',
            'Saldo',
            'Estado',
            'Saldo Acum.',
            'F. Factura',
            'F. Vencimiento',
            'F. Entrega',
            'Días Créd.',
            'Vendedor',
            'Notas'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(header_row, col, header, header_format)
        
        row += 1
        
        if self.group_by_partner:
            # Reporte agrupado por partner
            grand_total_balance = 0.0
            
            for partner_data in report_data:
                # Encabezado del partner
                worksheet.merge_range(f'A{row}:N{row}', 
                                    f"Partner: {partner_data['partner']} - RIF/CI: {partner_data['partner_vat']}", 
                                    partner_format)
                row += 1
                
                running_balance = 0.0
                for line in partner_data['lines']:
                    running_balance += line['amount_signed_usd']
                    
                    # Escribir datos de la línea
                    worksheet.write(row, 0, line['move_type'], cell_format)
                    worksheet.write(row, 1, line['move_name'], cell_format)
                    worksheet.write(row, 2, line['ref'], cell_format)
                    worksheet.write(row, 3, line['name'][:50] if line['name'] else '', cell_format)
                    worksheet.write(row, 4, line['balance_usd'], number_format)
                    worksheet.write(row, 5, line['amount_residual_usd'], number_format)
                    worksheet.write(row, 6, line['reconciled'] + ' ' + line['state'], cell_format)
                    worksheet.write(row, 7, running_balance, number_format)
                    
                    # Fechas
                    if line['invoice_date']:
                        worksheet.write_datetime(row, 8, line['invoice_date'], date_format)
                    else:
                        worksheet.write(row, 8, '', cell_format)
                    
                    if line['invoice_date_due']:
                        worksheet.write_datetime(row, 9, line['invoice_date_due'], date_format)
                    else:
                        worksheet.write(row, 9, '', cell_format)
                    
                    # Fecha de entrega (invoice_origin podría contener info de orden)
                    worksheet.write(row, 10, line['invoice_origin'], cell_format)
                    
                    # Días de crédito
                    if line['dias_credito'] is not None:
                        worksheet.write(row, 11, line['dias_credito'], cell_format)
                    else:
                        worksheet.write(row, 11, '', cell_format)
                    
                    # Vendedor
                    worksheet.write(row, 12, line['invoice_user'][:25] if line['invoice_user'] else '', cell_format)
                    
                    # Notas (narration)
                    worksheet.write(row, 13, line['narration'][:100] if line['narration'] else '', cell_format)
                    
                    row += 1
                
                # Total del partner
                worksheet.write(row, 0, 'SUBTOTAL', total_format)
                for col in [1, 2, 3]:
                    worksheet.write(row, col, '', total_format)
                worksheet.write(row, 4, partner_data['total_balance_usd'], total_format)
                worksheet.write(row, 5, '', total_format)
                worksheet.write(row, 6, '', total_format)
                worksheet.write(row, 7, running_balance, total_format)
                for col in [8, 9, 10, 11, 12, 13]:
                    worksheet.write(row, col, '', total_format)
                
                grand_total_balance += partner_data['total_balance_usd']
                row += 2
            
            # Gran total
            worksheet.write(row, 0, 'TOTAL GENERAL', total_format)
            for col in [1, 2, 3]:
                worksheet.write(row, col, '', total_format)
            worksheet.write(row, 4, grand_total_balance, total_format)
            worksheet.write(row, 5, '', total_format)
            worksheet.write(row, 6, '', total_format)
            worksheet.write(row, 7, grand_total_balance, total_format)
            for col in [8, 9, 10, 11, 12, 13]:
                worksheet.write(row, col, '', total_format)
        else:
            # Reporte sin agrupar
            running_balance = 0.0
            for line_data in report_data:
                # Calcular balance acumulado en USD
                if self.account_type == 'receivable':
                    # Para cuentas por cobrar
                    if line_data['credit_usd'] > 0:
                        running_balance -= line_data['credit_usd']
                    else:
                        running_balance += line_data['debit_usd']
                else:
                    # Para cuentas por pagar
                    if line_data['debit_usd'] > 0:
                        running_balance -= line_data['debit_usd']
                    else:
                        running_balance += line_data['credit_usd']
                
                # Escribir datos
                worksheet.write(row, 0, line_data['move_type'], cell_format)
                worksheet.write(row, 1, line_data['move_name'], cell_format)
                worksheet.write(row, 2, line_data['ref'], cell_format)
                worksheet.write(row, 3, line_data['name'][:50] if line_data['name'] else '', cell_format)
                worksheet.write(row, 4, line_data['balance_usd'], number_format)
                worksheet.write(row, 5, line_data['amount_residual_usd'], number_format)
                worksheet.write(row, 6, line_data['reconciled'] + ' ' + line_data['state'], cell_format)
                worksheet.write(row, 7, running_balance, number_format)
                
                # Fechas
                if line_data['invoice_date']:
                    worksheet.write_datetime(row, 8, line_data['invoice_date'], date_format)
                else:
                    worksheet.write(row, 8, '', cell_format)
                
                if line_data['invoice_date_due']:
                    worksheet.write_datetime(row, 9, line_data['invoice_date_due'], date_format)
                else:
                    worksheet.write(row, 9, '', cell_format)
                
                # Fecha de entrega
                worksheet.write(row, 10, line_data['invoice_origin'], cell_format)
                
                # Días de crédito
                if line_data['dias_credito'] is not None:
                    worksheet.write(row, 11, line_data['dias_credito'], cell_format)
                else:
                    worksheet.write(row, 11, '', cell_format)
                
                # Vendedor
                worksheet.write(row, 12, line_data['invoice_user'][:25] if line_data['invoice_user'] else '', cell_format)
                
                # Notas
                worksheet.write(row, 13, line_data['narration'][:100] if line_data['narration'] else '', cell_format)
                
                row += 1
            
            # Total final sin agrupar
            worksheet.write(row, 3, 'TOTAL', total_format)
            worksheet.write(row, 4, '', total_format)
            worksheet.write(row, 5, '', total_format)
            worksheet.write(row, 6, '', total_format)
            worksheet.write(row, 7, running_balance, total_format)
            for col in [0, 1, 2, 3, 4, 8, 9]:
                worksheet.write(row, col, '', total_format)
        
        # Ajustar ancho de columnas
        worksheet.set_column('A:A', 8)   # Tipo
        worksheet.set_column('B:B', 15)  # Asiento
        worksheet.set_column('C:C', 15)  # Referencia
        worksheet.set_column('D:D', 30)  # Etiqueta
        worksheet.set_column('E:E', 15)  # Monto
        worksheet.set_column('F:F', 15)  # Saldo
        worksheet.set_column('G:G', 12)  # Estado
        worksheet.set_column('H:J', 12)  # Fechas agrupadas (Factura, Vencimiento, Entrega)
        worksheet.set_column('K:K', 10)  # Días crédito
        worksheet.set_column('L:L', 20)  # Vendedor
        worksheet.set_column('M:M', 40)  # Notas
        
        workbook.close()
        output.seek(0)
        
        # Guardar el archivo con nombre más descriptivo
        account_type_name = dict(self._fields["account_type"].selection).get(self.account_type, 'Todas')
        self.report_file = base64.b64encode(output.read())
        self.report_filename = f"Apuntes_{account_type_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.entries.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
    
    def generate_pdf_report(self):
        """
        Genera el reporte en formato PDF
        """
        # CAMBIO: Usar el sistema de reportes de Odoo directamente
        # En lugar de html2pdf que no existe en Odoo 18
        
        # Obtener datos
        report_data = self._get_report_data()
        
        # Generar HTML content
        html_content = self._generate_html_report(report_data)
        
        # Usar el método base64 directamente para simplificar
        # Ya que html2pdf no existe en Odoo 18, guardamos como HTML
        # El usuario puede imprimir desde el navegador o convertir con herramientas externas
        
        # Nombre del archivo más descriptivo
        account_type_name = dict(self._fields["account_type"].selection).get(self.account_type, 'Todas')
        self.report_file = base64.b64encode(html_content.encode('utf-8'))
        self.report_filename = f"Apuntes_{account_type_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        # Notificar al usuario que el archivo es HTML
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.entries.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_message': 'El reporte se ha generado en formato HTML. Puede abrirlo en su navegador e imprimirlo como PDF desde ahí.'
            }
        }
    
    def _generate_html_report(self, report_data):
        """
        Genera el HTML para el reporte PDF
        """
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 10pt; }
                h1 { text-align: center; color: #2C3E50; }
                .header-info { margin-bottom: 20px; background: #f5f5f5; padding: 10px; border-radius: 5px; }
                .header-info p { margin: 5px 0; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                th { background-color: #F5F5F5; color: #333; padding: 8px; text-align: left; border: 1px solid #ddd; font-size: 9pt; }
                td { padding: 6px; border: 1px solid #E8E8E8; font-size: 9pt; }
                tr:nth-child(even) { background-color: #FAFAFA; }
                .text-right { text-align: right; }
                .text-center { text-align: center; }
                .total-row { background-color: #EFEFEF; font-weight: bold; }
                .negative { color: #d9534f; }
                .partner-header { background-color: #E0E0E0; font-weight: bold; margin-top: 20px; }
                .page-break { page-break-after: always; }
                @page { size: landscape; margin: 1cm; }
            </style>
        </head>
        <body>
        """
        
        # Título
        html += f"<h1>REPORTE DE APUNTES CONTABLES (USD) - {self.company_id.name}</h1>"
        
        # Información de filtros
        html += '<div class="header-info">'
        html += f'<p><strong>Tipo de Cuenta:</strong> {dict(self._fields["account_type"].selection).get(self.account_type)}</p>'
        if self.partner_id:
            html += f'<p><strong>Cliente/Proveedor:</strong> {self.partner_id.name}</p>'
        # CAMBIO: Mostrar vendedor usando commission_seller_id
        if self.commission_seller_id:
            html += f'<p><strong>Vendedor:</strong> {self.commission_seller_id.name}</p>'
        
        periodo = f"Desde {self.date_from.strftime('%d/%m/%Y') if self.date_from else 'Inicio'}"
        periodo += f" hasta {self.date_to.strftime('%d/%m/%Y') if self.date_to else 'Hoy'}"
        html += f'<p><strong>Período:</strong> {periodo}</p>'
        html += '</div>'
        
        if self.group_by_partner:
            # Reporte agrupado
            for partner_data in report_data:
                html += f'<div class="partner-header">Partner: {partner_data["partner"]} - RIF/CI: {partner_data["partner_vat"]}</div>'
                html += """
                <table>
                <thead>
                <tr>
                    <th>Tipo</th>
                    <th>Asiento</th>
                    <th>Referencia</th>
                    <th>Etiqueta</th>
                    <th class="text-right">Monto USD</th>
                    <th class="text-right">Saldo USD</th>
                    <th>Estado</th>
                    <th>F. Factura</th>
                    <th>F. Venc.</th>
                    <th>Días Cr.</th>
                    <th>Vendedor</th>
                </tr>
                </thead>
                <tbody>
                """
                
                running_balance = 0.0
                for line in partner_data['lines']:
                    running_balance += line['amount_signed_usd']
                    
                    # Clase para montos negativos
                    monto_class = 'negative' if line['balance_usd'] < 0 else ''
                    
                    # Formatear fecha
                    fecha = line['invoice_date'] if line['invoice_date'] else line['date']
                    fecha_str = fecha.strftime('%d/%m/%Y') if fecha else ''
                    fecha_venc = line['invoice_date_due'].strftime('%d/%m/%Y') if line['invoice_date_due'] else ''
                    
                    html += f"""
                    <tr>
                        <td class="text-center">{line['move_type']}</td>
                        <td>{line['move_name']}</td>
                        <td>{line['ref']}</td>
                        <td>{line['name'][:40]}</td>
                        <td class="text-right {monto_class}">${line['balance_usd']:,.2f}</td>
                        <td class="text-right">${running_balance:,.2f}</td>
                        <td>{line['state']}</td>
                        <td>{fecha_str}</td>
                        <td>{fecha_venc}</td>
                        <td class="text-center">{line['dias_credito'] or ''}</td>
                        <td>{line['invoice_user'][:20] if line['invoice_user'] else ''}</td>
                    </tr>
                    """
                
                # Total del partner
                html += f"""
                <tr class="total-row">
                    <td colspan="4" class="text-right">TOTAL</td>
                    <td class="text-right">${partner_data['total_balance_usd']:,.2f}</td>
                    <td class="text-right">${running_balance:,.2f}</td>
                    <td colspan="5"></td>
                </tr>
                """
                html += '</tbody></table><br/>'
        
        html += '</body></html>'
        return html
    
    def action_generate_report(self):
        """
        Acción principal para generar el reporte
        """
        if self.output_format == 'excel':
            return self.generate_excel_report()
        elif self.output_format == 'pdf':
            return self.generate_pdf_report()
        else:
            raise UserError(_('Formato no soportado.'))
        
    def action_print_report(self):
        """
        Acción para imprimir/descargar el reporte
        """
        if not self.report_file:
            raise UserError(_('Primero debe generar el reporte.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/report_file/{self.report_filename}?download=true',
            'target': 'self',
        }