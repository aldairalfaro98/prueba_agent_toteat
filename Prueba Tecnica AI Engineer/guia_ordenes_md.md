# Guía Técnica 3 — Registro y Administración de Órdenes

**Software:** GastroSoft POS  
**Versión:** 2.1.5 (enero 2025)  
**Documento técnico** — Cómo crear, gestionar y cerrar órdenes en mesas, delivery y takeaway.

## 1. Introducción

El módulo de Órdenes es el núcleo operativo de GastroSoft POS.

Permite registrar pedidos de clientes, asignarlos a meseros, calcular impuestos y propinas, aplicar descuentos y cerrar la orden de manera segura.

Este documento explica cómo manejar órdenes abiertas, agregar productos, transferir mesas y procesar pagos.

## 2. Acceso al módulo de Órdenes

1. Inicie sesión con un perfil de **Mesero**, **Administrador** o **Gerente**.

2. En el menú lateral, seleccione:  
   **Órdenes → Crear/Administrar Órdenes**

3. El panel muestra:
   - Mesas activas
   - Pedidos abiertos
   - Pedidos por takeaway o delivery
   - Botones de acción rápida: **Nueva Orden**, **Cerrar Orden**, **Transferir Mesa**

## 3. Crear una nueva orden

1. Haga clic en **"Nueva Orden"**.

2. Seleccione:
   - **Tipo de orden:** Mesa, Takeaway, Delivery
   - **Mesa asignada:** Para órdenes de mesa
   - **Cliente (opcional):** Nombre o teléfono
   - **Mesero asignado:** Usuario responsable

3. Pulse **Crear Orden**. La orden se abrirá y estará lista para agregar productos.

## 4. Agregar productos a la orden

1. Desde la orden abierta, haga clic en **"Agregar Producto"**.

2. Seleccione la categoría y el producto deseado.

3. Configure modificadores, extras o notas especiales si aplica.

4. Pulse **Añadir al carrito**. Cada producto agregado recibe un **cart_id** único dentro de la orden.

💡 **Tip:** Puede añadir múltiples unidades del mismo producto o variar modificadores entre unidades.

## 5. Modificar productos en la orden

- **Editar producto:** Cambiar cantidad, modificadores o extras.
- **Eliminar producto:** Retirar del carrito antes de cerrar la orden.

⚠️ No puede eliminar productos que ya fueron facturados parcialmente, a menos que se haga una nota de crédito.

## 6. Aplicar descuentos y propinas

- **Descuento:** Puede aplicar por producto o por total de orden.
- **Propina:** El mesero o cliente puede agregar un porcentaje opcional.

El sistema recalcula automáticamente el total neto y el impuesto.

## 7. Transferir o fusionar órdenes

- **Transferir mesa:** Mueva una orden de una mesa a otra disponible.
- **Fusionar órdenes:** Combine varias órdenes abiertas para un mismo cliente.

## 8. Cierre de orden y pago

1. Pulse **Cerrar Orden**.

2. Seleccione el método de pago:
   - Efectivo
   - Tarjeta
   - Combinado (efectivo + tarjeta)

3. Revise impuestos y propinas calculadas automáticamente.

4. Confirme el cierre.

💡 **Tip:** El sistema genera un recibo PDF que puede imprimirse o enviarse por correo.

## 9. Estados de la orden

| Estado | Descripción |
|--------|-------------|
| Abierta | Orden en progreso, sin cerrar |
| Cerrada | Orden completada y pagada |
| En preparación | Productos enviados a cocina o barra |
| Parcial | Algunos productos facturados, otros abiertos |