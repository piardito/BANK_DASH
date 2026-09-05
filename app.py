import streamlit as st
import polars as pl
import zipfile
import io
import gc
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

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

PALETTE_SEQ = ["#B08D57", "#2C3E42", "#6B8E7F", "#8C6A3F", "#16332B", "#C9B27C", "#4A5A54", "#A9744F"]
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

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

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
uploaded_file = st.file_uploader(
    "Déposez un fichier ZIP ou CSV (jusqu’à ~100 Mo, séparateur ;)",
    type=["zip", "csv"]
)

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
# "age" n'est volontairement PAS forcée en Int16 ici : si une seule valeur
# du fichier n'est pas un entier pur (ex: "35.0", "35,0", espace, vide),
# le cast pendant la lecture CSV (avec ignore_errors) peut annuler TOUTE
# la colonne au lieu de juste la ligne fautive. Elle est donc lue en texte
# puis nettoyée/convertie proprement juste après le chargement.
DTYPE_OVERRIDES = {
    "client_id": pl.Int32,
    "seg_dig_auto": pl.Int8,
    "TOP_TERRITORIAL_ENGAGE": pl.Int8,
    "TOP_OPTIMISATEUR_MULTIBANCARISE": pl.Int8,
    "TOP_JOUEUR_INVESTISSEUR": pl.Int8,
    "TOP_PRUDENT_INSTALLE": pl.Int8,
    "TOP_PROFESSIONNEL_INDEPENDANT": pl.Int8,
}

def _read_csv_optimized(source):
    """Lit un CSV (bytes ou flux) en ne gardant que les colonnes utiles,
    avec des dtypes réduits, pour limiter le pic mémoire."""
    # Étape 1 : lire uniquement l'en-tête pour savoir quelles colonnes existent
    peek = pl.read_csv(source, separator=";", n_rows=0, ignore_errors=True)
    # IMPORTANT : on parcourt peek.columns (l'ordre RÉEL du fichier), pas
    # USED_COLUMNS. Passer à Polars une liste de colonnes dans un ordre
    # différent de celui du CSV source peut désaligner la lecture (des
    # valeurs associées au mauvais nom de colonne). USED_COLUMNS sert
    # uniquement de filtre "quelles colonnes garder", jamais d'ordre.
    cols_to_use = [c for c in peek.columns if c in USED_COLUMNS] or None

    if hasattr(source, "seek"):
        source.seek(0)  # remettre le curseur après le peek

    schema_overrides = {
        k: v for k, v in DTYPE_OVERRIDES.items()
        if cols_to_use is None or k in cols_to_use
    }

    return pl.read_csv(
        source,
        separator=";",
        ignore_errors=True,
        low_memory=False,
        rechunk=True,
        columns=cols_to_use,
        schema_overrides=schema_overrides,
    )

@st.cache_resource
def load_csv_stream(file_bytes):
    return _read_csv_optimized(file_bytes)

@st.cache_resource(hash_funcs={"streamlit.runtime.uploaded_file_manager.UploadedFile": lambda f: f"{f.name}_{f.size}"})
def load_zip(file):
    with zipfile.ZipFile(file) as z:
        csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
        if csv_name is None:
            raise ValueError("Aucun CSV trouvé dans le ZIP.")
        with z.open(csv_name) as csv_file:
            # Une seule lecture en bytes (pas de BytesIO en plus : évite une
            # copie mémoire supplémentaire). On passe des bytes bruts, pas
            # l'objet ZipExtFile, pour éviter que Polars ne tente de rouvrir
            # le nom du fichier directement sur le disque.
            csv_bytes = csv_file.read()
        result = _read_csv_optimized(csv_bytes)
        del csv_bytes
        gc.collect()
        return result


# MAIN LOGIC
if uploaded_file is not None:
    try:
        # Chargement
        if uploaded_file.name.lower().endswith(".zip"):
            df = load_zip(uploaded_file)
        else:
            df = load_csv_stream(uploaded_file)
        df = df.rechunk()  # consolide les fragments issus du parsing low_memory
        gc.collect()

        # Nettoyage robuste de la colonne "age" : lue en texte brut, elle
        # peut contenir des formats variés ("35", "35.0", "35,0", " 35 ",
        # valeurs vides...). On nettoie et on caste en float d'abord (accepte
        # les décimales) avant l'entier, ligne par ligne, sans jamais faire
        # échouer toute la colonne pour quelques valeurs mal formées.
        age_debug_dtype_before = None
        age_debug_sample_before = None
        if "age" in df.columns:
            age_debug_dtype_before = df.schema["age"]
            age_debug_sample_before = df["age"].drop_nulls().head(10).to_list()
            df = df.with_columns(
                pl.col("age")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .str.replace_all(",", ".")
                .cast(pl.Float64, strict=False)
                .round(0)
                .cast(pl.Int16, strict=False)
                .alias("age")
            )
            with st.expander("🔧 Diagnostic colonne 'age'"):
                st.write(f"Type détecté à la lecture : `{age_debug_dtype_before}`")
                st.write(f"Exemples de valeurs brutes (avant nettoyage) : {age_debug_sample_before}")
                st.write(f"Valeurs non nulles après nettoyage : {df['age'].drop_nulls().len():,}".replace(",", " "))

        # Nettoyage texte (désactivable pour économiser la mémoire sur gros fichiers)
        clean_text = st.sidebar.checkbox("Nettoyer les espaces en trop (texte)", value=True)
        if clean_text:
            df = df.with_columns([
                pl.col(pl.Utf8).str.strip_chars()
            ])

        # Colonnes à faible cardinalité (peu de valeurs distinctes répétées
        # sur des centaines de milliers de lignes) : passage en Categorical
        # pour diviser fortement l'empreinte mémoire. Important sur un
        # environnement à RAM limitée (ex: Render Free, 512 Mo).
        low_cardinality_cols = [
            "agence", "region", "grappe", "segmentation_marketing",
            "segmentation_comportementale", "conseiller",
            "segmentation_principalisation",
        ]
        cast_exprs = [
            pl.col(c).cast(pl.Categorical)
            for c in low_cardinality_cols
            if c in df.columns
        ]
        if cast_exprs:
            df = df.with_columns(cast_exprs)

        st.success("Chargement terminé ✔️")

        # FILTRES DYNAMIQUES
        st.sidebar.header("🔍 Filtres globaux")

        df_filtered = df

        def add_filter(col_name, label):
            nonlocal_df = df_filtered
            if col_name in df.columns:
                # Cascade : les valeurs proposées viennent du DataFrame déjà
                # filtré par les sélections précédentes, pas du DataFrame complet
                values = nonlocal_df[col_name].unique().to_list()
                values = [v for v in values if v is not None]
                values = sorted([str(v) for v in values])
                values = ["Tous"] + values
                widget_key = f"filter_{col_name}_{uploaded_file.name}_{uploaded_file.size}"
                # Si la sélection précédente n'existe plus dans la liste
                # cascadée (ex: agence absente de la région choisie),
                # on la réinitialise pour éviter une erreur Streamlit
                if widget_key in st.session_state and st.session_state[widget_key] not in values:
                    st.session_state[widget_key] = "Tous"
                selected = st.sidebar.selectbox(label, values, key=widget_key)
                if selected != "Tous" and selected in values:
                    return nonlocal_df.filter(pl.col(col_name).cast(pl.Utf8) == selected)
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

        seg_mkt_counts = None
        if "segmentation_marketing" in df_filtered.columns and total > 0:
            seg_mkt_counts = df_filtered["segmentation_marketing"].value_counts().sort("count", descending=True)

        seg_comp_counts = None
        if "segmentation_comportementale" in df_filtered.columns and total > 0:
            seg_comp_counts = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True)

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
            aff_rows = []
            for col_name, label in top_present:
                nb_top = df_filtered.filter(
                    pl.col(col_name).cast(pl.Float64, strict=False) == 1
                ).height
                aff_rows.append({"segment_affinitaire": label, "count": nb_top})
            seg_aff_counts = pl.DataFrame(aff_rows).sort("count", descending=True)

        seg_prin_counts = None
        if "segmentation_principalisation" in df_filtered.columns and total > 0:
            seg_prin_counts = df_filtered["segmentation_principalisation"].value_counts()

        # Répartition par tranche d'âge
        age_counts = None
        nb_age_renseigne = 0
        if "age" in df_filtered.columns and total > 0:
            df_age = df_filtered.filter(pl.col("age").is_not_null())
            nb_age_renseigne = len(df_age)
            if nb_age_renseigne > 0:
                df_age = df_age.with_columns(
                    pl.when(pl.col("age") < 25).then(pl.lit("< 25 ans"))
                    .when(pl.col("age") < 35).then(pl.lit("25-34 ans"))
                    .when(pl.col("age") < 45).then(pl.lit("35-44 ans"))
                    .when(pl.col("age") < 55).then(pl.lit("45-54 ans"))
                    .when(pl.col("age") < 65).then(pl.lit("55-64 ans"))
                    .otherwise(pl.lit("65 ans et +"))
                    .alias("tranche_age")
                )
                age_counts = df_age["tranche_age"].value_counts().sort("count", descending=True)

        # KPIs
        st.subheader("📊 KPIs Principaux")

        k1, k2, k3, k4 = st.columns(4)

        # 1. Clients uniques
        nb_clients = df_filtered["client_id"].n_unique() if "client_id" in df_filtered.columns else total
        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if seg_mkt_counts is not None:
            k2.metric("Segment Marketing", str(seg_mkt_counts["segmentation_marketing"][0]))
        else:
            k2.metric("Segment Marketing", "N/A")

        # 3. % Digital autonomes : seg_dig_auto est un flag entier 0/1
        if "seg_dig_auto" in df_filtered.columns:
            nb_dig = df_filtered.filter(
                pl.col("seg_dig_auto").cast(pl.Float64, strict=False) == 1
            ).height
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
                .rename({"segment_affinitaire": "Segment affinitaire (TOP_)", "count": "Nb clients"})
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
            st.caption(f"{pct_age_dom:.1f}% des clients avec âge renseigné ({nb_age_renseigne:,} sur {total:,})".replace(",", " "))

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
                st.plotly_chart(fig_prin, use_container_width=True)

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
                st.plotly_chart(fig_mkt, use_container_width=True)

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
                st.plotly_chart(fig_aff_bar, use_container_width=True)

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
                st.plotly_chart(fig_aff_donut, use_container_width=True)

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
                st.plotly_chart(fig_comp, use_container_width=True)

        # 6. Heatmap Principalisation × Marketing
        with g6:
            if "segmentation_principalisation" in df_filtered.columns and "segmentation_marketing" in df_filtered.columns and total > 0:
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
                st.plotly_chart(fig_cross, use_container_width=True)

        # 7. Répartition par tranche d'âge (Barres, ordre chronologique)
        with g7:
            if age_counts is not None:
                import pandas as pd
                age_order = ["< 25 ans", "25-34 ans", "35-44 ans", "45-54 ans", "55-64 ans", "65 ans et +"]
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
                st.plotly_chart(fig_age, use_container_width=True)

        # EXPORT
        def export_csv(df_export):
            buffer = io.BytesIO()
            df_export.write_csv(buffer, separator=";")
            return buffer.getvalue()

        if total > 0:
            st.download_button(
                f"💾 Télécharger les {total:,} lignes filtrées (CSV ;)".replace(",", " "),
                data=export_csv(df_filtered),
                file_name="export_filtre.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("Aucune ligne à exporter avec les filtres actuels.")

    except Exception as e:
        st.error(f"Erreur : {e}")

else:
    st.info("⏳ En attente d’un fichier ZIP ou CSV…")
