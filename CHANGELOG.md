# Changelog
Todas las modificaciones notables de este proyecto se documentarán en este archivo.

El formato se inspira en "Keep a Changelog". Las fechas están en UTC.

## [2025-08-21]
### Added
- Listado de Usuarios (solo Administradores).
  - Nueva vista y URL para listar usuarios.
  - Nuevo template: `usuarios/templates/usuarios/lista_usuarios.html`.
  - Enlace desde la página de inicio/admin para acceder al listado (template `home`).
- PR: #1 "Listado de Usuarios (Lectura) desde un Administrador".
- Commit: [8f318e5](https://github.com/RguerreroHKA/Modulo_User/commit/8f318e515e6789542ee698809bae1de83c13e53a)

### Changed
- Ajustes en `usuarios/views.py` y `usuarios/urls.py` para exponer el listado.
- Actualización de `.gitignore` (limpieza de bytecode y caché).

### Removed
- Archivos generados de Python del historial (p. ej. `*.pyc`, `__pycache__`).

---

## [2025-08-20]
### Changed
- Dejar de trackear bases de datos SQLite locales (p. ej. `db.sqlite3`).
  - Commit: [d98a1ec](https://github.com/RguerreroHKA/Modulo_User/commit/d98a1ec6fd997ea28c3869127c258911c8ca4f31)

- Ampliación de `.gitignore` con ignores estándar de Django/Python.
  - Commit: [f1cd1d0](https://github.com/RguerreroHKA/Modulo_User/commit/f1cd1d0dec924626e09675db6afd93aeae545c8f)

---

## [Inicial]
### Added
- Estructura base del proyecto Django y app `usuarios`.
  - Commit: [0d60d1e](https://github.com/RguerreroHKA/Modulo_User/commit/0d60d1ee5f62cc1ce99f37468b30d50fb2cc9c8b)