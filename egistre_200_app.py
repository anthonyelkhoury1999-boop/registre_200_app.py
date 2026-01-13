# registre_200_app.py
# Caisse — Retour à la cible (ex: 200$)
# - OPEN / CLOSE en 2 colonnes
# - Suggestion RETRAIT: favorise 100/50/20, puis 10/5 rarement, pièces seulement pour finir, rouleaux en dernier
# - Ajustement interactif +/- (verrouille la dénomination)
# - Rapport imprimable (bouton imprime le tableau)
# - Timezone Montréal (America/Toronto)
# - PAS de météo

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date
from zoneinfo import ZoneInfo

# ================== CONFIG APP ==================
st.set_page_config(page_title="Caisse — Retour à la cible", layout="centered")
TZ = ZoneInfo("America/Toronto")

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

# ================== DENOMS ==================
DENOMS = {
    # Billets
    "Billet 100 $": 10000,
    "Billet 50 $": 5000,
    "Billet 20 $": 2000,
    "Billet 10 $": 1000,
    "Billet 5 $": 500,
    # Pièces
    "Pièce 2 $": 200,
    "Pièce 1 $": 100,
    "Pièce 0,25 $": 25,
    "Pièce 0,10 $": 10,
    "Pièce 0,05 $": 5,
    # Rouleaux
    "Rouleau 2 $ (25) — 50 $": 5000,
    "Rouleau 1 $ (25) — 25 $": 2500,
    "Rouleau 0,25 $ (40) — 10 $": 1000,
    "Rouleau 0,10 $ (50) — 5 $": 500,
    "Rouleau 0,05 $ (40) — 2 $": 200,
}

BILLS_BIG = ["Billet 100 $", "Billet 50 $", "Billet 20 $"]
BILLS_SMALL = ["Billet 10 $", "Billet 5 $"]
COINS = ["Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $"]
ROLLS = [
    "Rouleau 2 $ (25) — 50 $",
    "Rouleau 1 $ (25) — 25 $",
    "Rouleau 0,25 $ (40) — 10 $",
    "Rouleau 0,10 $ (50) — 5 $",
    "Rouleau 0,05 $ (40) — 2 $",
]

# Affichage (UI): billets -> pièces -> rouleaux
DISPLAY_ORDER = BILLS_BIG + BILLS_SMALL + COINS + ROLLS

# ================== HELPERS ==================
def cents_to_str(c: int) -> str:
    return f"{c / 100:.2f} $"

def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)

def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}

def clamp_locked(locked: dict, avail: dict) -> dict:
    out = {}
    for k, v in locked.items():
        v = int(v)
        if v < 0:
            v = 0
        mx = int(avail.get(k, 0))
        if v > mx:
            v = mx
        out[k] = v
    return out

def take_greedy(remaining: int, keys: list, avail: dict, out: dict, locked: dict) -> int:
    """
    Essaie de prendre le max possible sur 'keys' (dans cet ordre), en respectant:
    - disponibilité (avail)
    - déjà pris (out)
    - verrouillés (locked) => on n'y touche pas
    """
    for k in keys:
        if remaining <= 0:
            break
        if k in locked:
            continue
        if k not in avail:
            continue
        v = DENOMS[k]
        can_take = int(avail.get(k, 0)) - int(out.get(k, 0))
        if can_take < 0:
            can_take = 0
        take = min(remaining // v, can_take)
        if take > 0:
            out[k] = int(out.get(k, 0)) + int(take)
            remaining -= int(take) * v
    return remaining

def suggest_retrait(diff_cents: int, allowed: list, avail: dict, locked: dict):
    """
    Priorité:
    1) 100/50/20 (gros billets)
    2) 10/5 (rarement)
    3) Pièces seulement pour finir
    4) Rouleaux en dernier recours
    """
    out = {k: 0 for k in DENOMS}

    # appliquer locked d'abord
    for k, q in locked.items():
        out[k] = int(q)

    remaining = diff_cents - total_cents(out)
    if remaining < 0:
        return out, remaining  # locked trop haut

    allowed_set = set(allowed)

    # clés autorisées + ordonnées
    big = [k for k in BILLS_BIG if k in allowed_set]
    small = [k for k in BILLS_SMALL if k in allowed_set]
    coins = [k for k in COINS if k in allowed_set]
    rolls = [k for k in ROLLS if k in allowed_set]

    # IMPORTANT: coins pour finir => on prend du plus grand au plus petit
    coins_desc = sorted(coins, key=lambda x: DENOMS[x], reverse=True)
    rolls_desc = sorted(rolls, key=lambda x: DENOMS[x], reverse=True)

    remaining = take_greedy(remaining, big, avail, out, locked)
    remaining = take_greedy(remaining, small, avail, out, locked)
    remaining = take_greedy(remaining, coins_desc, avail, out, locked)
    remaining = take_greedy(remaining, rolls_desc, avail, out, locked)

    return out, remaining

def rows_report(open_c, close_c, retrait_c, restant_c):
    rows = []
    t_open = t_close = t_ret = t_res = 0

    for k in DISPLAY_ORDER:
        o = int(open_c.get(k, 0))
        c = int(close_c.get(k, 0))
        r = int(retrait_c.get(k, 0))
        s = int(restant_c.get(k, 0))

        rows.append({
            "Dénomination": k,
            "OPEN": o,
            "CLOSE": c,
            "RETRAIT": r,
            "RESTANT": s,
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
if "locked_retrait" not in st.session_state:
    st.session_state.locked_retrait = {}

if "show_report" not in st.session_state:
    st.session_state.show_report = False

if "report_payload" not in st.session_state:
    st.session_state.report_payload = None

# ================== UI ==================
st.title("Caisse — Calcul retrait pour revenir à la cible")
st.caption("CLOSE → l’app propose RETRAIT (favorise 100/50/20), tu ajustes (-/+) et tu imprimes le rapport.")

st.divider()

# --------- META ---------
st.header("Informations")
m1, m2, m3, m4 = st.columns([1.8, 1.0, 1.1, 1.1])

with m1:
    cashier = st.text_input("Nom du caissier / caissière", value="")
with m2:
    register_no = st.selectbox("Caisse #", [1, 2, 3], index=0)
with m3:
    rep_date = st.date_input("Date", value=date.today())
with m4:
    rep_time = st.time_input("Heure", value=datetime.now(TZ).time().replace(second=0, microsecond=0))

TARGET = int(st.number_input("Montant cible à laisser ($)", min_value=0, step=10, value=200)) * 100

st.divider()

# --------- OPEN (2 colonnes) ---------
st.header("OPEN — Fond de caisse (matin)")
open_counts = {}
o1, o2 = st.columns(2)
for i, k in enumerate(DISPLAY_ORDER):
    with (o1 if i % 2 == 0 else o2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"open_{k}")
st.info("TOTAL OPEN : " + cents_to_str(total_cents(open_counts)))

st.divider()

# --------- CLOSE (2 colonnes) ---------
st.header("CLOSE — Comptage fin de journée")
close_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(DISPLAY_ORDER):
    with (c1 if i % 2 == 0 else c2):
        close_counts[k] = st.number_input(f"{k} (CLOSE)", min_value=0, step=1, value=0, key=f"close_{k}")
total_close = total_cents(close_counts)
st.success("TOTAL CLOSE : " + cents_to_str(total_close))

st.divider()

# --------- RETRAIT ---------
st.header("RETRAIT — Pour revenir à la cible")
diff = total_close - TARGET
st.write("Cible:", f"**{cents_to_str(TARGET)}**")
st.write("À retirer (CLOSE - cible):", f"**{cents_to_str(diff)}**")

# Allowed (2 colonnes)
st.subheader("Types autorisés (pour le retrait)")
allowed = []
a1, a2 = st.columns(2)
for i, k in enumerate(DISPLAY_ORDER):
    with (a1 if i % 2 == 0 else a2):
        if st.checkbox(k, value=True, key=f"allow_{k}"):
            allowed.append(k)

# Buttons
b1, b2, b3 = st.columns([1.2, 1.2, 2.6])
with b1:
    if st.button("PROPOSER RETRAIT"):
        st.session_state.locked_retrait = {}
        st.rerun()
with b2:
    if st.button("RÉINITIALISER AJUSTEMENTS"):
        st.session_state.locked_retrait = {}
        st.rerun()

# Calcul
retrait_counts = {k: 0 for k in DENOMS}
restant_counts = dict(close_counts)

if diff <= 0:
    st.warning("La caisse est sous la cible (ou égale). Ici il faudrait AJOUTER, pas retirer.")
else:
    if not allowed:
        st.error("Choisis au moins un type autorisé.")
    else:
        # clamp locked before computing
        st.session_state.locked_retrait = clamp_locked(st.session_state.locked_retrait, close_counts)
        locked = dict(st.session_state.locked_retrait)

        retrait_counts, remaining = suggest_retrait(diff, allowed, close_counts, locked)
        retrait_total = total_cents(retrait_counts)

        if remaining == 0:
            st.success("RETRAIT total proposé: " + cents_to_str(retrait_total))
        elif remaining < 0:
            st.warning("Tu as dépassé la cible de retrait de " + cents_to_str(-remaining) + " (manuel trop haut).")
        else:
            st.warning("Impossible de couvrir exactement. Reste non couvert: " + cents_to_str(remaining))

        st.subheader("Ajuster le retrait (ATM +/-)")
        st.caption("Cliquer ➖/➕ verrouille une dénomination; le reste se recalcule automatiquement.")

        for k in DISPLAY_ORDER:
            if k not in allowed:
                continue

            q = int(retrait_counts.get(k, 0))
            max_avail = int(close_counts.get(k, 0))

            row = st.columns([2.8, 1.0, 1.0, 1.6, 1.6])
            row[0].write(k)
            minus = row[1].button("➖", key=f"minus_{k}")
            plus = row[2].button("➕", key=f"plus_{k}")
            row[3].write(f"RETRAIT: **{q}**")
            row[4].write(f"Dispo: {max_avail}")

            if minus or plus:
                new_locked = dict(st.session_state.locked_retrait)

                # start from current suggested if not already locked
                if k not in new_locked:
                    new_locked[k] = q

                if minus:
                    new_locked[k] = int(new_locked[k]) - 1
                if plus:
                    new_locked[k] = int(new_locked[k]) + 1

                if new_locked[k] < 0:
                    new_locked[k] = 0
                if new_locked[k] > max_avail:
                    new_locked[k] = max_avail

                st.session_state.locked_retrait = new_locked
                st.rerun()

        restant_counts = sub_counts(close_counts, retrait_counts)
        st.divider()
        st.header("RESTANT — Ce qui reste dans la caisse")
        st.info("RESTANT total: " + cents_to_str(total_cents(restant_counts)))

st.divider()

# --------- RAPPORT ---------
st.header("Rapport imprimable")
rA, rB = st.columns([1, 1])
with rA:
    gen_report = st.button("GÉNÉRER LE RAPPORT")
with rB:
    clear_report = st.button("EFFACER")

if clear_report:
    st.session_state.show_report = False
    st.session_state.report_payload = None

if gen_report:
    now_local = datetime.now(TZ)
    dt_str = f"{rep_date.isoformat()} {rep_time.strftime('%H:%M')}"

    meta_lines = [
        f"Caisse #: {register_no}",
        f"Caissier(ère): {cashier.strip() if cashier.strip() else '—'}",
        f"Date/Heure (saisie): {dt_str}",
        "Généré le " + now_local.strftime("%Y-%m-%d %H:%M"),
    ]

    rows = rows_report(open_counts, close_counts, retrait_counts, restant_counts)
    st.session_state.report_payload = {"rows": rows, "meta": meta_lines}
    st.session_state.show_report = True

if st.session_state.show_report and st.session_state.report_payload:
    html = build_print_html(
        st.session_state.report_payload["rows"],
        st.session_state.report_payload["meta"],
    )
    components.html(html, height=600, scrolling=True)

