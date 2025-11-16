# ClauSyn - Hotel Reservation System

## Project Overview

**ClauSyn** is an Odoo 17 module for hotel reservation management developed by Almus Dev (JDV-ALM). This module serves as the base system for managing the complete lifecycle of hotel reservations, including guest check-ins, consumption tracking, advance payments, and integrated accounting.

- **Module Name**: `hotel_reservation_base`
- **Version**: 17.0.1.0.0
- **Category**: Hotel
- **License**: LGPL-3
- **Developer**: Almus Dev (JDV-ALM)
- **Website**: https://www.almus.dev

### Core Features

- Complete reservation lifecycle management (draft → confirmed → checked in → checked out → invoiced)
- Manual charge recording (cargos manuales)
- Advance payment tracking (anticipos)
- Automatic balance calculation
- Integration with Point of Sale (POS) for guest consumption tracking
- Integration with accounting module (account.payment)
- Multi-currency support with automatic conversion
- Support for price lists and product catalogs

---

## Codebase Structure

```
ClauSyn/
├── README.md                              # Basic project information
├── CLAUDE.md                              # This file - AI assistant guide
└── hotel_reservation_base/                # Main Odoo module
    ├── __init__.py                        # Module initialization
    ├── __manifest__.py                    # Module manifest/metadata
    ├── data/
    │   └── sequence_data.xml              # Reservation number sequences
    ├── models/                            # Business logic models
    │   ├── __init__.py                    # Models initialization
    │   ├── hotel_reservation.py           # Main reservation model
    │   ├── hotel_reservation_line.py      # Manual charges/consumption lines
    │   ├── hotel_reservation_payment.py   # Advance payments
    │   ├── account_payment.py             # Accounting integration
    │   └── res_config_settings.py         # Configuration settings
    ├── security/
    │   ├── security.xml                   # User groups and categories
    │   └── ir.model.access.csv            # Model access rights
    ├── static/
    │   └── description/
    │       └── icon.png                   # Module icon
    ├── views/                             # UI definitions
    │   ├── hotel_reservation_views.xml    # Main reservation views
    │   ├── hotel_reservation_line_views.xml
    │   ├── hotel_reservation_payment_views.xml
    │   ├── res_config_settings_views.xml
    │   └── menuitems.xml                  # Menu structure
    └── wizards/                           # Transient models for dialogs
        ├── __init__.py
        ├── hotel_payment_wizard.py        # Payment registration wizard
        └── hotel_payment_wizard_views.xml
```

### Module Dependencies

The module depends on these Odoo core modules:
- `base` - Core functionality
- `product` - Product/service catalog
- `account` - Accounting and payments
- `sale_management` - Sales management
- `point_of_sale` - POS integration

---

## Key Models and Their Relationships

### 1. `hotel.reservation` (Main Model)
The central container for all guest activities during their stay.

**Key Fields:**
- `name`: Auto-generated reservation number (RESV-YYYY-NNNN)
- `partner_id`: Customer (res.partner)
- `room_id`: Room product
- `room_number`: Physical room identifier
- `checkin_date`, `checkout_date`: Planned dates
- `checkin_real`, `checkout_real`: Actual dates
- `state`: Workflow state (draft/confirmed/checked_in/checked_out/done/cancelled)

**Relationships:**
- `line_ids`: One2many → hotel.reservation.line (manual charges)
- `payment_ids`: One2many → hotel.reservation.payment (advance payments)
- `pos_order_ids`: One2many → pos.order (POS consumption)

**Computed Fields:**
- `room_subtotal`: Room cost (nights × room price)
- `charges_subtotal`: Sum of manual charges
- `pos_charges_subtotal`: Sum of POS orders
- `amount_total`: Total amount due
- `total_paid`: Total advance payments
- `balance`: Remaining balance

### 2. `hotel.reservation.line`
Represents manual charges added to a reservation.

**Key Features:**
- Multi-currency support with stored exchange rates
- Tax calculation
- Product catalog integration
- Price list support
- State validation (can only modify in draft/confirmed/checked_in states)

### 3. `hotel.reservation.payment`
Advance payments (anticipos) applied to a reservation.

**Key Features:**
- Creates `account.payment` records automatically
- Multi-currency with conversion to reservation currency
- Journal and payment method tracking
- Integration with POS payment methods

### 4. Workflow States

```
draft → confirmed → checked_in → checked_out → done
   ↓                                              ↑
   └──────────────→ cancelled ←──────────────────┘
```

**State Transitions:**
- `draft → confirmed`: `action_confirm()` - Validates dates
- `confirmed → checked_in`: `action_check_in()` - Records actual check-in time
- `checked_in → checked_out`: `action_check_out()` - Records actual check-out time
- `checked_out → done`: `action_done()` - Validates balance is paid
- `any → cancelled`: `action_cancel()` - Only if no payments exist

---

## Development Conventions

### 1. File Headers
All Python and XML files must include the standard header:

```python
# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev
```

```xml
<!-- Desarrollado por Almus Dev (JDV-ALM) - www.almus.dev -->
```

### 2. Odoo ORM Patterns

**Model Inheritance:**
```python
class HotelReservation(models.Model):
    _name = 'hotel.reservation'
    _description = 'Reserva de Hotel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkin_date desc, id desc'
```

**Field Definitions:**
```python
# Always include string, help text, and tracking for important fields
partner_id = fields.Many2one(
    'res.partner',
    string='Cliente',
    required=True,
    tracking=True,
    help='Cliente responsable de la reserva'
)
```

**Computed Fields:**
```python
@api.depends('line_ids.subtotal', 'payment_ids.amount')
def _compute_amounts(self):
    for record in self:
        # Always use self iteration for computed fields
        record.amount_total = sum(line.subtotal for line in record.line_ids)
```

**Constraints:**
```python
@api.constrains('checkin_date', 'checkout_date')
def _check_dates(self):
    for reservation in self:
        if reservation.checkin_date >= reservation.checkout_date:
            raise ValidationError(_('La fecha de checkout debe ser posterior al checkin'))
```

### 3. Security Model

**Access Rights** (`ir.model.access.csv`):
- All models grant full CRUD access to `base.group_user`
- Format: `access_model_name_group,model_name.group,model_id,group_id,read,write,create,unlink`

**Security Groups** (`security/security.xml`):
- `group_hotel_user`: Basic hotel user access
- `group_hotel_manager`: Full access (implies hotel_user)

### 4. XML View Conventions

**Form Views:**
```xml
<form string="Reserva de Hotel">
    <header>
        <!-- State transition buttons with attrs for visibility -->
        <button name="action_confirm"
                string="Confirmar"
                type="object"
                class="btn-primary"
                attrs="{'invisible': [('state', '!=', 'draft')]}"/>
        <field name="state" widget="statusbar" statusbar_visible="draft,confirmed,checked_in,done"/>
    </header>
    <sheet>
        <div class="oe_button_box" name="button_box">
            <!-- Smart buttons -->
        </div>
        <div class="oe_title">
            <!-- Record title -->
        </div>
        <group>
            <!-- Fields in grouped columns -->
        </group>
        <notebook>
            <!-- Related data in tabs -->
        </notebook>
    </sheet>
</form>
```

**Tree Views:**
```xml
<tree editable="bottom">
    <!-- Use editable="bottom" or "top" for inline editing -->
    <field name="product_id" options="{'no_create': True}"/>
    <field name="subtotal" sum="Total"/>
</tree>
```

### 5. Naming Conventions

**Models:**
- Use dot notation: `hotel.reservation`, `hotel.reservation.line`
- Description in Spanish: `'Reserva de Hotel'`

**Fields:**
- Snake_case: `checkin_date`, `room_number`
- Related fields end with `_id` (Many2one) or `_ids` (Many2many/One2many)
- String labels in Spanish

**Methods:**
- Action methods: `action_confirm()`, `action_check_in()`
- Compute methods: `_compute_amounts()`, `_compute_room_type()`
- Onchange methods: `_onchange_product_id()`
- Constraint methods: `_check_dates()`, `_check_quantity()`

### 6. Translation
- Use `_()` for all user-facing strings: `_('Reserva confirmada')`
- Error messages always wrapped in `_()`
- Field strings are automatically translatable

---

## Common Development Tasks

### Adding a New Field

1. **Add to model** (`models/hotel_reservation.py`):
```python
new_field = fields.Char(
    string='New Field',
    help='Description of what this field does',
    tracking=True  # If you want to track changes
)
```

2. **Add to view** (`views/hotel_reservation_views.xml`):
```xml
<field name="new_field"/>
```

3. **Update manifest version** if needed (`__manifest__.py`):
```python
'version': '17.0.1.0.1',  # Increment last digit for minor changes
```

### Adding a New Model

1. **Create model file** (`models/new_model.py`):
```python
# -*- coding: utf-8 -*-
# Desarrollado por Almus Dev (JDV-ALM)
# www.almus.dev

from odoo import models, fields, api, _

class NewModel(models.Model):
    _name = 'hotel.new.model'
    _description = 'Description'

    name = fields.Char(string='Name', required=True)
```

2. **Import in `models/__init__.py`**:
```python
from . import new_model
```

3. **Add security** (`security/ir.model.access.csv`):
```csv
access_hotel_new_model_user,hotel.new.model.user,model_hotel_new_model,base.group_user,1,1,1,1
```

4. **Create views** (`views/new_model_views.xml`)

5. **Add to manifest** (`__manifest__.py`):
```python
'data': [
    ...
    'views/new_model_views.xml',
],
```

### Adding a State Transition

1. **Add state to selection** if not exists
2. **Create action method**:
```python
def action_new_state(self):
    """Descriptive docstring"""
    for record in self:
        # Validations
        if record.state != 'expected_state':
            raise UserError(_('Error message'))

        # State change
        record.state = 'new_state'
        record.message_post(body=_('State changed'))
```

3. **Add button to view**:
```xml
<button name="action_new_state"
        string="New State"
        type="object"
        class="btn-primary"
        attrs="{'invisible': [('state', '!=', 'expected_state')]}"/>
```

### Multi-Currency Implementation

This module uses a sophisticated multi-currency approach:

1. **Each reservation has a base currency** (`currency_id`)
2. **Charges can be in different currencies** (`price_currency_id`)
3. **Exchange rates are stored** at the time of transaction (`currency_rate`)
4. **Automatic conversion** happens in computed fields

**Example from `hotel.reservation.line`:**
```python
@api.depends('price_currency_id', 'currency_id', 'date')
def _compute_currency_rate(self):
    for line in self:
        if line.price_currency_id != line.currency_id:
            line.currency_rate = line.price_currency_id._get_conversion_rate(
                line.price_currency_id,
                line.currency_id,
                line.company_id,
                line.date
            )
```

---

## Git Workflow

### Commit Message Convention

Based on recent commits, use descriptive Spanish messages:

**Format:**
```
Verb + description. Explain what changed and why in detail.
```

**Examples:**
- "Actualizar modelo HotelReservation con nuevos campos y mejoras en la lógica de cálculo..."
- "Agregar vista del asistente de pago de hotel en el manifiesto..."
- "Add access to hotel_reservation_base" (English also acceptable)

**Best Practices:**
1. Start with action verb (Actualizar, Agregar, Corregir, Implementar)
2. Include affected components
3. Explain the "why" not just the "what"
4. Break large changes into multiple commits

### Branch Strategy

- Development happens on feature branches
- Branch naming: `claude/descriptive-name-session-id`
- Always push to the correct branch
- Use `git push -u origin <branch-name>`

---

## Testing Guidelines

### Manual Testing Checklist

When modifying the reservation workflow:

1. **State Transitions:**
   - [ ] Can create draft reservation
   - [ ] Can confirm with valid dates
   - [ ] Can't confirm with invalid dates (checkout <= checkin)
   - [ ] Can check-in only from confirmed
   - [ ] Can check-out only from checked_in
   - [ ] Can't mark done with pending balance
   - [ ] Can cancel only if no payments exist

2. **Financial Calculations:**
   - [ ] Room subtotal calculates correctly (nights × price)
   - [ ] Manual charges sum correctly
   - [ ] POS orders sum correctly
   - [ ] Total = room + charges + pos
   - [ ] Balance = total - payments
   - [ ] Multi-currency conversion works

3. **Validations:**
   - [ ] Can't delete confirmed reservations
   - [ ] Can't add charges to done/cancelled reservations
   - [ ] Quantity must be > 0
   - [ ] Price can't be negative
   - [ ] Advance payment creates account.payment

### Unit Test Template (Future)

```python
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError

class TestHotelReservation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Reservation = self.env['hotel.reservation']
        self.partner = self.env.ref('base.res_partner_1')

    def test_date_validation(self):
        """Test that checkout must be after checkin"""
        with self.assertRaises(ValidationError):
            self.Reservation.create({
                'partner_id': self.partner.id,
                'room_number': '101',
                'checkin_date': '2025-01-15',
                'checkout_date': '2025-01-14',  # Invalid!
            })
```

---

## Important Notes for AI Assistants

### When Modifying This Codebase

1. **Always Preserve Headers**
   - Never remove the developer attribution header
   - Keep the encoding declaration

2. **Respect State Management**
   - Don't bypass state validations
   - Always check state before allowing operations
   - Use `self.ensure_one()` when expecting single record

3. **Multi-Currency Awareness**
   - Never assume all amounts are in the same currency
   - Always specify `currency_field` for Monetary fields
   - Store exchange rates when recording transactions

4. **Follow Odoo Best Practices**
   - Use `@api.depends()` for computed fields
   - Use `@api.constrains()` for validations
   - Use `@api.onchange()` for UI behavior only
   - Never use `sudo()` unless absolutely necessary
   - Always iterate over `self` in multi-record methods

5. **Security Considerations**
   - Check record rules and access rights
   - Validate user permissions before state changes
   - Don't expose sensitive data in error messages

6. **Error Messages**
   - Always use `_()` for translation
   - Be specific about what went wrong
   - Suggest how to fix the issue

7. **Performance**
   - Avoid N+1 queries (use prefetch or read_group)
   - Store computed fields when frequently accessed
   - Use SQL views for complex reporting (future)

8. **Integration Points**
   - `pos.order` links via `hotel_reservation_id` (requires pos_hotel_integration module)
   - `account.payment` created automatically from `hotel.reservation.payment`
   - Price lists affect charge pricing

### Common Pitfalls to Avoid

1. **Don't** modify reservation amounts in done/cancelled state
2. **Don't** delete records with related data without checking `ondelete` cascade
3. **Don't** forget to update `store=True` when changing compute dependencies
4. **Don't** use hardcoded IDs - use `self.env.ref()` for XML IDs
5. **Don't** mix languages in user-facing text (stick to Spanish)

### Module Extension Pattern

Future modules should extend this base:

```python
class HotelReservation(models.Model):
    _inherit = 'hotel.reservation'

    # Add fields or override methods
    new_feature = fields.Boolean(string='New Feature')

    def action_check_out(self):
        # Extend existing behavior
        result = super().action_check_out()
        # Additional logic here
        return result
```

---

## Configuration Settings

The module supports configuration via Settings > Hotel:

- Advance payment account configuration
- Default journals for payments
- Integration with other modules (POS, accounting)

See `models/res_config_settings.py` for available options.

---

## Sequence Configuration

Reservation numbers follow the pattern: `RESV-YYYY-NNNN`

- Prefix: `RESV-%(year)s-`
- Padding: 4 digits
- Code: `hotel.reservation`
- Defined in: `data/sequence_data.xml`

---

## Future Development Areas

Based on code comments and structure:

1. **POS Integration** (`pos_hotel_integration` module)
   - Link POS orders to reservations
   - Charge room from POS

2. **Sales Bridge** (`hotel_sale_bridge` module)
   - Checkout wizard to create invoices
   - Integration with sale.order

3. **Room Management**
   - Room availability calendar
   - Room type categorization (partially implemented via `room_type_id`)

4. **Reporting**
   - Occupancy reports
   - Revenue reports
   - Guest history

---

## Quick Reference

### Essential Commands

```bash
# Odoo development server
./odoo-bin -c odoo.conf -u hotel_reservation_base -d database_name

# Check module manifest
cat hotel_reservation_base/__manifest__.py

# View model structure
grep "class.*models.Model" hotel_reservation_base/models/*.py
```

### Key Files to Check First

1. `__manifest__.py` - Module dependencies and data files
2. `models/hotel_reservation.py` - Core business logic
3. `views/hotel_reservation_views.xml` - UI structure
4. `security/ir.model.access.csv` - Permissions

### Useful Odoo ORM Methods

```python
# Search
reservations = self.env['hotel.reservation'].search([('state', '=', 'draft')])

# Browse (by ID)
reservation = self.env['hotel.reservation'].browse(id)

# Create
reservation = self.env['hotel.reservation'].create({...})

# Write
reservation.write({'state': 'confirmed'})

# Unlink
reservation.unlink()

# Access environment
user = self.env.user
company = self.env.company
context = self.env.context
```

---

## Support and Resources

- **Developer**: Almus Dev (JDV-ALM)
- **Website**: https://www.almus.dev
- **Odoo Documentation**: https://www.odoo.com/documentation/17.0/
- **Repository**: ClauSyn (current repository)

---

## Version History

- **17.0.1.0.0** - Initial release
  - Complete reservation lifecycle
  - Multi-currency support
  - POS integration preparation
  - Advance payments with accounting integration

---

*Last Updated: 2025-11-16*
*This document is maintained for AI assistants working on the ClauSyn codebase.*
