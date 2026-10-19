# 🐾 Tablero contable MYPE (Streamlit)

Versión en Python del tablero HTML "Contabilidades - Registro 2026".

## Estructura
```
tablero_contable/
├── app.py                  # Interfaz Streamlit (pestañas, filtros, checklist)
├── core.py                 # Lógica: fechas, estados, persistencia, backup
├── requirements.txt
├── data/
│   ├── calendario.py       # Cronogramas SUNAT 2026 (IGV-Renta y SIRE)
│   ├── libros.py           # Libros por régimen/tramo y checklist mensual
│   └── datos_iniciales.json# Tus 12 empresas y 107 tareas del HTML
└── .streamlit/
    ├── config.toml         # Colores
    └── secrets.toml.example# Contraseña opcional
```

## Ejecutar en tu PC
```bash
pip install -r requirements.txt
streamlit run app.py
```
La primera vez copia `datos_iniciales.json` a `data/estado.json`; ahí se guardan tus avances.

## Subir a Streamlit Community Cloud
1. Sube la carpeta a un repositorio de GitHub (**privado**, tiene datos de tus clientes).
2. En share.streamlit.io: *New app* → elige el repo → archivo principal `app.py`.
3. En *Settings → Secrets* agrega `PASSWORD = "tu-clave"` para proteger el acceso.

⚠️ En Streamlit Cloud el disco es temporal: si la app se reinicia se pierden los avances.
Usa **💾 Copia de seguridad → Descargar copia** con frecuencia y vuelve a cargarla cuando haga falta.
Para persistencia permanente, cambia `guardar()`/`cargar()` en `core.py` por una base de datos
(Supabase, Google Sheets, etc.).

Verifica siempre las fechas en sunat.gob.pe.
