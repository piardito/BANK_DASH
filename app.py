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

# --- Palette "banque premium" : vert profond (confiance/patrimoine) + or (valeur) ---
COLOR_PRIMARY = "#0B3D2E"      # vert forêt profond
COLOR_PRIMARY_LIGHT = "#1C5F45"
COLOR_ACCENT = "#B08D57"       # or/bronze discret
COLOR_BG = "#F6F5F1"           # ivoire papier
COLOR_CARD_BG = "#FFFFFF"
COLOR_TEXT = "#1A2620"
COLOR_MUTED = "#5C6B63"
COLOR_BORDER = "#DEDCD3"

PALETTE_SEQ = ["#0B3D2E", "#B08D57", "#4C7A63", "#8C6A3F", "#1C5F45", "#C9B27C", "#2E4A3D", "#A98D5D"]
PALETTE_SCALE = ["#F6F5F1", "#C9B27C", "#B08D57", "#4C7A63", "#0B3D2E"]

pio.templates["banque_premium"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color=COLOR_TEXT, size=13),
        title=dict(font=dict(family="Source Serif 4, serif", size=17, color=COLOR_PRIMARY)),
        paper_bgcolor=COLOR_CARD_BG,
        plot_bgcolor=COLOR_CARD_BG,
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

    h1, h2, h3 {{
        font-family: 'Source Serif 4', serif !important;
        color: {COLOR_PRIMARY} !important;
        font-weight: 600 !important;
    }}

    /* Bandeau institutionnel */
    .bank-header {{
        background: linear-gradient(135deg, {COLOR_PRIMARY} 0%, {COLOR_PRIMARY_LIGHT} 100%);
        padding: 28px 36px;
        border-radius: 6px;
        margin-bottom: 28px;
        border-left: 5px solid {COLOR_ACCENT};
    }}
    .bank-header h1 {{
        color: #FFFFFF !important;
        font-size: 1.6rem !important;
        margin: 0 !important;
        letter-spacing: 0.2px;
    }}
    .bank-header p {{
        color: #E8E4D9;
        margin: 6px 0 0 0;
        font-size: 0.92rem;
        font-family: 'Inter', sans-serif;
    }}

    /* Cartes metric */
    [data-testid="stMetric"] {{
        background-color: {COLOR_CARD_BG};
        border: 1px solid {COLOR_BORDER};
        border-left: 3px solid {COLOR_ACCENT};
        border-radius: 4px;
        padding: 16px 18px;
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLOR_MUTED} !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {COLOR_PRIMARY} !important;
        font-family: 'Source Serif 4', serif !important;
        font-weight: 600 !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {COLOR_PRIMARY};
    }}
    [data-testid="stSidebar"] * {{
        color: #F0EEE6 !important;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        text-transform: none !important;
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

    /* Sous-titres de section */
    .stSubheader, div[data-testid="stMarkdownContainer"] h3 {{
        border-bottom: 1px solid {COLOR_BORDER};
        padding-bottom: 6px;
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
USED_COLUMNS = [
    "client_id", "agence", "region", "grappe",
    "segmentation_marketing", "segmentation_comportementale",
    "segment_affinitaire", "seg_dig_auto",
    "TOP_TERRITORIAL_ENGAGE", "TOP_OPTIMISATEUR_MULTIBANCARISE",
    "TOP_JOUEUR_INVESTISSEUR", "TOP_PRUDENT_INSTALLE",
    "TOP_PROFESSIONNEL_INDEPENDANT",
    "conseiller", "segmentation_principalisation",
]

# Types réduits pour les colonnes numériques : un flag 0/1 n'a pas besoin
# d'un Int64 (8 octets), Int8 (1 octet) suffit largement.
DTYPE_OVERRIDES = {
    "client_id": pl.Int32,
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
    cols_to_use = [c for c in USED_COLUMNS if c in peek.columns] or None

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
            "segmentation_comportementale", "segment_affinitaire",
            "seg_dig_auto", "conseiller", "segmentation_principalisation",
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

        seg_aff_counts = None
        if "segment_affinitaire" in df_filtered.columns and total > 0:
            df_aff_clean = df_filtered.filter(
                pl.col("segment_affinitaire").is_not_null() &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
            )
            if len(df_aff_clean) > 0:
                seg_aff_counts = df_aff_clean["segment_affinitaire"].value_counts().sort("count", descending=True)

        seg_prin_counts = None
        if "segmentation_principalisation" in df_filtered.columns and total > 0:
            seg_prin_counts = df_filtered["segmentation_principalisation"].value_counts()

        # KPIs
        st.subheader("📊 KPIs Principaux")

        k1, k2, k3, k4 = st.columns(4)

        # 1. Clients uniques
        nb_clients = df_filtered["client_id"].n_unique() if "client_id" in df_filtered.columns else total
        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if seg_mkt_counts is not None:
            k2.metric("Segment Marketing Dominant", str(seg_mkt_counts["segmentation_marketing"][0]))
        else:
            k2.metric("Segment Marketing Dominant", "N/A")

        # 3. % Digital autonomes
        if "seg_dig_auto" in df_filtered.columns:
            df_dig = df_filtered.filter(
                pl.col("seg_dig_auto").cast(pl.Utf8).str.to_lowercase().is_in(["oui", "1", "actif", "autonome"])
            )
            pct_dig = (len(df_dig) / total) * 100 if total > 0 else 0
            k3.metric("% Digital Autonomes", f"{pct_dig:.1f}%")
        else:
            k3.metric("% Digital Autonomes", "N/A")

        # 4. Segment comportemental dominant + %
        if seg_comp_counts is not None:
            seg_comp_dom = seg_comp_counts["segmentation_comportementale"][0]
            pct_comp_dom = (seg_comp_counts["count"][0] / total) * 100
            k4.metric("Segment Comportemental Dominant", f"{seg_comp_dom}", f"{pct_comp_dom:.1f}%")
        else:
            k4.metric("Segment Comportemental Dominant", "N/A")

        # CARTES TOP_
        top_columns = [
            ("TOP_TERRITORIAL_ENGAGE", "Territorial Engagé"),
            ("TOP_OPTIMISATEUR_MULTIBANCARISE", "Optimisateur Multibancarisé"),
            ("TOP_JOUEUR_INVESTISSEUR", "Joueur Investisseur"),
            ("TOP_PRUDENT_INSTALLE", "Prudent Installé"),
            ("TOP_PROFESSIONNEL_INDEPENDANT", "Professionnel Indépendant"),
        ]
        top_present = [(c, l) for c, l in top_columns if c in df_filtered.columns]

        if top_present and total > 0:
            st.subheader("🏅 Indicateurs TOP")
            top_cols_ui = st.columns(len(top_present))
            for (col_name, label), ui_col in zip(top_present, top_cols_ui):
                nb_top = df_filtered.filter(
                    pl.col(col_name).cast(pl.Float64, strict=False) == 1
                ).height
                pct_top = (nb_top / total) * 100
                ui_col.metric(
                    label,
                    f"{nb_top:,}".replace(",", " "),
                    f"{pct_top:.1f}% du portefeuille"
                )

        # SEGMENT AFFINITAIRE GLOBAL + RANG
        st.subheader("🏆 Segment Affinitaire Dominant + Classement Global")

        if seg_aff_counts is not None:
            seg_aff_dom_global = seg_aff_counts["segment_affinitaire"][0]
            pct_aff_global = (seg_aff_counts["count"][0] / total) * 100

            st.metric(
                label="Segment Affinitaire Dominant",
                value=str(seg_aff_dom_global),
                delta=f"{pct_aff_global:.1f}% du portefeuille"
            )

        # GRAPHIQUES SEGMENTATIONS
        st.subheader("📈 Graphiques des Segmentations")

        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)
        g5, g6 = st.columns(2)

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

        # 3. Affinitaire (Barres)
        with g3:
            if seg_aff_counts is not None:
                df_aff_bar = seg_aff_counts.to_pandas()
                fig_aff_bar = px.bar(
                    df_aff_bar,
                    x="segment_affinitaire",
                    y="count",
                    title="Segments Affinitaires (Classement)",
                    text_auto=True,
                    color="count",
                    color_continuous_scale=PALETTE_SCALE
                )
                st.plotly_chart(fig_aff_bar, use_container_width=True)

        # 4. Affinitaire (Donut)
        with g4:
            if seg_aff_counts is not None:
                df_aff_donut = seg_aff_counts.to_pandas()
                fig_aff_donut = px.pie(
                    df_aff_donut,
                    values="count",
                    names="segment_affinitaire",
                    title="Répartition Affinitaire",
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
