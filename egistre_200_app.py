# registre_200_app.py
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date
from zoneinfo import ZoneInfo

# ================== TIMEZONE ==================
TZ = ZoneInfo("America/Toronto")

# ================== PAGE ==================
st.set_page_config(page_title="Caisse — Retour à 200$", layout="centered")

# ================== AUTH ==================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("Accès protégé")
    pwd = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if pwd == st.secrets["APP_PASSWORD"]:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.stop()

# ================== CONFIG ==================
DENOMS = {
    "Billet 100 $": 10000,
    "Billet 50 $": 5000,
    "Billet 20 $": 2000,
    "Billet 10 $": 1000,
    "Billet 5 $": 500,
    "Pièce 2 $": 200,
    "Pièce 1 $": 100,
    "Pièce 0,25 $": 25,
    "Pièce 0,10 $": 10,
    "Pièce 0,05 $": 5,
    "Rouleau 2 $ (25) — 50 $": 5000,
    "Rouleau 1 $ (25) — 25 $": 2500,
    "Rouleau 0,25 $ (40) — 10 $": 1000,
    "Rouleau 0,10 $ (50) — 5 $": 500,
    "Rouleau 0,05 $ (40) — 2 $": 200,
}

ORDER = list(DENOMS.keys())

BIG_BILLS = ["Billet 100 $", "Billet 50 $", "Billet 20 $"]
SMALL_BILLS = ["Billet 10 $", "Billet 5 $"]
COINS = ["Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $"]
ROLLS = [k for k in ORDER if k.startswith("Rouleau")]

# ================== HELPERS ==================
def cents_to_str(c):
    return f"{c/100:.2f} $"

def total_cents(counts):
    return sum(counts.get(k, 0) * DENOMS[k] for k in DENOMS)

def sub_counts(a, b):
    return {k: a.get(k, 0) - b.get(k, 0) for k in DENOMS}

def clamp_locked(locked, available):
    out = {}
    for k, v in locked.items():
        out[k] = max(0, min(int(v), int(available.get(k, 0))))
    return out

def take_greedy(remaining, keys, available, out, locked):
    for k in keys:
        if remaining <= 0 or k in locked:
            continue
        v = DENOMS[k]
        can = available.get(k, 0) - out.get(k, 0)
        take = min(remaining // v, max(can, 0))
        out[k] += take
        remaining -= take * v
    return remaining

def suggest_retrait(diff, allowed, available, locked):
    out = {k: locked.get(k, 0) for k in DENOMS}
    remaining = diff - total_cents(out)

    allowed_set = set(allowed)

    remaining = take_greedy(remaining, [k for k in BIG_BILLS if k in allowed_set], available, out, locked)
    remaining = take_greedy(remaining, [k for k in SMALL_BILLS if k in allowed_set], available, out, locked)
    remaining = take_greedy(remaining, [k for k in COINS if k in allowed_set], available, out, locked)
    remaining = take_greedy(remaining, [k for k in ROLLS if k in allowed_set], available, out, locked)

    return out, remaining
    def rows_report(open_c, close_c, retrait_c, restant_c):
    rows = []
    t_open = t_close = t_ret = t_res = 0

    for k in ORDER:
        o = int(open_c.get(k, 0))
        c = int(close_c.get(k, 0))
        r = int(retrait_c.get(k, 0))
        s = int(restant_c.get(k, 0))

        rows.append({
            "Dénomination": k,
            "OPEN": o,
            "CLOSE": c,
            "RETRAIT": r,
            "RESTANT": s
        })

        t_open += o * DENOMS[k]
        t_close += c * DENOMS[k]
        t_ret += r * DENOMS[k]
        t_res += s * DENOMS[k]

    rows.append({
        "Dénomination": "TOTAL ($)",
        "OPEN": f"{t_open/100:.2f}",
        "CLOSE": f"{t_close/100:.2f}",
        "RETRAIT": f"{t_ret/100:.2f}",
        "RESTANT": f"{t_res/100:.2f}",
    })
    return rows


def build_print_html(rows, meta_lines):
    body = ""
    for r in rows:
        body += (
            "<tr>"
            f"<td>{r['Dénomination']}</td>"
            f"<td style='text-align:center'>{r['OPEN']}</td>"
            f"<td style='text-align:center'>{r['CLOSE']}</td>"
            f"<td style='text-align:center'>{r['RETRAIT']}</td>"
            f"<td style='text-align:center'>{r['RESTANT']}</td>"
            "</tr>"
        )

    meta_html = "".join(
        [f"<div style='opacity:0.75; font-size:12px; margin-top:3px;'>{m}</div>" for m in meta_lines]
    )

    report_inner = f"""
      <div>
        <h2 style="margin:0;">Rapport caisse — Retour à la cible</h2>
        {meta_html}
      </div>
      <div style="height:12px;"></div>
      <table style="width:100%; border-collapse:collapse; font-size:14px; background:#ffffff; color:#000000;"
             border="1" cellpadding="6" cellspacing="0">
        <thead>
          <tr style="background:#f3f3f3; color:#000;">
            <th>Dénomination</th>
            <th>OPEN</th>
            <th>CLOSE</th>
            <th>RETRAIT</th>
            <th>RESTANT</th>
          </tr>
        </thead>
        <tbody>
          {body}
        </tbody>
      </table>
    """
    report_inner_js = report_inner.replace("`", "\\`")

    html = f"""
    <div style="font-family: Arial, sans-serif;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
        <div>
          <h3 style="margin:0;">Aperçu du rapport</h3>
          <div style="opacity:0.7; font-size:12px;">Imprime seulement le tableau.</div>
        </div>
        <button id="print-btn" style="
          padding:10px 14px;
          border-radius:10px;
          border:1px solid #ccc;
          cursor:pointer;
          font-weight:600;
          background:white;
        ">🖨️ Imprimer le rapport</button>
      </div>

      <div style="height:10px;"></div>
      <div id="report">{report_inner}</div>
    </div>

    <script>
      function printOnlyReport() {{
        var reportHtml = `{report_inner_js}`;
        var w = window.open('', '_blank', 'width=900,height=700');
        w.document.open();
        w.document.write('<html><head><title>Rapport caisse</title>');
        w.document.write('<style>');
        w.document.write('body{{font-family:Arial,sans-serif;padding:18px;background:#fff;color:#000;}}');
        w.document.write('table{{width:100%;border-collapse:collapse;}}');
        w.document.write('th,td{{border:1px solid #000;padding:6px;}}');
        w.document.write('th{{background:#f3f3f3;}}');
        w.document.write('</style>');
        w.document.write('</head><body>');
        w.document.write(reportHtml);
        w.document.write('</body></html>');
        w.document.close();
        w.focus();
        w.print();
      }}
      const btn = document.getElementById('print-btn');
      if (btn) btn.addEventListener('click', printOnlyReport);
    </script>
    """
    return html

# ================== STATE ==================
if "locked" not in st.session_state:
    st.session_state.locked = {}
if "show_report" not in st.session_state:
    st.session_state.show_report = False
if "report_data" not in st.session_state:
    st.session_state.report_data = None

# ================== UI ==================
st.title("Caisse — Retour à 200 $")

# ---------- META ----------
st.header("Informations")
c1, c2, c3, c4 = st.columns(4)
with c1:
    cashier = st.text_input("Caissier / Caissière")
with c2:
    register_no = st.selectbox("Caisse #", [1, 2, 3])
with c3:
    rep_date = st.date_input("Date", value=date.today())
with c4:
    rep_time = st.time_input("Heure", value=datetime.now(TZ).time().replace(second=0))

TARGET = int(st.number_input("Montant cible ($)", value=200, step=10)) * 100

# ---------- OPEN ----------
st.header("OPEN — Fond de caisse")
open_counts = {}
o1, o2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (o1 if i % 2 == 0 else o2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"open_{k}")

st.info("TOTAL OPEN : " + cents_to_str(total_cents(open_counts)))
# ---------- CLOSE ----------
st.header("CLOSE — Fin de journée")
close_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        close_counts[k] = st.number_input(f"{k} (CLOSE)", min_value=0, step=1, value=0, key=f"close_{k}")

total_close = total_cents(close_counts)
st.success("TOTAL CLOSE : " + cents_to_str(total_close))
# ---------- RETRAIT ----------
st.header("RETRAIT")
diff = total_close - TARGET
st.write("À retirer :", cents_to_str(diff))

st.subheader("Types autorisés pour le retrait")

allowed = []
a1, a2 = st.columns(2)

for i, k in enumerate(ORDER):
    with (a1 if i % 2 == 0 else a2):
        if st.checkbox(k, value=True, key=f"allow_{k}"):
            allowed.append(k)

st.session_state.locked = clamp_locked(st.session_state.locked, close_counts)

if diff > 0 and allowed:
    retrait, remaining = suggest_retrait(diff, allowed, close_counts, st.session_state.locked)

    st.subheader("Ajuster le retrait")
    for k in allowed:
        cols = st.columns([3, 1, 1, 2])
        cols[0].write(k)
        if cols[1].button("➖", key=f"m_{k}"):
            st.session_state.locked[k] = max(0, retrait.get(k, 0) - 1)
            st.rerun()
        if cols[2].button("➕", key=f"p_{k}"):
            st.session_state.locked[k] = min(close_counts.get(k, 0), retrait.get(k, 0) + 1)
            st.rerun()
        cols[3].write(f"RETRAIT: {retrait.get(k, 0)} / Dispo: {close_counts.get(k, 0)}")

    restant = sub_counts(close_counts, retrait)
    st.info("RESTANT : " + cents_to_str(total_cents(restant)))

# ---------- REPORT ----------
st.header("Rapport")
if st.button("GÉNÉRER LE RAPPORT"):
    now_local = datetime.now(TZ)
    meta = [
        f"Caisse #: {register_no}",
        f"Caissier(ère): {cashier.strip() or '—'}",
        f"Date/Heure: {rep_date} {rep_time.strftime('%H:%M')}",
        "Généré le " + now_local.strftime("%Y-%m-%d %H:%M"),
    ]
    st.session_state.report_data = meta
    st.session_state.show_report = True

if st.session_state.show_report:
    st.success("Rapport généré (heure locale correcte).")
