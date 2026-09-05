"""Tableau de bord Streamlit de pilotage du portefeuille client.

Permet de charger un fichier CSV (ou un ZIP contenant un CSV), d'appliquer
des filtres dynamiques, et de visualiser les segmentations, indicateurs
comportementaux et affinitaires du portefeuille.
"""

import gc
import io
import time
import zipfile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import polars as pl
import streamlit as st

# CONFIG
st.set_page_config(page_title="Portefeuille Client — Pilotage", layout="wide", page_icon="🏦")

# --- Palette "banque premium" : sobre, vert en accent seulement (pas dominant) ---
COLOR_PRIMARY = "#16332B"      # vert profond, réservé aux accents/bandeau
COLOR_PRIMARY_LIGHT = "#25493D"
COLOR_ACCENT = "#B08D57"       # or/bronze
COLOR_BG = "#F7F7F5"           # gris-ivoire très clair
COLOR_CARD_BG = "#FFFFFF"
COLOR_TEXT = "#26302B"         # charcoal, pas vert, pour le texte courant
COLOR_MUTED = "#6B7570"
COLOR_BORDER = "#E4E2DA"

PALETTE_SEQ = [
    "#B08D57", "#2C3E42", "#6B8E7F", "#8C6A3F",
    "#16332B", "#C9B27C", "#4A5A54", "#A9744F",
]
PALETTE_SCALE = ["#F7F7F5", "#C9B27C", "#B08D57", "#6B8E7F", "#16332B"]

pio.templates["banque_premium"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color=COLOR_TEXT, size=13),
        title=dict(font=dict(family="Source Serif 4, serif", size=16, color=COLOR_TEXT)),
        paper_bgcolor="#FBFAF7",
        plot_bgcolor="#FBFAF7",
        colorway=PALETTE_SEQ,
        xaxis=dict(gridcolor=COLOR_BORDER, zerolinecolor=COLOR_BORDER),
        yaxis=dict(gridcolor=COLOR_BORDER, zerolinecolor=COLOR_BORDER),
        legend=dict(font=dict(size=12)),
    )
)
pio.templates.default = "banque_premium"

FONT_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Source+Serif+4:wght@500;600;700"
    "&family=Inter:wght@400;500;600;700&display=swap"
)

st.markdown(f"""
<style>
    @import url('{FONT_IMPORT_URL}');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        color: {COLOR_TEXT};
    }}

    .stApp {{
        background-color: {COLOR_BG};
    }}

    h1 {{
        font-family: 'Source Serif 4', serif !important;
        font-weight: 600 !important;
    }}
    h2, h3 {{
        font-family: 'Inter', sans-serif !important;
        color: {COLOR_TEXT} !important;
        font-weight: 600 !important;
        font-size: 1.05rem !important;
    }}

    /* Bandeau institutionnel (en-tête seulement) */
    .bank-header {{
        background: linear-gradient(120deg, {COLOR_PRIMARY} 0%, {COLOR_PRIMARY_LIGHT} 100%);
        padding: 20px 32px;
        border-radius: 6px;
        margin-bottom: 24px;
        border-left: 4px solid {COLOR_ACCENT};
    }}
    .bank-header h1 {{
        color: #FFFFFF !important;
        font-size: 1.35rem !important;
        margin: 0 !important;
        letter-spacing: 0.2px;
    }}
    .bank-header p {{
        color: #D7D3C6;
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        font-family: 'Inter', sans-serif;
    }}

    /* Titres de section : petit accent gauche, pas de bordure pleine largeur */
    div[data-testid="stMarkdownContainer"] h3 {{
        border-left: 3px solid {COLOR_ACCENT};
        padding-left: 10px;
        margin-top: 8px !important;
    }}

    /* Cartes metric : chiffres discrets + alignement garanti même si le
       libellé passe sur 2 lignes */
    [data-testid="stMetric"] {{
        background-color: {COLOR_CARD_BG};
        border: 1px solid {COLOR_BORDER};
        border-left: 3px solid {COLOR_ACCENT};
        border-radius: 4px;
        padding: 12px 14px;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLOR_TEXT} !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.25 !important;
    }}
    [data-testid="stMetricLabel"] p {{
        white-space: normal !important;
        overflow-wrap: break-word !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {COLOR_TEXT} !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        line-height: 1.3 !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.72rem !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.2 !important;
    }}
    [data-testid="stMetricDelta"] div {{
        white-space: normal !important;
        overflow-wrap: break-word !important;
    }}

    /* Colonnes strictement égales : évite que le contenu (texte long,
       delta tronqué) ne pousse certaines cartes plus larges que d'autres */
    [data-testid="stHorizontalBlock"] {{
        align-items: stretch !important;
    }}
    [data-testid="column"] {{
        flex: 1 1 0 !important;
        min-width: 0 !important;
        width: 0 !important;
    }}
    [data-testid="stMetric"] {{
        height: 100%;
    }}

    /* Graphiques : carte crème cohérente au lieu d'un blanc pur qui tranche */
    [data-testid="stPlotlyChart"] {{
        background-color: #FBFAF7;
        border: 1px solid {COLOR_BORDER};
        border-radius: 4px;
        padding: 8px;
    }}

    /* Sidebar : fond clair, accent vert discret, pas de fond plein vert */
    [data-testid="stSidebar"] {{
        background-color: #FBFAF8;
        border-right: 1px solid {COLOR_BORDER};
    }}
    [data-testid="stSidebar"] * {{
        color: {COLOR_TEXT} !important;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: {COLOR_PRIMARY} !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        border-left: none !important;
        padding-left: 0 !important;
        border-bottom: 2px solid {COLOR_ACCENT};
        padding-bottom: 8px;
        margin-bottom: 14px !important;
    }}

    /* Widgets de filtre bien visibles : contour net + fond blanc distinct */
    [data-testid="stSidebar"] label {{
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        color: {COLOR_PRIMARY} !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background-color: #FFFFFF !important;
        border: 1.5px solid {COLOR_PRIMARY} !important;
        border-radius: 4px !important;
        box-shadow: none !important;
    }}
    [data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {{
        border-color: {COLOR_ACCENT} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
        margin-bottom: 4px !important;
    }}
    [data-testid="stSidebar"] .stSelectbox {{
        margin-bottom: 16px !important;
    }}

    /* Boutons */
    .stDownloadButton button, .stButton button {{
        background-color: {COLOR_ACCENT} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
    }}
    .stDownloadButton button:hover, .stButton button:hover {{
        background-color: {COLOR_PRIMARY} !important;
    }}

    hr {{
        border-color: {COLOR_BORDER} !important;
    }}
</style>

<div class="bank-header">
    <h1>Pilotage du Portefeuille Client</h1>
    <p>Vue consolidée des segmentations, indicateurs comportementaux et affinitaires</p>
</div>
""", unsafe_allow_html=True)

# UPLOAD ZIP / CSV
upload_col, clear_col = st.columns([5, 1])
with upload_col:
    uploaded_file = st.file_uploader(
        "Déposez un fichier ZIP ou CSV (jusqu’à ~100 Mo, séparateur ;)",
        type=["zip", "csv"]
    )
with clear_col:
    st.write("")  # alignement vertical avec le file_uploader
    st.write("")
    clear_cache_clicked = st.button(
        "🔄 Vider le cache",
        help=(
            "Force un rechargement complet du fichier "
            "(ignore tout résultat déjà mis en cache)."
        ),
    )
    if clear_cache_clicked:
        st.cache_resource.clear()
        st.rerun()

# Colonnes réellement utilisées par ce dashboard : si le fichier réel en
# contient d'autres, elles ne sont même pas parsées (gain mémoire direct).
# NB : "segment_affinitaire" n'est plus utilisée — le segment affinitaire
# est désormais dérivé des colonnes TOP_. "age" a été ajoutée pour la
# répartition par tranche d'âge (renommez-la ici si votre colonne porte
# un autre nom dans le CSV).
USED_COLUMNS = [
    "client_id", "agence", "region", "grappe",
    "segmentation_marketing", "segmentation_comportementale",
    "seg_dig_auto", "age",
    "TOP_TERRITORIAL_ENGAGE", "TOP_OPTIMISATEUR_MULTIBANCARISE",
    "TOP_JOUEUR_INVESTISSEUR", "TOP_PRUDENT_INSTALLE",
    "TOP_PROFESSIONNEL_INDEPENDANT",
    "conseiller", "segmentation_principalisation",
]

# Types réduits pour les colonnes numériques : un flag 0/1 n'a pas besoin
# d'un Int64 (8 octets), Int8 (1 octet) suffit largement. seg_dig_auto est
# aussi un flag 0/1 entier -> Int8.
# Ces casts sont appliqués APRÈS la lecture complète du CSV (voir
# load_csv_stream / load_zip ci-dessous), avec strict=False : une valeur
# mal formée dans une colonne devient simplement null pour cette ligne-là,
# sans jamais annuler toute la colonne. "age" n'est pas ici : elle est
# nettoyée séparément juste après le chargement (gère les
# décimales/virgules/espaces).
DTYPE_OVERRIDES = {
    "client_id": pl.Int32,
    "seg_dig_auto": pl.Int8,
    "TOP_TERRITORIAL_ENGAGE": pl.Int8,
    "TOP_OPTIMISATEUR_MULTIBANCARISE": pl.Int8,
    "TOP_JOUEUR_INVESTISSEUR": pl.Int8,
    "TOP_PRUDENT_INSTALLE": pl.Int8,
    "TOP_PROFESSIONNEL_INDEPENDANT": pl.Int8,
}


def _scan_and_select(source):
    """Lit un CSV en mode "lazy" et projette sur USED_COLUMNS.

    Essaie d'abord SANS `ignore_errors` (chemin rapide de Polars, qui
    n'est pas ralenti par la logique de tolérance aux erreurs) ; ne
    retombe sur `ignore_errors=True` (plus lent, mais tolérant) que si
    la première tentative échoue réellement. Sur un fichier propre,
    c'est le principal gain de vitesse possible ici : le fait de ne
    lire que 15 colonnes sur 16 (voir USED_COLUMNS) n'a en soi qu'un
    effet marginal.

    Note : factorisée ici (DRY) plutôt que dupliquée dans load_csv_stream
    et load_zip. Revers de la médaille — voir la note sur le cache dans
    load_csv_stream ci-dessous — si cette fonction change seule sans que
    load_csv_stream/load_zip ne changent, Streamlit peut ne pas invalider
    leur cache automatiquement : utiliser le bouton "🔄 Vider le cache"
    de l'interface après une modification de cette fonction.
    """
    for ignore_errors in (False, True):
        try:
            lf = pl.scan_csv(source, separator=";", ignore_errors=ignore_errors)
            cols_to_use = [c for c in lf.columns if c in USED_COLUMNS]
            if cols_to_use:
                lf = lf.select(cols_to_use)
            return lf.collect()
        except Exception:
            if ignore_errors:
                raise
            if hasattr(source, "seek"):
                source.seek(0)
    raise RuntimeError("Lecture CSV impossible.")  # inatteignable en pratique


@st.cache_resource
def load_csv_stream(file_bytes):
    # NOTE IMPORTANTE SUR LE CACHE : Streamlit invalide le cache d'une
    # fonction @st.cache_resource quand LE CODE DE CETTE FONCTION change,
    # mais ne suit pas les changements d'une fonction helper appelée à
    # l'intérieur si le corps de CETTE fonction reste identique. Toute la
    # logique de lecture/nettoyage est donc écrite directement ici (et
    # dupliquée dans load_zip ci-dessous) plutôt que factorisée dans une
    # fonction externe, pour qu'une future modification force bien un
    # nouveau calcul au lieu de servir un résultat périmé.
    df_full = _scan_and_select(file_bytes)
    cast_exprs = [
        pl.col(col_name).cast(dtype, strict=False).alias(col_name)
        for col_name, dtype in DTYPE_OVERRIDES.items()
        if col_name in df_full.columns
    ]
    if cast_exprs:
        df_full = df_full.with_columns(cast_exprs)
    df_full = df_full.rechunk()

    gc.collect()
    return df_full, timings


_UPLOADED_FILE_TYPE = "streamlit.runtime.uploaded_file_manager.UploadedFile"


@st.cache_resource(
    hash_funcs={_UPLOADED_FILE_TYPE: lambda f: f"{f.name}_{f.size}"}
)
def load_zip(file):

    with zipfile.ZipFile(file) as z:
        csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
        if csv_name is None:
            raise ValueError("Aucun CSV trouvé dans le ZIP.")
        with z.open(csv_name) as csv_file:
            # Une seule lecture en bytes : scan_csv a besoin d'une source
            # "seekable", ce que l'objet ZipExtFile ne garantit pas — on
            # décompresse donc une fois en mémoire puis on l'enveloppe
            # dans un BytesIO pour Polars.
            csv_bytes = csv_file.read()
        df_full = _scan_and_select(io.BytesIO(csv_bytes))
        del csv_bytes
        cast_exprs = [
            pl.col(col_name).cast(dtype, strict=False).alias(col_name)
            for col_name, dtype in DTYPE_OVERRIDES.items()
            if col_name in df_full.columns
        ]
        if cast_exprs:
            df_full = df_full.with_columns(cast_exprs)
        df_full = df_full.rechunk()

        gc.collect()
        return df_full, {}


# MAIN LOGIC
if uploaded_file is not None:

    try:
        # Chargement
        if uploaded_file.name.lower().endswith(".zip"):
            df, _ = load_zip(uploaded_file)
        else:
            df, _ = load_csv_stream(uploaded_file)
        # NOTE VITESSE : rechunk()/gc.collect() sont faits UNE SEULE FOIS,
        # à l'intérieur des fonctions @st.cache_resource ci-dessus — donc
        # uniquement lors d'un vrai chargement, jamais à chaque interaction
        # (chaque clic sur un filtre relance ce script en entier ; les
        # refaire ici à chaque fois coûtait du temps pour rien puisque `df`
        # vient alors du cache, déjà nettoyé).
        # Nettoyage texte (désactivable pour économiser la mémoire sur gros fichiers)
        clean_text = st.sidebar.checkbox("Nettoyer les espaces en trop (texte)", value=True)

        # NOTE VITESSE : ce bloc (nettoyage de "age", trim texte, passage en
        # Categorical) portait sur les 700k lignes et se relançait à CHAQUE
        # interaction (chaque clic sur un filtre relance tout le script),
        # alors que son résultat ne dépend que du fichier chargé et de la
        # case à cocher ci-dessus. On le mémorise donc dans st.session_state
        # et on ne le recalcule que si le fichier ou la case a changé.
        prep_key = (uploaded_file.name, uploaded_file.size, clean_text)
        if st.session_state.get("_last_file_key") != (uploaded_file.name, uploaded_file.size):
            st.session_state.pop("_filter_values_cache", None)
            st.session_state.pop("_export_csv", None)
            st.session_state["_last_file_key"] = (uploaded_file.name, uploaded_file.size)
        prep_just_recomputed = st.session_state.get("_prep_key") != prep_key
        if prep_just_recomputed:
            df_prepared = df

            # Nettoyage robuste de la colonne "age" : lue en texte brut,
            # elle peut contenir des formats variés ("35", "35.0", "35,0",
            # " 35 ", valeurs vides...). On caste en float d'abord (accepte
            # les décimales) avant l'entier, sans jamais faire échouer
            # toute la colonne pour quelques valeurs mal formées.
            if "age" in df_prepared.columns:
                df_prepared = df_prepared.with_columns(
                    pl.col("age")
                    .cast(pl.Utf8, strict=False)
                    .str.strip_chars()
                    .str.replace_all(",", ".")
                    .cast(pl.Float64, strict=False)
                    .round(0)
                    .cast(pl.Int16, strict=False)
                    .alias("age")
                )
                age_diag["nb_valides"] = df_prepared["age"].drop_nulls().len()

            if clean_text:
                df_prepared = df_prepared.with_columns([
                    pl.col(pl.Utf8).str.strip_chars()
                ])

            # Colonnes à faible cardinalité (peu de valeurs distinctes
            # répétées sur des centaines de milliers de lignes) : passage
            # en Categorical pour diviser fortement l'empreinte mémoire.
            low_cardinality_cols = [
                "agence", "region", "grappe", "segmentation_marketing",
                "segmentation_comportementale", "conseiller",
                "segmentation_principalisation",
            ]
            cat_cast_exprs = [
                pl.col(c).cast(pl.Categorical)
                for c in low_cardinality_cols
                if c in df_prepared.columns
            ]
            if cat_cast_exprs:
                df_prepared = df_prepared.with_columns(cat_cast_exprs)

            st.session_state["_prep_key"] = prep_key
            st.session_state["_prep_df"] = df_prepared

        df = st.session_state["_prep_df"]

        with st.expander("⏱️ Performance de la préparation des données"):
            if prep_just_recomputed:
                st.caption(
                    "Recalculée à l'instant (nouveau fichier ou case "
                    "à cocher modifiée) :"
                )
            else:
                st.caption("Réutilisée depuis le cache de session (inchangée).")
            for step_name, seconds in st.session_state["_prep_timings"].items():
                st.write(f"{step_name} : {seconds:.2f} s")

        st.success("Chargement terminé ✔️")

        # FILTRES DYNAMIQUES
        st.sidebar.header("🔍 Filtres globaux")
        st.sidebar.caption("Sélection multiple possible — laissez vide pour tout inclure.")

        df_filtered = df

        def add_filter(col_name, label):
            nonlocal_df = df_filtered
            if col_name in df.columns:
                # Cascade : les valeurs proposées viennent du DataFrame déjà
                # filtré par les sélections précédentes, pas du DataFrame complet
                # Les valeurs d'un filtre peuvent être coûteuses à recalculer.
                # Cache session : invalidé quand le fichier change ou quand le filtre
                # précédent modifie réellement le DataFrame en cascade.
                filter_cache = st.session_state.setdefault("_filter_values_cache", {})
                cache_key = (
                    uploaded_file.name,
                    uploaded_file.size,
                    col_name,
                    tuple(
                        (k, tuple(map(str, st.session_state.get(f"filter_{k}_{uploaded_file.name}_{uploaded_file.size}", []))))
                        for k in ["region", "agence", "grappe", "segmentation_marketing", "conseiller"]
                        if k != col_name
                    ),
                )
                if cache_key in filter_cache:
                    values = filter_cache[cache_key]
                else:
                    values = nonlocal_df[col_name].unique().to_list()
                    values = [v for v in values if v is not None]
                    values = sorted([str(v) for v in values])
                    filter_cache[cache_key] = values

                widget_key = f"filter_{col_name}_{uploaded_file.name}_{uploaded_file.size}"
                # Si une sélection précédente n'existe plus dans la liste
                # cascadée (ex: agence absente de la région choisie), on la
                # retire pour éviter une erreur Streamlit.
                if widget_key in st.session_state:
                    valid_selection = [v for v in st.session_state[widget_key] if v in values]
                    if valid_selection != st.session_state[widget_key]:
                        st.session_state[widget_key] = valid_selection
                selected = st.sidebar.multiselect(label, values, key=widget_key)
                if selected:
                    return nonlocal_df.filter(pl.col(col_name).cast(pl.Utf8).is_in(selected))
            return nonlocal_df

        df_filtered = add_filter("region", "Région")
        df_filtered = add_filter("agence", "Agence")
        df_filtered = add_filter("grappe", "Grappe")
        df_filtered = add_filter("segmentation_marketing", "Segment Marketing")
        df_filtered = add_filter("conseiller", "Conseiller")
        total = len(df_filtered)

        # --- Agrégations calculées UNE SEULE FOIS, réutilisées partout ---
        # (avant: certaines colonnes étaient recomptées 2 à 3 fois séparément
        # pour les KPIs et les graphiques, ce qui ralentissait chaque filtre)

        # Agrégations uniquement sur les petites tables nécessaires aux graphiques.
        # On évite de créer des DataFrames intermédiaires inutiles.
        seg_mkt_counts = (
            df_filtered["segmentation_marketing"].value_counts(sort=True)
            if "segmentation_marketing" in df_filtered.columns and total > 0
            else None
        )

        seg_comp_counts = (
            df_filtered["segmentation_comportementale"].value_counts(sort=True)
            if "segmentation_comportementale" in df_filtered.columns and total > 0
            else None
        )

        # Segment affinitaire : dérivé des colonnes TOP_ (le nombre de
        # clients à 1 sur chaque flag), et non plus de la colonne
        # "segmentation_affinitaire" qui n'est plus utilisée du tout.
        top_columns = [
            ("TOP_TERRITORIAL_ENGAGE", "Territorial Engagé"),
            ("TOP_OPTIMISATEUR_MULTIBANCARISE", "Optimisateur Multibancarisé"),
            ("TOP_JOUEUR_INVESTISSEUR", "Joueur Investisseur"),
            ("TOP_PRUDENT_INSTALLE", "Prudent Installé"),
            ("TOP_PROFESSIONNEL_INDEPENDANT", "Professionnel Indépendant"),
        ]
        top_present = [(c, l) for c, l in top_columns if c in df_filtered.columns]

        seg_aff_counts = None
        if top_present and total > 0:
            top_names = [label for _, label in top_present]
            top_exprs = [
                pl.col(col_name).cast(pl.Int8, strict=False).sum().alias(label)
                for col_name, label in top_present
            ]
            top_totals = df_filtered.select(top_exprs).row(0)
            seg_aff_counts = (
                pl.DataFrame({
                    "segment_affinitaire": top_names,
                    "count": list(top_totals),
                })
                .sort("count", descending=True)
            )

        seg_prin_counts = None
        if "segmentation_principalisation" in df_filtered.columns and total > 0:
            seg_prin_counts = df_filtered["segmentation_principalisation"].value_counts()

        # Répartition par tranche d'âge
        age_counts = None
        nb_age_renseigne = 0
        if "age" in df_filtered.columns and total > 0:
            nb_age_renseigne = df_filtered["age"].is_not_null().sum()
            if nb_age_renseigne > 0:
                age_counts = (
                    df_filtered
                    .select(
                        pl.when(pl.col("age") < 25).then(pl.lit("< 25 ans"))
                        .when(pl.col("age") < 35).then(pl.lit("25-34 ans"))
                        .when(pl.col("age") < 45).then(pl.lit("35-44 ans"))
                        .when(pl.col("age") < 55).then(pl.lit("45-54 ans"))
                        .when(pl.col("age") < 65).then(pl.lit("55-64 ans"))
                        .otherwise(pl.lit("65 ans et +"))
                        .alias("tranche_age")
                    )
                    .filter(pl.col("tranche_age").is_not_null())
                    .group_by("tranche_age")
                    .len()
                    .rename({"len": "count"})
                    .sort("count", descending=True)
                )

        # KPIs
        st.subheader("📊 KPIs Principaux")

        k1, k2, k3, k4 = st.columns(4)

        # 1. Clients uniques
        if "client_id" in df_filtered.columns:
            nb_clients = df_filtered["client_id"].n_unique()
        else:
            nb_clients = total
        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if seg_mkt_counts is not None:
            k2.metric("Segment Marketing", str(seg_mkt_counts["segmentation_marketing"][0]))
        else:
            k2.metric("Segment Marketing", "N/A")

        # 3. % Digital autonomes : seg_dig_auto est un flag entier 0/1
        if "seg_dig_auto" in df_filtered.columns:
            nb_dig = df_filtered["seg_dig_auto"].cast(pl.Int64, strict=False).sum() or 0
            pct_dig = (nb_dig / total) * 100 if total > 0 else 0
            k3.metric("% Digital Autonomes", f"{pct_dig:.1f}%")
        else:
            k3.metric("% Digital Autonomes", "N/A")

        # 4. Segment comportemental dominant + %
        if seg_comp_counts is not None:
            seg_comp_dom = seg_comp_counts["segmentation_comportementale"][0]
            pct_comp_dom = (seg_comp_counts["count"][0] / total) * 100
            k4.metric("Segment Comportemental", f"{seg_comp_dom}")
            k4.caption(f"{pct_comp_dom:.1f}% du portefeuille")
        else:
            k4.metric("Segment Comportemental", "N/A")

        # CARTES TOP_ (réutilise seg_aff_counts, pas de recomptage)
        if top_present and seg_aff_counts is not None and total > 0:
            st.subheader("🏅 Indicateurs TOP")
            top_cols_ui = st.columns(len(top_present))
            aff_lookup = dict(zip(
                seg_aff_counts["segment_affinitaire"].to_list(),
                seg_aff_counts["count"].to_list(),
            ))
            for (col_name, label), ui_col in zip(top_present, top_cols_ui):
                nb_top = aff_lookup.get(label, 0)
                pct_top = (nb_top / total) * 100
                ui_col.metric(label, f"{nb_top:,}".replace(",", " "))
                ui_col.caption(f"{pct_top:.1f}% du portefeuille")

        # SEGMENT AFFINITAIRE GLOBAL + RANG (basé sur les colonnes TOP_)
        st.subheader("🏆 Segment Affinitaire Dominant (TOP_) + Classement Global")

        if seg_aff_counts is not None and len(seg_aff_counts) > 0:
            seg_aff_dom_global = seg_aff_counts["segment_affinitaire"][0]
            pct_aff_global = (seg_aff_counts["count"][0] / total) * 100

            st.metric(
                label="Segment Affinitaire Dominant",
                value=str(seg_aff_dom_global)
            )
            st.caption(f"{pct_aff_global:.1f}% du portefeuille")

            df_rank_global = (
                seg_aff_counts
                .with_columns([
                    (pl.col("count") / total * 100).round(1).alias("% du portefeuille")
                ])
                .with_row_index("Rang", offset=1)
                .rename({
                    "segment_affinitaire": "Segment affinitaire (TOP_)",
                    "count": "Nb clients",
                })
                .select(["Rang", "Segment affinitaire (TOP_)", "Nb clients", "% du portefeuille"])
                .to_pandas()
            )
            st.dataframe(
                df_rank_global,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rang": st.column_config.NumberColumn("Rang", format="%d"),
                    "% du portefeuille": st.column_config.ProgressColumn(
                        "% du portefeuille", format="%.1f%%", min_value=0, max_value=100
                    ),
                    "Nb clients": st.column_config.NumberColumn("Nb clients", format="%d"),
                },
            )

        # RÉPARTITION PAR TRANCHE D'ÂGE + CLASSEMENT
        st.subheader("📅 Répartition par Tranche d'Âge + Classement")

        if age_counts is not None and len(age_counts) > 0:
            age_dom = age_counts["tranche_age"][0]
            pct_age_dom = (age_counts["count"][0] / nb_age_renseigne) * 100

            st.metric(
                label="Tranche d'Âge Dominante",
                value=str(age_dom)
            )
            st.caption(
                f"{pct_age_dom:.1f}% des clients avec âge renseigné "
                f"({nb_age_renseigne:,} sur {total:,})".replace(",", " ")
            )

            df_age_rank = (
                age_counts
                .with_columns([
                    (pl.col("count") / nb_age_renseigne * 100).round(1).alias("% du portefeuille")
                ])
                .with_row_index("Rang", offset=1)
                .rename({"tranche_age": "Tranche d'âge", "count": "Nb clients"})
                .select(["Rang", "Tranche d'âge", "Nb clients", "% du portefeuille"])
                .to_pandas()
            )
            st.dataframe(
                df_age_rank,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rang": st.column_config.NumberColumn("Rang", format="%d"),
                    "% du portefeuille": st.column_config.ProgressColumn(
                        "% du portefeuille", format="%.1f%%", min_value=0, max_value=100
                    ),
                    "Nb clients": st.column_config.NumberColumn("Nb clients", format="%d"),
                },
            )
        else:
            if "age" in df_filtered.columns:
                st.info(
                    f"Colonne 'age' trouvée mais aucune valeur numérique exploitable "
                    f"après nettoyage (0 valeur valide sur {total:,} lignes). "
                    f"Vérifiez le contenu réel de cette colonne dans le fichier."
                    .replace(",", " ")
                )
            else:
                st.info("Colonne 'age' absente du fichier chargé.")

        # GRAPHIQUES SEGMENTATIONS
        # Configuration légère : moins d'éléments UI côté navigateur.
        PLOTLY_CONFIG = {
            "displayModeBar": False,
            "responsive": True,
        }

        def compact_fig(fig):
            fig.update_layout(
                margin=dict(l=20, r=20, t=45, b=20),
                height=320,
            )
            return fig
        st.subheader("📈 Graphiques des Segmentations")

        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)
        g5, g6 = st.columns(2)
        g7, g8 = st.columns(2)

        # 1. Principalisation (Donut)
        with g1:
            if seg_prin_counts is not None:
                df_prin = seg_prin_counts.to_pandas()
                fig_prin = px.pie(
                    df_prin,
                    values="count",
                    names="segmentation_principalisation",
                    title="Segmentation Principalisation",
                    hole=0.45,
                    color_discrete_sequence=PALETTE_SEQ
                )
                st.plotly_chart(compact_fig(fig_prin), use_container_width=True, config=PLOTLY_CONFIG)

        # 2. Marketing (Donut)
        with g2:
            if seg_mkt_counts is not None:
                df_mkt = seg_mkt_counts.to_pandas()
                fig_mkt = px.pie(
                    df_mkt,
                    values="count",
                    names="segmentation_marketing",
                    title="Segmentation Marketing",
                    hole=0.45,
                    color_discrete_sequence=PALETTE_SEQ
                )
                st.plotly_chart(compact_fig(fig_mkt), use_container_width=True, config=PLOTLY_CONFIG)

        # 3. Affinitaire TOP_ (Barres)
        with g3:
            if seg_aff_counts is not None:
                df_aff_bar = seg_aff_counts.to_pandas()
                fig_aff_bar = px.bar(
                    df_aff_bar,
                    x="segment_affinitaire",
                    y="count",
                    title="Segments Affinitaires TOP_ (Classement)",
                    text_auto=True,
                    color="count",
                    color_continuous_scale=PALETTE_SCALE
                )
                st.plotly_chart(compact_fig(fig_aff_bar), use_container_width=True, config=PLOTLY_CONFIG)

        # 4. Affinitaire TOP_ (Donut)
        with g4:
            if seg_aff_counts is not None:
                df_aff_donut = seg_aff_counts.to_pandas()
                fig_aff_donut = px.pie(
                    df_aff_donut,
                    values="count",
                    names="segment_affinitaire",
                    title="Répartition Affinitaire (TOP_)",
                    hole=0.45,
                    color_discrete_sequence=PALETTE_SEQ
                )
                st.plotly_chart(compact_fig(fig_aff_donut), use_container_width=True, config=PLOTLY_CONFIG)

        # 5. Comportementale (Barres)
        with g5:
            if seg_comp_counts is not None:
                df_comp_bar = seg_comp_counts.to_pandas()
                fig_comp = px.bar(
                    df_comp_bar,
                    x="segmentation_comportementale",
                    y="count",
                    title="Segmentation Comportementale",
                    text_auto=True,
                    color="count",
                    color_continuous_scale=PALETTE_SCALE
                )
                st.plotly_chart(compact_fig(fig_comp), use_container_width=True, config=PLOTLY_CONFIG)

        # 6. Heatmap Principalisation × Marketing
        with g6:
            has_prin = "segmentation_principalisation" in df_filtered.columns
            has_mkt = "segmentation_marketing" in df_filtered.columns
            if has_prin and has_mkt and total > 0:
                df_cross = (
                    df_filtered
                    .group_by(["segmentation_principalisation", "segmentation_marketing"])
                    .count()
                    .to_pandas()
                )

                fig_cross = px.density_heatmap(
                    df_cross,
                    x="segmentation_principalisation",
                    y="segmentation_marketing",
                    z="count",
                    title="Croisement Principalisation × Marketing",
                    color_continuous_scale=PALETTE_SCALE
                )
                st.plotly_chart(compact_fig(fig_cross), use_container_width=True, config=PLOTLY_CONFIG)

        # 7. Répartition par tranche d'âge (Barres, ordre chronologique)
        with g7:
            if age_counts is not None:
                age_order = [
                    "< 25 ans", "25-34 ans", "35-44 ans",
                    "45-54 ans", "55-64 ans", "65 ans et +",
                ]
                df_age_bar = age_counts.to_pandas()
                df_age_bar["tranche_age"] = pd.Categorical(
                    df_age_bar["tranche_age"], categories=age_order, ordered=True
                )
                df_age_bar = df_age_bar.sort_values("tranche_age")
                fig_age = px.bar(
                    df_age_bar,
                    x="tranche_age",
                    y="count",
                    title="Répartition par Tranche d'Âge",
                    text_auto=True,
                    color="count",
                    color_continuous_scale=PALETTE_SCALE
                )
                st.plotly_chart(compact_fig(fig_age), use_container_width=True, config=PLOTLY_CONFIG)

        # EXPORT
        # OPTIMISATION IMPORTANTE :
        # avant, export_csv(df_filtered) était exécuté à chaque rerun,
        # même si l'utilisateur ne cliquait jamais sur Télécharger.
        # Ici, on prépare le CSV uniquement après le clic.
        if total > 0:
            if st.button(
                f"💾 Préparer le téléchargement des {total:,} lignes filtrées".replace(",", " "),
                use_container_width=True,
                key="prepare_export"
            ):
                export_buffer = io.BytesIO()
                df_filtered.write_csv(export_buffer, separator=";")
                st.session_state["_export_csv"] = export_buffer.getvalue()

            if "_export_csv" in st.session_state:
                st.download_button(
                    "⬇️ Télécharger le CSV",
                    data=st.session_state["_export_csv"],
                    file_name="export_filtre.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_export"
                )
        else:
            st.warning("Aucune ligne à exporter avec les filtres actuels.")

        # Profiling : temps Python/rendu du dashboard.
        dashboard_timings["00 - Chargement/préparation (hors rerun)"] = sum(load_timings.values()) + sum(
            st.session_state.get("_prep_timings", {}).values()
        )
        dashboard_timings["TOTAL script mesuré"] = time.perf_counter() - dashboard_t0

        with st.expander("🔬 Profilage détaillé du dashboard", expanded=True):
            st.write("Les temps ci-dessous permettent de distinguer le chargement des données du rendu Streamlit.")
            for name, seconds in dashboard_timings.items():
                st.write(f"{name} : {seconds:.3f} s")

    except Exception as e:
        st.error(f"Erreur : {e}")

else:
    st.info("⏳ En attente d’un fichier ZIP ou CSV…")
