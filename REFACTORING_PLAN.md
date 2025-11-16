# Plan de Refactorización - hotel_reservation_base
*Alineación con el concepto de Suite Modular*

## Objetivo
Simplificar hotel_reservation_base para que sea SOLO un "Gestor de Folios", eliminando funcionalidades que corresponden a otros módulos de la suite.

---

## 1. MENÚS - Eliminar Duplicados

### Archivos a Modificar:

#### ❌ ELIMINAR completamente de `hotel_reservation_views.xml`:
```xml
<!-- Líneas 227-289 - TODO EL BLOQUE DE MENÚS -->
<menuitem id="menu_hotel_root"...
<menuitem id="menu_hotel_reservation"...
<menuitem id="menu_hotel_reservation_all"...
<record id="action_hotel_reservation_checkin_today"...
<menuitem id="menu_hotel_reservation_checkin_today"...
<record id="action_hotel_reservation_checkout_today"...
<menuitem id="menu_hotel_reservation_checkout_today"...
<record id="action_hotel_reservation_in_house"...
<menuitem id="menu_hotel_reservation_in_house"...
```

#### ❌ ELIMINAR de `res_config_settings_views.xml`:
```xml
<!-- Líneas 48-57 -->
<menuitem id="menu_hotel_config"...
<menuitem id="menu_hotel_config_settings"...
```

#### ✏️ CORREGIR en `hotel_reservation_payment_views.xml`:
```xml
<!-- Línea 156 - Cambiar parent -->
ANTES: parent="hotel_reservation_base.menu_hotel_reservation"
DESPUÉS: parent="hotel_reservation_base.menu_hotel_reports"
```

**Resultado:** Solo `menuitems.xml` define la estructura de menús.

---

## 2. MODELO hotel.reservation - Eliminar Gestión de Habitaciones

### Campos a ELIMINAR:

```python
# hotel_reservation_base/models/hotel_reservation.py

# Líneas 33-38 - ELIMINAR
room_id = fields.Many2one(
    'product.product',
    string='Habitación',
    domain=[('is_room', '=', True)],
    help='Producto configurado como habitación'
)

# Líneas 47-52 - ELIMINAR
room_type_id = fields.Many2one(
    'product.category',
    string='Tipo de Habitación',
    compute='_compute_room_type',
    store=True
)

# Líneas 133-138 - ELIMINAR
room_subtotal = fields.Monetary(
    string='Subtotal Habitación',
    compute='_compute_amounts',
    store=True,
    currency_field='currency_id'
)
```

### Métodos a ELIMINAR:

```python
# Líneas 190-196 - ELIMINAR
@api.depends('room_id')
def _compute_room_type(self):
    for reservation in self:
        if reservation.room_id:
            reservation.room_type_id = reservation.room_id.categ_id
        else:
            reservation.room_type_id = False
```

### Modificar `_compute_amounts()`:

```python
# Líneas 203-243 - MODIFICAR

@api.depends('line_ids.price_subtotal', 'payment_ids.amount',
             'pos_order_ids.amount_total')  # Eliminar room_id, checkin/checkout
def _compute_amounts(self):
    for reservation in self:
        # ELIMINAR cálculo de room_subtotal (líneas 208-219)

        # MANTENER
        reservation.charges_subtotal = sum(line.price_subtotal for line in reservation.line_ids)

        reservation.pos_charges_subtotal = sum(
            order.amount_total for order in reservation.pos_order_ids
            if order.state in ['paid', 'done', 'invoiced']
        )

        # MODIFICAR - Sin room_subtotal
        reservation.amount_total = (
            reservation.charges_subtotal +
            reservation.pos_charges_subtotal
        )

        reservation.total_paid = sum(
            payment.amount_reservation_currency for payment in reservation.payment_ids
        )

        reservation.balance = reservation.amount_total - reservation.total_paid
```

---

## 3. VISTAS - Actualizar

### hotel_reservation_views.xml

#### Form View (líneas 43-61):
```xml
<!-- ANTES -->
<group>
    <field name="partner_id" options="{'no_create': True}"/>
    <field name="room_id" options="{'no_create': True}"/>  <!-- ELIMINAR -->
    <field name="room_number"/>
    <field name="room_type_id"/>  <!-- ELIMINAR -->
</group>

<!-- DESPUÉS -->
<group>
    <field name="partner_id" options="{'no_create': True}"/>
    <field name="room_number"/>
    <field name="checkin_date"/>
    <field name="checkout_date"/>
</group>
<group>
    <field name="adults"/>
    <field name="children"/>
    <field name="pricelist_id" options="{'no_create': True}"/>
</group>
```

#### Totales (líneas 119-133):
```xml
<!-- ELIMINAR línea 121 -->
<field name="room_subtotal" widget="monetary" options="{'currency_field': 'currency_id'}"/>

<!-- MANTENER -->
<field name="charges_subtotal" widget="monetary" options="{'currency_field': 'currency_id'}"/>
<field name="pos_charges_subtotal" widget="monetary" options="{'currency_field': 'currency_id'}"/>
<field name="amount_total".../>
<field name="total_paid".../>
<field name="balance".../>
```

#### Tree View (líneas 148-160):
```xml
<!-- ELIMINAR room_id si existe -->
```

#### Search View:
```xml
<!-- Revisar si tiene filtros por room_type_id y eliminarlos -->
```

---

## 4. CAMPOS A MANTENER (Aportan valor)

### ✅ Información Básica del Folio:
- `name` - Código del folio
- `partner_id` - Huésped
- `room_number` - Identificador simple (texto)
- `adults`, `children` - Info básica
- `checkin_date`, `checkout_date` - Fechas planificadas
- `checkin_real`, `checkout_real` - Fechas reales
- `state` - Flujo del folio
- `notes` - Observaciones

### ✅ Multi-moneda y Tarifas:
- `currency_id` - Moneda del folio
- `pricelist_id` - Tarifas para cargos manuales

### ✅ Relaciones (para Apps 2 y 3):
- `line_ids` - Cargos manuales
- `payment_ids` - Anticipos
- `pos_order_ids` - Para pos_hotel_integration

### ✅ Campos Monetarios (Core):
- `charges_subtotal` - Suma cargos manuales
- `pos_charges_subtotal` - Suma consumos POS
- `amount_total` - Total del folio
- `total_paid` - Anticipos aplicados
- `balance` - Saldo pendiente

### ✅ Auditoría:
- `company_id` - Multi-compañía
- `user_id` en lines - Trazabilidad

---

## 5. IMPACTO EN OTROS ARCHIVOS

### ✅ NO requiere cambios:
- `hotel_reservation_line.py` - Solo usa campos que se mantienen
- `hotel_reservation_payment.py` - No depende de room_id
- `wizards/` - No afectado
- `security/` - No afectado
- `data/` - No afectado

---

## 6. BENEFICIOS DE LA REFACTORIZACIÓN

### Alineación con el Concepto:
✅ hotel_reservation_base = "Gestor de Folios" (sin gestión de habitaciones)
✅ Producto de habitación lo manejará hotel_sale_bridge (App 3)
✅ Eliminada duplicación de menús
✅ Código más limpio y mantenible

### Simplicidad:
- **Campos eliminados:** 3 (room_id, room_type_id, room_subtotal)
- **Métodos eliminados:** 1 (_compute_room_type)
- **Líneas eliminadas:** ~100 (menús duplicados)
- **Complejidad reducida:** Cálculos más simples

### Flexibilidad:
- ✅ Mantiene pricelist_id para tarifas variables
- ✅ Mantiene pos_order_ids para futura integración
- ✅ Mantiene toda la lógica de anticipos
- ✅ Mantiene multi-moneda

---

## 7. PLAN DE EJECUCIÓN

### Paso 1: Eliminar Menús Duplicados
- [ ] Eliminar líneas 227-289 de hotel_reservation_views.xml
- [ ] Eliminar líneas 48-57 de res_config_settings_views.xml
- [ ] Corregir parent en hotel_reservation_payment_views.xml línea 156

### Paso 2: Actualizar Modelo
- [ ] Eliminar room_id de hotel_reservation.py
- [ ] Eliminar room_type_id de hotel_reservation.py
- [ ] Eliminar room_subtotal de hotel_reservation.py
- [ ] Eliminar método _compute_room_type()
- [ ] Simplificar _compute_amounts() (eliminar cálculo de room_subtotal)
- [ ] Actualizar @api.depends() en _compute_amounts()

### Paso 3: Actualizar Vistas
- [ ] Eliminar room_id de form view
- [ ] Eliminar room_type_id de form view
- [ ] Reorganizar campos en form view
- [ ] Eliminar room_subtotal de totales
- [ ] Revisar tree view
- [ ] Revisar search view

### Paso 4: Testing
- [ ] Instalar módulo actualizado
- [ ] Crear folio de prueba
- [ ] Agregar cargo manual
- [ ] Registrar anticipo
- [ ] Verificar cálculos
- [ ] Verificar menús (sin duplicados)

### Paso 5: Documentación
- [ ] Actualizar CLAUDE.md
- [ ] Commit con mensaje descriptivo
- [ ] Push a repositorio

---

## 8. RIESGOS Y MITIGACIÓN

### ⚠️ Riesgo: Datos existentes con room_id
**Mitigación:** El campo simplemente desaparece, no afecta folios existentes (solo no se mostrará)

### ⚠️ Riesgo: Código que dependa de room_subtotal
**Mitigación:** Los cargos manuales y POS siguen funcionando. Si se necesita un subtotal de habitación, se puede agregar manualmente como cargo.

### ⚠️ Riesgo: Menús rotos después de eliminar duplicados
**Mitigación:** Solo eliminamos duplicados, los originales en menuitems.xml se mantienen.

---

## Resultado Esperado

Un módulo **hotel_reservation_base** que:
- ✅ Es SOLO un gestor de folios (cuentas corrientes)
- ✅ NO gestiona habitaciones ni productos
- ✅ Tiene menús únicos y bien organizados
- ✅ Es más simple y mantenible
- ✅ Está listo para integrarse con Apps 2 y 3
- ✅ Sigue siendo funcional de forma independiente
