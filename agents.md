# trading-lab

## Reglas de trabajo

- No eliminar funciones existentes sin verificar todos sus usos.
- Preferir cambios pequenos y localizados frente a reescribir archivos completos.
- Mantener compatibilidad con historico SQLite.
- Nunca borrar datos de data/trading.db.
- V3 debe conservarse como historico.
- Momentum V4 es el score tecnico principal.
- Reversal V1 es una estrategia independiente.
- No mezclar Momentum y Reversal en un unico score.
- Antes de modificar database/db.py, revisar todas las funciones que lo importan.
- Ejecutar validacion sintactica despues de cambios Python.
- Cuando haya cambios SQL, comprobar placeholders vs columnas.
- No modificar .env ni exponer credenciales.