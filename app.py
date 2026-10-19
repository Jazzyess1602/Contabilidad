"""Tablero contable MYPE - versión Streamlit."""
from datetime import date

import streamlit as st

import core
from data.calendario import CAL, MESES
from data.libros import (LIBROS, OPCIONALES, REGIMENES, REQ, TRAMOS, items_mes)

st.set_page_config(page_title="Tablero contable MYPE", page_icon="🐾", layout="centered")

st.markdown("""
<style>
.badge{font-size:.75rem;font-weight:700;padding:3px 10px;border-radius:99px;white-space:nowrap}
.b-vencido{background:#fee2e2;color:#b91c1c}.b-urgente{background:#fef3c7;color:#92400e}
.b-prox,.b-ok{background:#dbeafe;color:#1e40af}.b-hecho{background:#dcfce7;color:#166534}
.b-na,.b-sinfecha{background:#e5e7eb;color:#6b7280}
.tag{font-size:.7rem;padding:1px 7px;border-radius:99px;border:1px solid #ccc;color:#777;margin-left:6px}
.hecho-txt{text-decoration:line-through;opacity:.55}
.tarea-sub{color:#6b7280;font-size:.82rem}
</style>
""", unsafe_allow_html=True)


# ---------- acceso opcional (contraseña en .streamlit/secrets.toml) ----------
def pedir_clave():
    clave = st.secrets.get("PASSWORD", None) if hasattr(st, "secrets") else None
    if not clave or st.session_state.get("ok"):
        return
    st.title("🔒 Tablero contable MYPE")
    v = st.text_input("Contraseña", type="password")
    if v and v == clave:
        st.session_state.ok = True
        st.rerun()
    st.stop()


try:
    pedir_clave()
except FileNotFoundError:
    pass  # sin secrets.toml: acceso libre (modo local)

# ---------- estado ----------
if "S" not in st.session_state:
    st.session_state.S = core.cargar()
S = st.session_state.S
if "mes_t" not in st.session_state:
    st.session_state.mes_t = core.primer_periodo()
if "mes_r" not in st.session_state:
    st.session_state.mes_r = core.primer_periodo()


def persistir():
    core.guardar(S)


def flash(msg, tipo="ok"):
    st.session_state["_flash"] = (tipo, msg)


# ---------- cabecera ----------
hoy = date.today()
st.title("🐾 Tablero contable MYPE")
st.caption(f"Hoy es {core.fmt(hoy.isoformat())}")

if "_flash" in st.session_state:
    tipo, msg = st.session_state.pop("_flash")
    (st.success if tipo == "ok" else st.error)(msg)

# ---------- copia de seguridad ----------
with st.expander("💾 Copia de seguridad (guardar o recuperar tus empresas y avances)"):
    st.caption("Descarga la copia y guárdala. Para recuperarla, súbela aquí y elige Reemplazar o Combinar.")
    st.download_button("⬇ Descargar copia", core.exportar(S), "copia-tablero-contable.json", "application/json")
    up = st.file_uploader("📂 Cargar copia", type=["json", "txt"])
    if up is not None:
        d = core.parsear_copia(up.getvalue().decode("utf-8", errors="ignore"))
        if d is None:
            st.error("El archivo no es una copia válida.")
        else:
            b1, b2 = st.columns(2)
            if b1.button("♻ Reemplazar todo"):
                S.clear(); S.update(d); persistir()
                flash(f"Copia restaurada: {len(S['c'])} empresas."); st.rerun()
            if b2.button("➕ Combinar"):
                n = core.combinar(S, d)
                flash(f"Se agregaron {n} empresas nuevas (las que ya existían por RUC se dejaron igual)."); st.rerun()

tab1, tab2 = st.tabs(["📅 Tareas y vencimientos", "📚 Registros, provisiones y cierre mensual"])

# =====================================================================
# TAB 1: TAREAS
# =====================================================================
with tab1:
    # ----- agregar empresa -----
    with st.expander("➕ Agregar empresa"):
        with st.form("f_emp", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre de la empresa")
            ruc = c2.text_input("RUC (11 dígitos)", max_chars=11)
            desde = st.selectbox("Generar obligaciones", range(len(CAL)),
                                 index=core.primer_periodo(), format_func=lambda i: f"Desde {CAL[i][0]}")
            bc = st.checkbox("Buen contribuyente / UESP")
            k1, k2, k3 = st.columns(3)
            kM = k1.checkbox("IGV-Renta / PLAME", True)
            kS = k2.checkbox("SIRE", True)
            kR = k3.checkbox("Renta anual 2026", True)
            if st.form_submit_button("+ Agregar empresa", type="primary"):
                err = core.agregar_empresa(S, nom, ruc, bc, desde, kM, kS, kR)
                flash(err or "Empresa agregada.", "err" if err else "ok")
                st.rerun()

    # ----- mis empresas -----
    with st.expander(f"🏢 Mis empresas ({len(S['c'])})"):
        for c in sorted(S["c"], key=lambda x: x["n"]):
            pend = sum(1 for t in S["t"] if t["c"] == c["id"] and not t.get("h") and not t.get("na"))
            a, b, d_ = st.columns([6, 1, 1])
            a.markdown(f"**{c['n']}**  \n<span class='tarea-sub'>RUC {c['r']} · dígito {core.digito(c)}"
                       f"{' · BC' if c.get('bc') else ''} · {pend} pend.</span>", unsafe_allow_html=True)
            with b.popover("✏️"):
                nn = st.text_input("Nuevo nombre", c["n"], key=f"ren_{c['id']}")
                if st.button("Guardar", key=f"rens_{c['id']}") and nn.strip():
                    c["n"] = nn.strip(); persistir(); st.rerun()
            with d_.popover("🗑"):
                st.warning(f"¿Eliminar {c['n']} y todas sus tareas?")
                if st.button("Sí, eliminar", key=f"del_{c['id']}"):
                    core.eliminar_empresa(S, c["id"]); st.rerun()

    # ----- otra obligación -----
    with st.expander("📝 Otra obligación (renta anual, PLE, DAOT, etc.)"):
        if not S["c"]:
            st.info("Primero agrega una empresa.")
        else:
            with st.form("f_otra", clear_on_submit=True):
                cc = st.selectbox("Empresa", [c["id"] for c in S["c"]],
                                  format_func=lambda i: core.empresa(S, i)["n"])
                ob = st.selectbox("Obligación (o escribe otra abajo)", [
                    "Renta anual (PDT 705)", "Libros electrónicos (PLE)", "Declaración informativa (DAOT)",
                    "Detracciones", "Otro pago a cuenta", "Otra…"])
                ob2 = st.text_input("Si elegiste 'Otra…', escríbela aquí")
                fe = st.date_input("Fecha de vencimiento", value=hoy)
                if st.form_submit_button("+ Agregar"):
                    titulo = ob2 if ob == "Otra…" else ob
                    if titulo.strip():
                        core.agregar_tarea(S, cc, titulo, fe); st.rerun()
                    else:
                        st.error("Escribe la obligación.")

    # ----- filtros -----
    st.markdown("**Qué obligaciones ver**")
    f1, f2, f3, f4 = st.columns(4)
    ks = {"m": f1.checkbox("IGV-Renta / PLAME", True, key="fk_m"),
          "s": f2.checkbox("SIRE", True, key="fk_s"),
          "r": f3.checkbox("Renta anual", True, key="fk_r"),
          "o": f4.checkbox("Otras", True, key="fk_o")}
    g1, g2, g3 = st.columns([2, 2, 2])
    orden = g1.selectbox("Ordenar", ["fecha", "digito", "empresa"], key="ord",
                         format_func={"fecha": "Por fecha", "digito": "Por último dígito del RUC", "empresa": "Por empresa"}.get)
    filtro = g2.selectbox("Empresa", [""] + [c["id"] for c in sorted(S["c"], key=lambda x: x["n"])], key="fco",
                          format_func=lambda i: f"Todas ({len(S['c'])})" if not i else f"{core.empresa(S, i)['n']} (…{core.digito(core.empresa(S, i))})")
    ocultar_na = g3.checkbox('Ocultar "No aplica"', key="hna")

    base = [t for t in S["t"]
            if core.empresa(S, t["c"]) and (not filtro or t["c"] == filtro)
            and ks.get(t.get("k", "o"), True) and not (ocultar_na and t.get("na"))]

    # ----- métricas -----
    v = u = p = h = 0
    for t in base:
        e = core.estado(t)
        if e == "na":
            continue
        if e == "hecho":
            h += 1
        else:
            p += 1
            v += e == "vencido"
            u += e == "urgente"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vencidas", v); m2.metric("Vencen ≤ 3 días", u); m3.metric("Pendientes", p); m4.metric("Presentadas", h)
    st.progress(h / (p + h) if (p + h) else 0.0)
    if v:
        st.info(f"Tienes {v} vencida{'s' if v > 1 else ''}. ¡Vamos con ellas! 💪")
    elif u:
        st.info(f"{u} vence{'n' if u > 1 else ''} en 3 días o menos ⏰")
    elif p:
        st.info("Todo va en orden. ¡Buen trabajo! ✨")
    elif h:
        st.success("¡Todo presentado! 🎉")

    # ----- selector de mes -----
    opciones = list(range(len(CAL))) + [-1]

    def etiqueta_mes(q):
        its = [x for x in base if core.periodo_de(x) == q and not x.get("na")]
        if q < 0:
            return f"Otras {len(its)}"
        dn = sum(1 for x in its if x.get("h"))
        return f"{CAL[q][0][:3]} {round(dn / len(its) * 100) if its else 0}%"

    TM = st.radio("Período", opciones, key="mes_t", horizontal=True, format_func=etiqueta_mes, label_visibility="collapsed")

    lista = [x for x in base if core.periodo_de(x) == TM]

    def clave(x):
        A, B = core.empresa(S, x["c"]), core.empresa(S, x["c"])
        cola = (1 if (x.get("h") or x.get("na")) else 0, x.get("f") or "9")
        if orden == "digito":
            return (core.digito(A), A["n"]) + cola
        if orden == "empresa":
            return (A["n"],) + cola
        return cola

    lista.sort(key=clave)
    st.subheader(f"{MESES[TM]} 2026 · período {CAL[TM][0]}" if TM >= 0 else "Otras obligaciones (sin período mensual)")
    if not lista:
        st.info("Sin tareas para mostrar en este período. Agrega una empresa con su RUC arriba 👆")

    ultimo = None
    for x in lista:
        c = core.empresa(S, x["c"])
        grupo = f"RUC termina en {core.digito(c)}" if orden == "digito" else c["n"] if orden == "empresa" else None
        if grupo and grupo != ultimo:
            st.markdown(f"##### 🐾 {grupo}")
            ultimo = grupo
        e = core.estado(x)
        with st.container(border=True):
            ca, cb, cc_, cd, ce, cf = st.columns([0.6, 5, 2.2, 1, 1, 1], vertical_alignment="center")
            kc = f"h_{x['id']}"
            st.session_state[kc] = bool(x.get("h"))
            def toggle(x=x, kc=kc):
                x["h"] = st.session_state[kc]; persistir()
            ca.checkbox("ok", key=kc, on_change=toggle, disabled=bool(x.get("na")), label_visibility="collapsed")
            tag = "<span class='tag'>SIRE</span>" if x.get("k") == "s" else ""
            cls = "hecho-txt" if e in ("hecho", "na") else ""
            nota = f"<br><span class='tarea-sub'>{x['nt']}</span>" if x.get("nt") else ""
            cb.markdown(f"<span class='{cls}'><b>{x['t']}</b>{tag}</span><br>"
                        f"<span class='tarea-sub'>{c['n']} · RUC …{core.digito(c)} · {core.fmt(x.get('f'))}</span>{nota}",
                        unsafe_allow_html=True)
            cc_.markdown(f"<span class='badge b-{e}'>{core.texto_estado(x)}</span>", unsafe_allow_html=True)
            if cd.button("Aplica" if x.get("na") else "N/A", key=f"na_{x['id']}", help="Marcar como No aplica"):
                x["na"] = not x.get("na")
                if x["na"]:
                    x["h"] = False
                persistir(); st.rerun()
            with ce.popover("📅"):
                nf = st.date_input("Fecha de vencimiento", value=date.fromisoformat(x["f"]) if x.get("f") else hoy, key=f"df_{x['id']}")
                if st.button("Guardar fecha", key=f"sf_{x['id']}"):
                    x["f"] = nf.isoformat(); persistir(); st.rerun()
            if cf.button("✕", key=f"rm_{x['id']}", help="Eliminar"):
                S["t"] = [y for y in S["t"] if y is not x]; persistir(); st.rerun()

    st.divider()
    z1, z2, _ = st.columns([1, 1, 3])
    with z1.popover("Vaciar todo"):
        st.warning("¿Borrar todas las empresas y tareas?")
        if st.button("Sí, borrar todo"):
            S["c"].clear(); S["t"].clear(); persistir(); st.rerun()
    if z2.button("Reiniciar presentadas"):
        for t in S["t"]:
            t["h"] = False
        persistir(); st.rerun()

    st.caption("Fechas del Cronograma de Obligaciones Mensuales 2026 (con ITF) y del Cronograma de Atraso de Registros "
               "Electrónicos (SIRE) 2026 de SUNAT, R.S. 281-2022/SUNAT. La Renta anual queda sin fecha hasta que SUNAT "
               "publique el cronograma del ejercicio 2026; usa 📅 para fijarla (o cambiar cualquier fecha por prórrogas). "
               "Verifica siempre en sunat.gob.pe.")

# =====================================================================
# TAB 2: REGISTROS, PROVISIONES Y CIERRE
# =====================================================================
with tab2:
    st.info("Las empresas se sincronizan con la pestaña Tareas. Marcar el IGV-Renta o el SIRE de un mes también "
            "los marca como presentados en Tareas.")
    if not S["c"]:
        st.warning("Primero agrega empresas en la pestaña Tareas; aparecerán aquí automáticamente.")
        st.stop()

    ids = [c["id"] for c in sorted(S["c"], key=lambda x: x["n"])]
    r1, r2, r3 = st.columns(3)
    rc = r1.selectbox("Empresa", ids, key="rco", format_func=lambda i: f"{core.empresa(S, i)['n']} (…{core.digito(core.empresa(S, i))})")
    c = core.empresa(S, rc)
    c.setdefault("reg", "rmt"); c.setdefault("tr", "t1")

    reg = r2.selectbox("Régimen", list(REGIMENES), index=list(REGIMENES).index(c["reg"]),
                       format_func=REGIMENES.get, key=f"reg_{rc}")
    if reg != c["reg"]:
        c["reg"] = reg; c["tr"] = TRAMOS[reg][0][0]; persistir(); st.rerun()
    tramos = TRAMOS[c["reg"]]
    if c["tr"] not in [t[0] for t in tramos]:
        c["tr"] = tramos[0][0]
    if len(tramos) > 1:
        tr = r3.selectbox("Tramo de ingresos", [t[0] for t in tramos], key=f"tr_{rc}",
                          index=[t[0] for t in tramos].index(c["tr"]), format_func=dict(tramos).get)
        if tr != c["tr"]:
            c["tr"] = tr; persistir(); st.rerun()

    clave_libros = c["reg"] if c["reg"] in ("rus", "rer") else c["tr"]

    def tarjeta_libro(k, opcional=False):
        na = bool(c.get("lna", {}).get(k))
        with st.container(border=True):
            a, b = st.columns([5, 1.3], vertical_alignment="center")
            tit, desc, frec = LIBROS[k]
            estilo = "hecho-txt" if na else ""
            a.markdown(f"<span class='{estilo}'><b>{tit}</b></span><br>{desc}<br><span class='tarea-sub'>{frec}</span>",
                       unsafe_allow_html=True)
            if b.button("Aplica" if na else "No aplica", key=f"lna_{rc}_{k}"):
                c.setdefault("lna", {})[k] = not na; persistir(); st.rerun()

    with st.expander("Libros y registros obligatorios de esta empresa"):
        if c["reg"] == "rus":
            st.info("Nuevo RUS: sin libros ni registros contables obligatorios. Conserva comprobantes de compras y las "
                    "boletas o tickets emitidos, y paga tu cuota mensual (Form. 1611).")
        else:
            st.markdown("**Obligatorios ante SUNAT**")
            for k in REQ[clave_libros]:
                tarjeta_libro(k)
            if clave_libros == "t4":
                st.markdown("**Contabilidad completa: registros adicionales según tu actividad**")
                st.info("Con más de 1,700 UIT la contabilidad es completa. Estos registros dependen de tu giro y de las "
                        "normas de SUNAT; confírmalos para cada empresa.")
                for k in OPCIONALES:
                    tarjeta_libro(k, True)
            elif c["reg"] != "rer":
                st.info("Los libros dependen de los ingresos del ejercicio anterior (UIT 2026 = S/ 5,500). Si cruzas un "
                        "umbral, cambian para el ejercicio siguiente.")

    RM = st.radio("Mes", range(len(CAL)), key="mes_r", horizontal=True, label_visibility="collapsed",
                  format_func=lambda i: f"{CAL[i][0][:3]} {core.porcentaje_mes(S, c, i)}%")
    st.subheader(f"{MESES[RM]} 2026 · período {CAL[RM][0]}")
    st.progress(core.porcentaje_mes(S, c, RM) / 100)

    for gi, (titulo, its) in enumerate(items_mes(RM)):
        st.markdown(f"##### 🐾 {titulo}")
        for it in its:
            na = core.ck_na(S, c, RM, it)
            hecho = core.ck_hecho(S, c, RM, it)
            f = None if na else core.fecha_item(c, RM, it)
            venc = ""
            if f:
                tarde = (not hecho) and core.dias(f) < 0
                color = "#b91c1c" if tarde else "#d9603f"
                venc = f" <span style='color:{color};font-weight:600'>Vence: {core.fmt(f)}</span>"
            with st.container(border=True):
                a, b, d_ = st.columns([0.6, 6, 1.4], vertical_alignment="center")
                kk = f"ck_{rc}_{RM}_{it[0]}"
                st.session_state[kk] = hecho
                def cb(it=it, kk=kk):
                    core.set_ck_hecho(S, c, RM, it, st.session_state[kk])
                a.checkbox("ok", key=kk, on_change=cb, disabled=na, label_visibility="collapsed")
                estilo = "hecho-txt" if (hecho or na) else ""
                b.markdown(f"<span class='{estilo}'><b>{it[1]}</b></span>{venc}<br><span class='tarea-sub'>{it[2]}</span>",
                           unsafe_allow_html=True)
                if d_.button("Aplica" if na else "No aplica", key=f"nab_{rc}_{RM}_{it[0]}"):
                    core.set_ck_na(S, c, RM, it, not na); st.rerun()

    st.info("Provisiones laborales (vacaciones, CTS, gratificaciones) según el régimen laboral MYPE vigente de la empresa: "
            "la microempresa no las causa y la pequeña empresa tiene beneficios reducidos. Confirma cuál corresponde.")
