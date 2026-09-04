import streamlit as st
import polars as pl
import zipfile
import io
import gc
import plotly.express as px

# ============================
# 🎨 DESIGN PREMIUM
# ============================
st.set_page_config(page_title="Dashboard Ultra-Performant", layout="wide")

st.markdown("""
<style>

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
    font-size: 14px;
}

h1, h2, h3, h4 {
    font-weight: 600;
    letter-spacing: -0.5px;
}

h1 {
    font-size: 32px !important;
    color: #1A1A1A;
}

h2 {
    font-size: 24px !important;
    margin-top: 20px;
}

h3 {
    font-size: 20px !important;
}

.sidebar .sidebar-content {
    background: #F7F9FC;
}

.metric-container {
    background: #ffffff;
    padding: 18px 22px;
    border-radius: 12px;
    border: 1px solid #E5E7EB;
    box-shadow: 0px 2px 6px rgba(0,0,0,0.04);
}

hr {
    border: none;
    border-top: 1px solid #E5E7EB;
}

</style>
""", unsafe_allow_html=True)

# ============================
# 🏦 HEADER PREMIUM
# ============================
st.markdown("""
<div style="padding: 20px 0 10px 0;">
    <h1 style="margin-bottom: -10px;">
        🏦 Portefeuille Client — Dashboard Ultra‑Performant
    </h1>
    <p style="color:#555; font-size:14px;">
        Analyse avancée, segmentation, indicateurs TOP et visualisations dynamiques
    </p>
</div>
""", unsafe_allow_html=True)

# ============================
# 📥 UPLOAD ZIP / CSV
# ============================
uploaded_file = st.file_uploader(
    "Déposez un fichier ZIP ou CSV (jusqu’à ~100 Mo, séparateur ;)",
    type=["zip", "csv"]
)

USED_COLUMNS = [
    "client_id", "agence", "region", "grappe",
    "segmentation_marketing", "segmentation_comportementale",
    "segment_affinitaire", "seg_dig_auto",
    "TOP_TERRITORIAL_ENGAGE", "TOP_OPTIMISATEUR_MULTIBANCARISE",
    "TOP_JOUEUR_INVESTISSEUR", "TOP_PRUDENT_INSTALLE",
    "TOP_PROFESSIONNEL_INDEPENDANT",
    "conseiller", "segmentation_principalisation",
]

DTYPE_OVERRIDES = {
    "client_id": pl.Int32,
    "TOP_TERRITORIAL_ENGAGE": pl.Int8,
    "TOP_OPTIMISATEUR_MULTIBANCARISE": pl.Int8,
    "TOP_JOUEUR_INVESTISSEUR": pl.Int8,
    "TOP_PRUDENT_INSTALLE": pl.Int8,
    "TOP_PROFESSIONNEL_INDEPENDANT": pl.Int8,
}

def _read_csv_optimized(source):
    peek = pl.read_csv(source, separator=";", n_rows=0, ignore_errors=True)
    cols_to_use = [c for c in USED_COLUMNS if c in peek.columns] or None

    if hasattr(source, "seek"):
        source.seek(0)

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
            csv_bytes = csv_file.read()
        result = _read_csv_optimized(csv_bytes)
        del csv_bytes
        gc.collect()
        return result

# ============================
# 🔍 MAIN LOGIC
# ============================
if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".zip"):
            df = load_zip(uploaded_file)
        else:
            df = load_csv_stream(uploaded_file)

        df = df.rechunk()
        gc.collect()

        clean_text = st.sidebar.checkbox("Nettoyer les espaces en trop (texte)", value=True)
        if clean_text:
            df = df.with_columns([
                pl.col(pl.Utf8).str.strip_chars()
            ])

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

        # ============================
        # 🔍 FILTRES DYNAMIQUES
        # ============================
        st.sidebar.header("🔍 Filtres globaux")

        df_filtered = df

        def add_filter(col_name, label):
            nonlocal_df = df_filtered
            if col_name in df.columns:
                values = nonlocal_df[col_name].unique().to_list()
                values = [v for v in values if v is not None]
                values = sorted([str(v) for v in values])
                values = ["Tous"] + values
                widget_key = f"filter_{col_name}_{uploaded_file.name}_{uploaded_file.size}"
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

        # ============================
        # 📊 AGRÉGATIONS
        # ============================
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

        # ============================
        # 📊 KPIs PREMIUM
        # ============================
        st.markdown("### 📌 Indicateurs Clés")

        k1, k2, k3, k4 = st.columns(4)

        nb_clients = df_filtered["client_id"].n_unique() if "client_id" in df_filtered.columns else total

        with k1:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))
            st.markdown('</div>', unsafe_allow_html=True)

        with k2:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.metric("Segment Marketing Dominant", str(seg_mkt_counts["segmentation_marketing"][0]) if seg_mkt_counts is not None else "N/A")
            st.markdown('</div>', unsafe_allow_html=True)

        with k3:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            if "seg_dig_auto" in df_filtered.columns:
                df_dig = df_filtered.filter(
                    pl.col("seg_dig_auto").cast(pl.Utf8).str.to_lowercase().is_in(["oui", "1", "actif", "autonome"])
                )
                pct_dig = (len(df_dig) / total) * 100 if total > 0 else 0
                st.metric("% Digital Autonomes", f"{pct_dig:.1f}%")
            else:
                st.metric("% Digital Autonomes", "N/A")
            st.markdown('</div>', unsafe_allow_html=True)

        with k4:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            if seg_comp_counts is not None:
                seg_comp_dom = seg_comp_counts["segmentation_comportementale"][0]
                pct_comp_dom = (seg_comp_counts["count"][0] / total) * 100
                st.metric("Segment Comportemental Dominant", f"{seg_comp_dom}", f"{pct_comp_dom:.1f}%")
            else:
                st.metric("Segment Comportemental Dominant", "N/A")
            st.markdown('</div>', unsafe_allow_html=True)

        # ============================
        # 📈 GRAPHIQUES PREMIUM
        # ============================
        px.defaults.template = "plotly_white"
        px.defaults.color_continuous_scale = px.colors.sequential.Blues

        st.markdown("### 📈 Visualisations des Segmentations")

        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)
        g5, g6 = st.columns(2)

        # Principalisation
        with g1:
            if seg_prin_counts is not None:
                df_prin = seg_prin_counts.to_pandas()
                fig_prin = px.pie(
                    df_prin,
                    values="count",
                    names="segmentation_principalisation",
                    title="Segmentation Principalisation",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_prin, use_container_width=True)

        # Marketing
        with g2:
            if seg_mkt_counts is not None:
                df_mkt = seg_mkt_counts.to_pandas()
                fig_mkt = px.pie(
                    df_mkt,
                    values="count",
                    names="segmentation_marketing",
                    title="Segmentation Marketing",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                st.plotly_chart(fig_mkt, use_container_width=True)

        # Affinitaire bar
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
                    color_continuous_scale="Blues"
                )
                st.plotly_chart(fig_aff_bar, use_container_width=True)

        # Affinitaire donut
        with g4:
            if seg_aff_counts is not None:
                df_aff_donut = seg_aff_counts.to_pandas()
                fig_aff_donut = px.pie(
                    df_aff_donut,
                    values="count",
                    names="segment_affinitaire",
                    title="Répartition Affinitaire",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_aff_donut, use_container_width=True)

        # Comportementale bar
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
                    color_continuous_scale="Viridis"
                )
                st.plotly_chart(fig_comp, use_container_width=True)

        # Heatmap
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
                    color_continuous_scale="Blues"
                )
                st.plotly_chart(fig_cross, use_container_width=True)

        # ============================
        # 💾 EXPORT CSV
        # ============================
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

# ============================
# 🧩 FOOTER PREMIUM
# ============================
st.markdown("""
<hr style="margin-top:40px;">
<p style="text-align:center; color:#888; font-size:13px;">
Dashboard optimisé Polars ⚡ — Design Premium ✨ — Powered by Streamlit
</p>
""", unsafe_allow_html=True)
