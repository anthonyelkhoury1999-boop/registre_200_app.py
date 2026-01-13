import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date, time as dtime

st.set_page_config(page_title="Caisse — Retour à 200$", layout="centered")

# --- Protection par mot de passe ---
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
# --- Fin protection ---

# ------------------ CONFIG ------------------
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

ORDER = [
    "Billet 100 $", "Billet 50 $", "Billet 20 $", "Billet 10 $", "Billet 5 $",
    "Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $",
    "Rouleau 2 $ (25) — 50 $", "Rouleau 1 $ (25) — 25 $", "Rouleau 0,25 $ (40) — 10 $",
    "Rouleau 0,10 $ (50) — 5 $", "Rouleau 0,05 $ (40) — 2 $",
]

BILLS = ["Billet 100 $", "Billet 50 $", "Billet 20 $", "Billet 10 $", "Billet 5 $"]
COINS = ["Pièce 2 $", "Pièce 1 $", "Pièce 0,25 $", "Pièce 0,10 $", "Pièce 0,05 $"]
ROLLS = [
    "Rouleau 2 $ (25) — 50 $",
    "Rouleau 1 $ (25) — 25 $",
    "Rouleau 0,25 $ (40) — 10 $",
    "Rouleau 0,10 $ (50) — 5 $",
    "Rouleau 0,05 $ (40) — 2 $",
]

DEFAULT_TARGET = 20000  # 200.00$

# ------------------ HELPERS ------------------
def cents_to_str(c: int) -> str:
    return f"{c/100:.2f} $"


def total_cents(counts: dict) -> int:
    return sum(int(counts.get(k, 0)) * DENOMS[k] for k in DENOMS)


def add_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in DENOMS}


def sub_counts(a: dict, b: dict) -> dict:
    return {k: int(a.get(k, 0)) - int(b.get(k, 0)) for k in DENOMS}


def clamp_locked(locked: dict, max_available: dict) -> dict:
    """Ensure 0 <= locked[k] <= max_available[k] for all locked keys."""
    out = dict(locked)
    for k in list(out.keys()):
        out[k] = int(out[k])
        if out[k] < 0:
            out[k] = 0
        if out[k] > int(max_available.get(k, 0)):
            out[k] = int(max_available.get(k, 0))
    return out


def _priority_sort(allowed: list) -> list:
    """
    Favorise les billets (gros->petit), puis les pièces (gros->petit),
    et met les rouleaux en DERNIER (donc "rarement" utilisés).
    """
    allowed_set = set(allowed)

    bills_desc = [k for k in BILLS if k in allowed_set]
    bills_desc = sorted(bills_desc, key=lambda x: DENOMS[x], reverse=True)

    coins_desc = [k for k in COINS if k in allowed_set]
    coins_desc = sorted(coins_desc, key=lambda x: DENOMS[x], reverse=True)

    rolls_desc = [k for k in ROLLS if k in allowed_set]
    rolls_desc = sorted(rolls_desc, key=lambda x: DENOMS[x], reverse=True)

    # Bills first, coins second, rolls last
    return bills_desc + coins_desc + rolls_desc


BIG_BILLS = ["Billet 100 $", "Billet 50 $", "Billet 20 $"]
SMALL_BILLS = ["Billet 10 $", "Billet 5 $"]

def _take_greedy_from_list(remaining: int, keys: list, available: dict, out: dict, locked: dict) -> int:
    """Take as much as possible from keys (in given order), respecting available + already out + locked keys."""
    for k in keys:
        if remaining <= 0:
            break
        if k not in out:
            continue
        if k in locked:
            continue
        v = DENOMS[k]
        max_can_take = int(available.get(k, 0)) - int(out.get(k, 0))
        if max_can_take < 0:
            max_can_take = 0
        take = min(remaining // v, max_can_take)
        if take > 0:
            out[k] += int(take)
            remaining -= int(take) * v
    return remaining


def fill_prefer_big_bills_coins_last(target_withdraw_cents: int, allowed: list, available: dict, locked: dict):
    """
    OUT pour atteindre target_withdraw_cents.
    Priorités:
      1) 100/50/20 (gros billets) au max
      2) 10/5 seulement si nécessaire (rare)
      3) Pièces seulement pour "finir" le montant (rounding)
      4) Rouleaux en dernier recours (rarement)
    Retourne: (out_counts, remaining_cents_after)
    """
    out = {k: 0 for k in DENOMS}

    # appliquer locked (l'utilisateur force certaines quantités)
    for k, q in locked.items():
        out[k] = int(q)

    remaining = target_withdraw_cents - sum(out[k] * DENOMS[k] for k in DENOMS)
    if remaining < 0:
        return out, remaining  # locked trop haut = retrait dépassé

    allowed_set = set(allowed)

    # listes filtrées par "allowed"
    big_bills = [k for k in BIG_BILLS if k in allowed_set]
    small_bills = [k for k in SMALL_BILLS if k in allowed_set]
    coins_desc = [k for k in COINS if k in allowed_set]
    coins_desc = sorted(coins_desc, key=lambda x: DENOMS[x], reverse=True)  # 2$ -> 0.05
    rolls_desc = [k for k in ROLLS if k in allowed_set]
    rolls_desc = sorted(rolls_desc, key=lambda x: DENOMS[x], reverse=True)

    # 1) gros billets d'abord (100, 50, 20)
    remaining = _take_greedy_from_list(remaining, big_bills, available, out, locked)

    # 2) si encore gros reste, on essaye 10/5, mais "rarement" = seulement si ça aide à descendre
    #    (ici: greedy normal, mais après les gros billets)
    remaining = _take_greedy_from_list(remaining, small_bills, available, out, locked)

    # 3) pièces uniquement pour finir (rounding)
    remaining = _take_greedy_from_list(remaining, coins_desc, available, out, locked)

    # 4) rouleaux seulement en dernier recours
    if remaining > 0:
        remaining = _take_greedy_from_list(remaining, rolls_desc, available, out, locked)

    return out, remaining


def rows_report(open_c, close_c, retrait_c, restant_c):
    """
    Table: Dénomination | OPEN | CLOSE | RETRAIT | RESTANT (cible)
    plus TOTAL($) row
    """
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


def build_print_html(rows, meta_lines: list[str]):
    body = ""
    for r in rows:
        body += (
            "<tr>"
            f"<td>{r['Dénomination']}</td>"
            f"<td>{r['OPEN']}</td>"
            f"<td>{r['CLOSE']}</td>"
            f"<td>{r['RETRAIT']}</td>"
            f"<td>{r['RESTANT']}</td>"
            "</tr>"
        )

    meta_html = "<br/>".join([f"<div style='opacity:0.75; font-size:12px; margin-top:3px;'>{m}</div>" for m in meta_lines])

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
            <th>RESTANT (cible)</th>
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
        w.document.write('body{{font-family:Arial,sans-serif;padding:18px;}}');
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


# ------------------ STATE ------------------
if "locked_retrait" not in st.session_state:
    st.session_state.locked_retrait = {}
if "show_report" not in st.session_state:
    st.session_state.show_report = False
if "report_data" not in st.session_state:
    st.session_state.report_data = None

# ------------------ UI ------------------
st.title("Caisse — Calcul retrait pour revenir à la cible")
st.caption("Tu comptes CLOSE, l’app propose RETRAIT (favorise gros billets), tu ajustes (-/+) et tu imprimes le rapport.")

st.divider()

# ---- Infos caissier / meta ----
st.header("Infos (pour le rapport)")
m1, m2, m3, m4 = st.columns([1.6, 1.2, 1.2, 1.2])

with m1:
    cashier_name = st.text_input("Nom du caissier / caissière", value="", placeholder="Ex: Anthony")
with m2:
    register_no = st.selectbox("Caisse #", options=[1, 2, 3], index=0)
with m3:
    rep_date = st.date_input("Date", value=date.today())
with m4:
    rep_time = st.time_input("Heure", value=datetime.now().time().replace(second=0, microsecond=0))

st.divider()

target = st.number_input("Montant cible à laisser dans la caisse ($)", min_value=0, step=10, value=200)
TARGET = int(target) * 100

# 1) OPEN
st.header("1) OPEN — Fond de caisse (matin)")
open_counts = {}
o1, o2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (o1 if i % 2 == 0 else o2):
        open_counts[k] = st.number_input(k, min_value=0, step=1, value=0, key=f"open_{k}")

total_open = total_cents(open_counts)
st.info("TOTAL OPEN : " + cents_to_str(total_open))

st.divider()

# 2) CLOSE
st.header("2) CLOSE — Comptage fin de journée")
close_counts = {}
c1, c2 = st.columns(2)
for i, k in enumerate(ORDER):
    with (c1 if i % 2 == 0 else c2):
        close_counts[k] = st.number_input(f"{k} (CLOSE)", min_value=0, step=1, value=0, key=f"close_{k}")

total_close = total_cents(close_counts)
st.success("TOTAL CLOSE : " + cents_to_str(total_close))

st.divider()

# 3) RETRAIT suggestion
st.header("3) RETRAIT — Pour revenir à la cible")
diff = total_close - TARGET  # amount to remove to reach target
st.write("Cible: **" + cents_to_str(TARGET) + "**")
st.write("Écart (CLOSE - cible): **" + cents_to_str(diff) + "**")

if diff < 0:
    st.warning("La caisse est en dessous de la cible. Ici il faudrait AJOUTER de l’argent, pas retirer.")
    retrait_counts = {k: 0 for k in DENOMS}
    restant_counts = close_counts
else:
    st.caption("Choisis les types autorisés pour le retrait. (L’algo favorise billets, rouleaux en dernier.)")
    allowed = []
    a1, a2 = st.columns(2)
    for i, k in enumerate(ORDER):
        with (a1 if i % 2 == 0 else a2):
            if st.checkbox(k, value=True, key=f"allow_{k}"):
                allowed.append(k)

    col_btns = st.columns([1, 1, 2])
    with col_btns[0]:
        if st.button("PROPOSER RETRAIT"):
            st.session_state.locked_retrait = {}
            st.rerun()
    with col_btns[1]:
        if st.button("RÉINITIALISER AJUSTEMENTS"):
            st.session_state.locked_retrait = {}
            st.rerun()

    # clamp locked based on availability = close_counts
    st.session_state.locked_retrait = clamp_locked(st.session_state.locked_retrait, close_counts)

    if not allowed and diff > 0:
        st.error("Choisis au moins un type autorisé pour le retrait.")
        retrait_counts = {k: 0 for k in DENOMS}
        restant_counts = close_counts
    else:
        retrait_counts, remaining_after = fill_greedy_favor_bills_avoid_rolls(
            target_withdraw_cents=diff,
            allowed=allowed,
            available=close_counts,
            locked=st.session_state.locked_retrait
        )

        retrait_total = total_cents(retrait_counts)

        # IMPORTANT: on ne bloque pas — warning si pas exact
        if remaining_after != 0:
            st.warning(
                "Impossible de faire un retrait EXACT avec les types autorisés + la disponibilité.\n\n"
                f"Montant restant non couvert: **{cents_to_str(remaining_after)}**"
            )
            st.write("RETRAIT total actuel: **" + cents_to_str(retrait_total) + "**")
        else:
            st.success("RETRAIT total proposé: " + cents_to_str(retrait_total))

        st.subheader("Ajuster le retrait")
        st.caption("Clique ➖/➕ pour verrouiller une dénomination, puis l’app recalcule le reste automatiquement.")

        for k in ORDER:
            if k not in allowed:
                continue

            q = int(retrait_counts.get(k, 0))
            max_avail = int(close_counts.get(k, 0))

            row = st.columns([2.8, 1.1, 1.1, 1.4, 1.6])
            row[0].write(k)
            minus = row[1].button("➖", key=f"minus_{k}")
            plus = row[2].button("➕", key=f"plus_{k}")
            row[3].write(f"RETRAIT: **{q}**")
            row[4].write(f"Dispo: {max_avail}")

            if minus or plus:
                locked = dict(st.session_state.locked_retrait)

                # start lock from current suggested value
                if k not in locked:
                    locked[k] = q

                if minus:
                    locked[k] = int(locked[k]) - 1
                if plus:
                    locked[k] = int(locked[k]) + 1

                if locked[k] < 0:
                    locked[k] = 0
                if locked[k] > max_avail:
                    locked[k] = max_avail

                st.session_state.locked_retrait = locked
                st.rerun()

        # compute remaining in register after withdrawal
        restant_counts = sub_counts(close_counts, retrait_counts)
        restant_total = total_cents(restant_counts)

        st.divider()
        st.header("4) RESTANT — Ce qui reste dans la caisse (devrait = cible)")
        st.info("RESTANT total: " + cents_to_str(restant_total))

        if restant_total != TARGET:
            st.warning("⚠️ Le restant n’est pas égal à la cible. Ajuste le retrait ou autorise d’autres types.")
        else:
            st.success("✅ Restant = cible")

st.divider()

# 5) Report
st.header("5) Rapport imprimable")

colA, colB = st.columns([1, 1])
with colA:
    gen = st.button("GÉNÉRER LE RAPPORT FINAL")
with colB:
    clear = st.button("EFFACER LE RAPPORT")

if clear:
    st.session_state.show_report = False
    st.session_state.report_data = None

if gen:
    if diff >= 0:
        retrait_counts_final = retrait_counts if "retrait_counts" in locals() else {k: 0 for k in DENOMS}
        restant_counts_final = restant_counts if "restant_counts" in locals() else close_counts
    else:
        retrait_counts_final = {k: 0 for k in DENOMS}
        restant_counts_final = close_counts

    rows = rows_report(open_counts, close_counts, retrait_counts_final, restant_counts_final)

    # meta lines
    dt_str = f"{rep_date.isoformat()} {rep_time.strftime('%H:%M')}"
    meta_lines = [
        f"Caisse #: {register_no}",
        f"Caissier(ère): {cashier_name if cashier_name.strip() else '—'}",
        f"Date/Heure: {dt_str}",
        f"Météo: {weather if weather.strip() else '—'}",
        "Généré le " + datetime.now().strftime("%Y-%m-%d %H:%M"),
    ]

    st.session_state.report_data = {"rows": rows, "meta_lines": meta_lines}
    st.session_state.show_report = True

if st.session_state.show_report and st.session_state.report_data:
    html = build_print_html(st.session_state.report_data["rows"], st.session_state.report_data["meta_lines"])
    components.html(html, height=560, scrolling=True)
