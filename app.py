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
        low_memory=True,
        rechunk=False
    )

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
        return pl.read_csv(
            csv_bytes,
            separator=";",
            ignore_errors=True,
            low_memory=True,
            rechunk=False
        )

# MAIN LOGIC
if uploaded_file is not None:
    try:
        # Chargement
        if uploaded_file.name.lower().endswith(".zip"):
            df = load_zip(uploaded_file)
        else:
            df = load_csv_stream(uploaded_file)

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

        if "segment_affinitaire" in df_filtered.columns and total > 0:
            df_aff_global = df_filtered.filter(
                pl.col("segment_affinitaire").is_not_null() &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
            )

            if len(df_aff_global) > 0:
                df_rank_global = (
                    df_aff_global["segment_affinitaire"]
                    .value_counts()
                    .sort("count", descending=True)
                    .with_columns([
                        pl.col("count").alias("nb_clients"),
                        (pl.col("count") / total * 100).alias("pct")
                    ])
                ).to_pandas()

                seg_aff_dom_global = df_rank_global["segment_affinitaire"][0]
                pct_aff_global = df_rank_global["pct"][0]

                st.metric(
                    label="Segment Affinitaire Dominant",
                    value=str(seg_aff_dom_global),
                    delta=f"{pct_aff_global:.1f}% du portefeuille"
                )

                st.write("### 📊 Classement complet des segments affinitaires")
                st.dataframe(df_rank_global, use_container_width=True)

        # GRAPHIQUES SEGMENTATIONS
        st.subheader("📈 Graphiques des Segmentations")

        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)
        g5, g6 = st.columns(2)

        # 1. Principalisation (Donut)
        with g1:
            if "segmentation_principalisation" in df_filtered.columns and total > 0:
                df_prin = df_filtered["segmentation_principalisation"].value_counts().to_pandas()
                fig_prin = px.pie(
                    df_prin,
                    values="count",
                    names="segmentation_principalisation",
                    title="Segmentation Principalisation",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_prin, use_container_width=True)

        # 2. Marketing (Donut)
        with g2:
            if "segmentation_marketing" in df_filtered.columns and total > 0:
                df_mkt = df_filtered["segmentation_marketing"].value_counts().to_pandas()
                fig_mkt = px.pie(
                    df_mkt,
                    values="count",
                    names="segmentation_marketing",
                    title="Segmentation Marketing",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                st.plotly_chart(fig_mkt, use_container_width=True)

        # 3. Affinitaire (Barres)
        with g3:
            if "segment_affinitaire" in df_filtered.columns and total > 0:
                df_aff_bar = df_filtered.filter(
                    pl.col("segment_affinitaire").is_not_null() &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
                )["segment_affinitaire"].value_counts().sort("count", descending=True).to_pandas()

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

        # 4. Affinitaire (Donut)
        with g4:
            if "segment_affinitaire" in df_filtered.columns and total > 0:
                df_aff_donut = df_filtered.filter(
                    pl.col("segment_affinitaire").is_not_null() &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
                )["segment_affinitaire"].value_counts().to_pandas()

                fig_aff_donut = px.pie(
                    df_aff_donut,
                    values="count",
                    names="segment_affinitaire",
                    title="Répartition Affinitaire",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_aff_donut, use_container_width=True)

        # 5. Comportementale (Barres)
        with g5:
            if "segmentation_comportementale" in df_filtered.columns and total > 0:
                df_comp_bar = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True).to_pandas()
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

        # 6. Heatmap Principalisation × Marketing
        with g6:
            if "segmentation_principalisation" in df_filtered.columns and "segmentation_marketing" in df_filtered.columns:
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

        # APERÇU + EXPORT
        st.subheader("📋 Aperçu (100 premières lignes)")
        st.dataframe(df_filtered.head(100).to_pandas(), use_container_width=True)

        @st.cache_data
        def export_csv(df_export):
            buffer = io.BytesIO()
            df_export.write_csv(buffer, separator=";")
            return buffer.getvalue()

        st.download_button(
            f"💾 Télécharger les {total:,} lignes filtrées (CSV ;)",
            data=export_csv(df_filtered),
            file_name="export_filtre.csv",
            mime="text/csv",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Erreur : {e}")

else:
    st.info("⏳ En attente d’un fichier ZIP ou CSV…")
