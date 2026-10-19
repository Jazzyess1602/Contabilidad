"""Lógica del tablero contable MYPE (sin dependencias de Streamlit)."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from data.calendario import CAL, SIRE, NOTA_RENTA
from data.libros import TRAMOS, items_mes

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
ESTADO = DATA_DIR / "estado.json"          # se crea solo; es tu base de datos local
INICIAL = DATA_DIR / "datos_iniciales.json"

DIAS_URGENTE = 3
DIAS_PROXIMO = 10


# ---------- persistencia ----------
def _normalizar(d: dict) -> dict:
    """Convierte ids numéricos (del HTML) a texto para que sean estables."""
    d.setdefault("c", [])
    d.setdefault("t", [])
    for c in d["c"]:
        c["id"] = str(c["id"])
    vistos: set[str] = set()
    for t in d["t"]:
        t["c"] = str(t["c"])
        tid = str(t.get("id", ""))
        # en copias antiguas varias tareas compartían id (el de la empresa): se hace único
        if not tid or tid in vistos:
            tid = nuevo_id()
        vistos.add(tid)
        t["id"] = tid
    return d


def cargar() -> dict:
    if not ESTADO.exists() and INICIAL.exists():
        shutil.copy(INICIAL, ESTADO)
    if ESTADO.exists():
        return _normalizar(json.loads(ESTADO.read_text(encoding="utf-8")))
    return {"c": [], "t": []}


def guardar(s: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------- empresas ----------
def digito(c: dict) -> int:
    return int(c["r"][-1])


def indice_cronograma(c: dict) -> int:
    """Posición en el cronograma: 6 si es buen contribuyente, si no según último dígito."""
    return 6 if c.get("bc") else [0, 1, 2, 2, 3, 3, 4, 4, 5, 5][digito(c)]


def empresa(s: dict, cid: str) -> dict | None:
    return next((c for c in s["c"] if c["id"] == cid), None)


def primer_periodo(hoy: date | None = None) -> int:
    """Primer período cuya fecha (dígito 0) aún no pasó; si no hay, el último."""
    hoy = hoy or date.today()
    for i, (_, fechas) in enumerate(CAL):
        if date.fromisoformat(fechas[0]) >= hoy:
            return i
    return len(CAL) - 1


def agregar_empresa(s, nombre, ruc, buen_contribuyente, desde, mensual, sire, renta):
    ruc = "".join(ch for ch in ruc if ch.isdigit())
    if not nombre.strip() or len(ruc) != 11:
        return "Ingresa el nombre y un RUC de 11 dígitos."
    if any(c["r"] == ruc for c in s["c"]):
        return "Ya existe una empresa con ese RUC."
    c = {"id": nuevo_id(), "n": nombre.strip(), "r": ruc, "bc": buen_contribuyente}
    s["c"].append(c)
    k = indice_cronograma(c)
    if mensual:
        for i, (p, f) in enumerate(CAL):
            if i >= desde:
                s["t"].append({"id": nuevo_id(), "c": c["id"], "t": f"IGV-Renta / PLAME · {p}", "f": f[k], "h": False, "k": "m"})
    if sire:
        for i, (p, f) in enumerate(SIRE):
            if i >= desde:
                s["t"].append({"id": nuevo_id(), "c": c["id"], "t": f"SIRE (RVIE / RCE) · {p}", "f": f[k], "h": False, "k": "s"})
    if renta:
        s["t"].append({"id": nuevo_id(), "c": c["id"], "t": "Renta anual 2026 (Form. 710)", "f": None, "h": False, "k": "r", "nt": NOTA_RENTA})
    guardar(s)
    return None


def eliminar_empresa(s, cid):
    s["c"] = [c for c in s["c"] if c["id"] != cid]
    s["t"] = [t for t in s["t"] if t["c"] != cid]
    guardar(s)


def agregar_tarea(s, cid, titulo, fecha: date):
    s["t"].append({"id": nuevo_id(), "c": cid, "t": titulo.strip(), "f": fecha.isoformat(), "h": False, "k": "o"})
    guardar(s)


# ---------- tareas ----------
def dias(f: str) -> int:
    return (date.fromisoformat(f) - date.today()).days


def estado(t: dict) -> str:
    if t.get("na"):
        return "na"
    if t.get("h"):
        return "hecho"
    if not t.get("f"):
        return "sinfecha"
    d = dias(t["f"])
    return "vencido" if d < 0 else "urgente" if d <= DIAS_URGENTE else "prox" if d <= DIAS_PROXIMO else "ok"


def texto_estado(t: dict) -> str:
    if t.get("na"):
        return "No aplica"
    if t.get("h"):
        return "Presentada"
    if not t.get("f"):
        return "Fecha por confirmar"
    d = dias(t["f"])
    if d < 0:
        return f"Venció hace {-d} d"
    return "Vence hoy" if d == 0 else "Vence mañana" if d == 1 else f"En {d} días"


_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]


def fmt(f: str | None) -> str:
    if not f:
        return "sin fecha"
    d = date.fromisoformat(f)
    return f"{_DIAS[d.weekday()]}, {d.day:02d} {_MESES[d.month - 1]} {d.year}"


def periodo_de(t: dict) -> int:
    """Índice del período mensual al que pertenece la tarea; -1 si es 'Otras'."""
    for i, (p, _) in enumerate(CAL):
        if f"· {p}" in t["t"]:
            return i
    return -1


# ---------- registros / checklist mensual ----------
def tarea_periodo(s, cid, k, m):
    return next((t for t in s["t"] if t["c"] == cid and t.get("k") == k and f"· {CAL[m][0]}" in t["t"]), None)


def _enlazada(s, c, m, it):
    return tarea_periodo(s, c["id"], it[3], m) if it[3] in ("s", "m") else None


def ck_hecho(s, c, m, it) -> bool:
    t = _enlazada(s, c, m, it)
    return bool(t["h"]) if t else bool(c.get("ck", {}).get(f"{m}|{it[0]}"))


def ck_na(s, c, m, it) -> bool:
    t = _enlazada(s, c, m, it)
    return bool(t.get("na")) if t else bool(c.get("ck", {}).get(f"{m}|{it[0]}|na"))


def set_ck_hecho(s, c, m, it, v):
    t = _enlazada(s, c, m, it)
    if t:
        t["h"] = v
    else:
        c.setdefault("ck", {})[f"{m}|{it[0]}"] = v
    guardar(s)


def set_ck_na(s, c, m, it, v):
    t = _enlazada(s, c, m, it)
    if t:
        t["na"] = v
        if v:
            t["h"] = False
    else:
        ck = c.setdefault("ck", {})
        ck[f"{m}|{it[0]}|na"] = v
        if v:
            ck[f"{m}|{it[0]}"] = False
    guardar(s)


def porcentaje_mes(s, c, m) -> int:
    n = d = 0
    for _, its in items_mes(m):
        for it in its:
            if ck_na(s, c, m, it):
                continue
            n += 1
            d += ck_hecho(s, c, m, it)
    return round(d / n * 100) if n else 0


def fecha_item(c, m, it):
    if it[3] == "s":
        return SIRE[m][1][indice_cronograma(c)]
    if it[3] in ("m", "w"):
        return CAL[m][1][indice_cronograma(c)]
    return None


# ---------- copia de seguridad ----------
def exportar(s) -> str:
    return json.dumps({"app": "tablero-contable-mype", "v": 3, "fecha": datetime.now().isoformat(), "datos": s},
                      ensure_ascii=False, indent=1)


def parsear_copia(texto: str) -> dict | None:
    try:
        o = json.loads(texto)
        d = o.get("datos", o)
        if not isinstance(d.get("c"), list) or not isinstance(d.get("t"), list):
            return None
        return _normalizar(d)
    except Exception:
        return None


def combinar(s, d) -> int:
    n = 0
    for c in d["c"]:
        if any(x["r"] == c["r"] for x in s["c"]):
            continue
        s["c"].append(c)
        s["t"].extend(t for t in d["t"] if t["c"] == c["id"])
        n += 1
    guardar(s)
    return n
