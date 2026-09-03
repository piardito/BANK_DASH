import streamlit as st
import polars as pl
import zipfile
import io
import plotly.express as px

# CONFIG
st.set_page_config(page_title="Dashboard Ultra-Performant", layout="wide")
st.title("🏦 Dashboard Ultra-Performant Portefeuille Client")

# UPLOAD ZIP / CSV
uploaded_file = st.file_uploader(
    "Déposez un fichier ZIP ou CSV (jusqu’à ~100 Mo, séparateur ;)",
    type=["zip", "csv"]
)

@st.cache_resource
def load_csv_stream(file_bytes):
    return pl.read_csv(
        file_bytes,
        separator=";",
        ignore_errors=True,
        low_memory=True
    )

@st.cache_resource
def load_zip(file):
    with zipfile.ZipFile(file) as z:
        csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
        if csv_name is None:
            raise ValueError("Aucun CSV trouvé dans le ZIP.")
        with z.open(csv_name) as csv_file:
            return load_csv_stream(csv_file)

# MAIN LOGIC
if uploaded_file is not None:
    try:
        # Chargement
        if uploaded_file.name.lower().endswith(".zip"):
            df = load_zip(uploaded_file)
        else:
            df = load_csv_stream(uploaded_file)

        # Nettoyage texte
        df = df.with_columns([
            pl.col(pl.Utf8).str.strip_chars()
        ])

        st.success("Chargement terminé ✔️")

        # FILTRES DYNAMIQUES
        st.sidebar.header("🔍 Filtres globaux")

        df_filtered = df

        def add_filter(col_name, label):
            if col_name in df.columns:
                values = df[col_name].unique().to_list()
                values = [v for v in values if v is not None]
                values = sorted([str(v) for v in values])
                values = ["Tous"] + values
                selected = st.sidebar.selectbox(label, values)
                if selected != "Tous":
                    return df_filtered.filter(pl.col(col_name).cast(pl.Utf8) == selected)
            return df_filtered

        df_filtered = add_filter("region", "Région")
        df_filtered = add_filter("agence", "Agence")
        df_filtered = add_filter("grappe", "Grappe")
        df_filtered = add_filter("conseiller", "Conseiller")

        total = len(df_filtered)

        # KPIs
        st.subheader("📊 KPIs Principaux")

        k1, k2, k3, k4 = st.columns(4)

        # 1. Clients uniques
        nb_clients = df_filtered["client_id"].n_unique() if "client_id" in df_filtered.columns else total
        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if "segmentation_marketing" in df_filtered.columns and total > 0:
            seg_mkt = df_filtered["segmentation_marketing"].value_counts().sort("count", descending=True)
            seg_dom_mkt = seg_mkt["segmentation_marketing"][0]
            k2.metric("Segment Marketing Dominant", str(seg_dom_mkt))
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
        if "segmentation_comportementale" in df_filtered.columns and total > 0:
            df_comp = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True)
            seg_comp_dom = df_comp["segmentation_comportementale"][0]
            pct_comp_dom = (df_comp["count"][0] / total) * 100
            k4.metric("Segment Comportemental Dominant", f"{seg_comp_dom}", f"{pct_comp_dom:.1f}%")
        else:
            k4.metric("Segment Comportemental Dominant", "N/A")

        # APERÇU
        st.subheader("📋 Aperçu (100 premières lignes)")
        st.dataframe(df_filtered.head(100).to_pandas(), use_container_width=True)

    except Exception as e:
        st.error(f"Erreur : {e}")

else:
    st.info("⏳ En attente d’un fichier ZIP ou CSV…")
