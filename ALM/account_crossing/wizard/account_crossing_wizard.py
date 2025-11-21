# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountCrossingWizard(models.TransientModel):
    _name = 'account.crossing.wizard'
    _description = 'Wizard de Cruce Contable'

    crossing_date = fields.Date(
        string='Fecha de Cruce',
        required=True,
        default=fields.Date.context_today,
        help='Fecha en la que se registrará el cruce contable'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        readonly=True,
        default=lambda self: self.env.user
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        readonly=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True,
        related='move_id.currency_id',
        store=True
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Base',
        related='company_id.currency_id',
        readonly=True
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        readonly=True,
        domain="[('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']), "
               "('state', '=', 'posted'), ('payment_state', '!=', 'paid')]"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        related='move_id.partner_id',
        readonly=True
    )
    move_type = fields.Selection(
        related='move_id.move_type',
        string='Tipo de Documento',
        readonly=True
    )
    invoice_date = fields.Date(
        related='move_id.invoice_date',
        string='Fecha Factura',
        readonly=True
    )
    amount_total = fields.Monetary(
        string='Monto Total',
        related='move_id.amount_total',
        readonly=True
    )
    amount_residual = fields.Monetary(
        string='Monto Pendiente',
        related='move_id.amount_residual',
        readonly=True
    )
    crossing_reason_id = fields.Many2one(
        'account.crossing.reason',
        string='Motivo de Cruce',
        required=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help='Seleccione el motivo del cruce contable'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        related='crossing_reason_id.journal_id',
        readonly=True,
        help='Diario donde se registrará el asiento de cruce'
    )
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta Contable',
        related='crossing_reason_id.account_id',
        readonly=True,
        help='Cuenta contable contra la cual se realizará el cruce'
    )
    amount = fields.Monetary(
        string='Monto a Cruzar',
        required=True,
        help='Monto que se cruzará en esta operación'
    )
    commission_seller_id = fields.Many2one(
        'res.partner',
        string='Vendedor CS',
        domain=[('is_commission_seller', '=', True)],
        help='Vendedor responsable que recibirá comisión por este cruce'
    )
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre este cruce'
    )
    # Campos informativos de saldo
    show_account_balance = fields.Boolean(
        string='Mostrar Saldo de Cuenta',
        compute='_compute_account_balance',
        help='Indica si se debe mostrar el saldo de la cuenta'
    )
    account_balance = fields.Monetary(
        string='Saldo Disponible en Cuenta',
        compute='_compute_account_balance',
        currency_field='currency_id',
        help='Saldo disponible en la cuenta del motivo de cruce para este contacto en moneda de la factura'
    )
    account_balance_company = fields.Monetary(
        string='Saldo en Moneda Base',
        compute='_compute_account_balance',
        currency_field='company_currency_id',
        help='Saldo en moneda base de la compañía (VES) con tasas históricas'
    )
    show_dual_currency = fields.Boolean(
        string='Mostrar Ambas Monedas',
        compute='_compute_account_balance',
        help='Indica si se debe mostrar el saldo en ambas monedas'
    )
    account_balance_info = fields.Char(
        string='Info Saldo',
        compute='_compute_account_balance'
    )
    # Campos informativos
    show_partial_warning = fields.Boolean(
        compute='_compute_show_warnings'
    )
    show_excess_warning = fields.Boolean(
        compute='_compute_show_warnings'
    )

    @api.depends('amount', 'amount_residual')
    def _compute_show_warnings(self):
        for wizard in self:
            residual = abs(wizard.amount_residual) if wizard.amount_residual else 0.0
            wizard.show_partial_warning = wizard.amount > 0 and wizard.amount < residual
            wizard.show_excess_warning = wizard.amount > residual

    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('El monto a cruzar debe ser mayor a cero.'))
            
            residual = abs(wizard.amount_residual)
            if wizard.amount > residual:
                raise ValidationError(_(
                    'El monto a cruzar (%(amount)s) no puede ser mayor al monto pendiente (%(residual)s).',
                    amount=wizard.amount,
                    residual=residual
                ))

    @api.constrains('crossing_date')
    def _check_crossing_date(self):
        for wizard in self:
            if wizard.crossing_date > fields.Date.today():
                raise ValidationError(_('La fecha de cruce no puede ser futura.'))
            
            # Validar período contable
            date = wizard.crossing_date
            company = wizard.company_id
            if company.fiscalyear_lock_date and date <= company.fiscalyear_lock_date:
                raise ValidationError(_(
                    'La fecha de cruce está en un período cerrado. '
                    'Por favor seleccione una fecha posterior a %s.'
                ) % company.fiscalyear_lock_date)

    @api.depends('crossing_reason_id', 'partner_id', 'company_id', 'currency_id')
    def _compute_account_balance(self):
        """Calcula el saldo disponible en la cuenta del motivo de cruce para el contacto
        
        En entornos multimoneda:
        - Filtra líneas por la moneda de la factura
        - Calcula saldo en moneda extranjera (amount_currency)
        - Calcula saldo en moneda base (balance con tasas históricas)
        """
        for wizard in self:
            wizard.show_account_balance = False
            wizard.account_balance = 0.0
            wizard.account_balance_company = 0.0
            wizard.show_dual_currency = False
            wizard.account_balance_info = ''
            
            if not wizard.crossing_reason_id or not wizard.partner_id:
                continue
            
            account = wizard.crossing_reason_id.account_id
            partner = wizard.partner_id
            currency = wizard.currency_id
            company_currency = wizard.company_currency_id
            
            # Dominio base para líneas contables
            domain = [
                ('account_id', '=', account.id),
                ('partner_id', '=', partner.id),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', wizard.company_id.id),
            ]
            
            # Obtener todas las líneas de la cuenta para este partner
            all_lines = self.env['account.move.line'].search(domain)
            
            if not all_lines:
                continue
            
            # Determinar si es multimoneda
            is_foreign_currency = currency != company_currency
            
            if is_foreign_currency:
                # Filtrar líneas en la moneda de la factura
                foreign_lines = all_lines.filtered(lambda l: l.currency_id == currency)
                
                if foreign_lines:
                    # Saldo en moneda extranjera (amount_currency ya tiene el signo correcto)
                    balance_foreign = sum(foreign_lines.mapped('amount_currency'))
                    # Saldo en moneda base (balance con tasas históricas)
                    balance_company = sum(foreign_lines.mapped('balance'))
                    
                    # Aplicar inversión de signo si está configurado
                    if wizard.crossing_reason_id.invert_balance_sign:
                        balance_foreign = -balance_foreign
                        balance_company = -balance_company
                    
                    wizard.show_account_balance = True
                    wizard.show_dual_currency = True
                    wizard.account_balance = balance_foreign
                    wizard.account_balance_company = balance_company
                    
                    # Generar información
                    if balance_foreign > 0:
                        wizard.account_balance_info = _('Saldo disponible')
                    elif balance_foreign < 0:
                        wizard.account_balance_info = _('Saldo negativo (sobregiro)')
                    else:
                        wizard.account_balance_info = _('Saldo en cero')
                else:
                    # No hay movimientos en esta moneda extranjera
                    wizard.show_account_balance = False
            else:
                # Moneda base solamente
                balance = sum(all_lines.mapped('balance'))
                
                # Aplicar inversión de signo si está configurado
                if wizard.crossing_reason_id.invert_balance_sign:
                    balance = -balance
                
                wizard.show_account_balance = True
                wizard.show_dual_currency = False
                wizard.account_balance = balance
                wizard.account_balance_company = balance
                
                # Generar información
                if balance > 0:
                    wizard.account_balance_info = _('Saldo disponible')
                elif balance < 0:
                    wizard.account_balance_info = _('Saldo negativo (sobregiro)')
                else:
                    wizard.account_balance_info = _('Saldo en cero')

    @api.onchange('crossing_reason_id')
    def _onchange_crossing_reason(self):
        """Actualiza información cuando cambia el motivo"""
        if self.crossing_reason_id and self.crossing_reason_id.company_id != self.company_id:
            self.crossing_reason_id = False
            return {
                'warning': {
                    'title': _('Advertencia'),
                    'message': _('El motivo seleccionado no pertenece a la compañía actual.')
                }
            }
        
        # Recalcular el saldo de la cuenta
        self._compute_account_balance()
    
    @api.onchange('move_id')
    def _onchange_move_commission_seller(self):
        """Hereda el vendedor de la factura si está disponible"""
        if self.move_id and hasattr(self.move_id, 'commission_seller_id'):
            self.commission_seller_id = self.move_id.commission_seller_id

    def action_create_crossing(self):
        """Crea el cruce contable"""
        self.ensure_one()
        
        # Validaciones finales
        if not self.crossing_reason_id:
            raise UserError(_('Debe seleccionar un motivo de cruce.'))
        
        if self.move_id.payment_state == 'paid':
            raise UserError(_('La factura ya fue pagada completamente.'))
        
        # Crear el cruce
        crossing_vals = {
            'crossing_date': self.crossing_date,
            'user_id': self.user_id.id,
            'company_id': self.company_id.id,
            'move_id': self.move_id.id,
            'crossing_reason_id': self.crossing_reason_id.id,
            'amount': self.amount,
            'commission_seller_id': self.commission_seller_id.id if self.commission_seller_id else False,
            'notes': self.notes,
            'state': 'draft',
        }
        
        crossing = self.env['account.crossing'].create(crossing_vals)
        
        # Confirmar automáticamente si está configurado
        if self.env.company.crossing_auto_post:
            crossing.action_post()
        
        # Mensaje en el chatter de la factura
        self.move_id.message_post(
            body=_('Cruce contable registrado: %(reason)s por %(amount)s %(currency)s',
                   reason=self.crossing_reason_id.display_name,
                   amount=self.amount,
                   currency=self.currency_id.symbol)
        )
        
        # Retornar acción para ver el cruce creado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.crossing',
            'res_id': crossing.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_and_new(self):
        """Crea el cruce y abre un nuevo wizard"""
        self.action_create_crossing()
        
        # Recargar la factura para actualizar montos
        self.move_id.invalidate_recordset(['amount_residual', 'payment_state'])
        
        if self.move_id.payment_state != 'paid':
            # Abrir nuevo wizard si aún hay saldo pendiente
            return self.move_id.action_register_crossing()
        
        return {'type': 'ir.actions.act_window_close'}


class ResCompany(models.Model):
    _inherit = 'res.company'

    crossing_auto_post = fields.Boolean(
        string='Confirmar Cruces Automáticamente',
        default=False,
        help='Si está activado, los cruces se confirmarán automáticamente al crearlos'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crossing_auto_post = fields.Boolean(
        related='company_id.crossing_auto_post',
        readonly=False,
        string='Confirmar Cruces Automáticamente'
    )