import streamlit as st
import polars as pl
import zipfile
import io
import gc
import plotly.express as px

# CONFIG
st.set_page_config(page_title="Dashboard Ultra-Performant", layout="wide")
st.title("🏦 Dashboard Ultra-Performant Portefeuille Client")

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
        low_memory=True,
        rechunk=False,
        low_memory=False,
        rechunk=True,
        columns=cols_to_use,
        schema_overrides=schema_overrides,
    )

            df = load_zip(uploaded_file)
        else:
            df = load_csv_stream(uploaded_file)
        df = df.rechunk()  # consolide les fragments issus du parsing low_memory
        gc.collect()

        # Nettoyage texte (désactivable pour économiser la mémoire sur gros fichiers)


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


        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if "segmentation_marketing" in df_filtered.columns and total > 0:
            seg_mkt = df_filtered["segmentation_marketing"].value_counts().sort("count", descending=True)
            seg_dom_mkt = seg_mkt["segmentation_marketing"][0]
            k2.metric("Segment Marketing Dominant", str(seg_dom_mkt))
        if seg_mkt_counts is not None:
            k2.metric("Segment Marketing Dominant", str(seg_mkt_counts["segmentation_marketing"][0]))
        else:
            k2.metric("Segment Marketing Dominant", "N/A")
            k3.metric("% Digital Autonomes", "N/A")

        # 4. Segment comportemental dominant + %
        if "segmentation_comportementale" in df_filtered.columns and total > 0:
            df_comp = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True)
            seg_comp_dom = df_comp["segmentation_comportementale"][0]
            pct_comp_dom = (df_comp["count"][0] / total) * 100
        if seg_comp_counts is not None:
            seg_comp_dom = seg_comp_counts["segmentation_comportementale"][0]
            pct_comp_dom = (seg_comp_counts["count"][0] / total) * 100
            k4.metric("Segment Comportemental Dominant", f"{seg_comp_dom}", f"{pct_comp_dom:.1f}%")
        else:
            k4.metric("Segment Comportemental Dominant", "N/A")

        # SEGMENT AFFINITAIRE GLOBAL + RANG
        st.subheader("🏆 Segment Affinitaire Dominant + Classement Global")

        if "segment_affinitaire" in df_filtered.columns and total > 0:
            df_aff_global = df_filtered.filter(
                pl.col("segment_affinitaire").is_not_null() &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
            )
        if seg_aff_counts is not None:
            seg_aff_dom_global = seg_aff_counts["segment_affinitaire"][0]
            pct_aff_global = (seg_aff_counts["count"][0] / total) * 100

            if len(df_aff_global) > 0:
                df_rank_global = (
                    df_aff_global["segment_affinitaire"]
                    .value_counts()
                    .sort("count", descending=True)
                    .with_columns([
                        (pl.col("count") / total * 100).alias("pct")
                    ])
                )

                seg_aff_dom_global = df_rank_global["segment_affinitaire"][0]
                pct_aff_global = df_rank_global["pct"][0]

                st.metric(
                    label="Segment Affinitaire Dominant",
                    value=str(seg_aff_dom_global),
                    delta=f"{pct_aff_global:.1f}% du portefeuille"
                )
            st.metric(
                label="Segment Affinitaire Dominant",
                value=str(seg_aff_dom_global),
                delta=f"{pct_aff_global:.1f}% du portefeuille"
            )

        # GRAPHIQUES SEGMENTATIONS
        st.subheader("📈 Graphiques des Segmentations")


        # 1. Principalisation (Donut)
        with g1:
            if "segmentation_principalisation" in df_filtered.columns and total > 0:
                df_prin = df_filtered["segmentation_principalisation"].value_counts().to_pandas()
            if seg_prin_counts is not None:
                df_prin = seg_prin_counts.to_pandas()
                fig_prin = px.pie(
                    df_prin,
                    values="count",


        # 2. Marketing (Donut)
        with g2:
            if "segmentation_marketing" in df_filtered.columns and total > 0:
                df_mkt = df_filtered["segmentation_marketing"].value_counts().to_pandas()
            if seg_mkt_counts is not None:
                df_mkt = seg_mkt_counts.to_pandas()
                fig_mkt = px.pie(
                    df_mkt,
                    values="count",


        # 3. Affinitaire (Barres)
        with g3:
            if "segment_affinitaire" in df_filtered.columns and total > 0:
                df_aff_bar = df_filtered.filter(
                    pl.col("segment_affinitaire").is_not_null() &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
                )["segment_affinitaire"].value_counts().sort("count", descending=True).to_pandas()

            if seg_aff_counts is not None:
                df_aff_bar = seg_aff_counts.to_pandas()
                fig_aff_bar = px.bar(
                    df_aff_bar,
                    x="segment_affinitaire",


        # 4. Affinitaire (Donut)
        with g4:
            if "segment_affinitaire" in df_filtered.columns and total > 0:
                df_aff_donut = df_filtered.filter(
                    pl.col("segment_affinitaire").is_not_null() &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.strip_chars() != "") &
                    (pl.col("segment_affinitaire").cast(pl.Utf8).str.to_lowercase() != "none")
                )["segment_affinitaire"].value_counts().to_pandas()

            if seg_aff_counts is not None:
                df_aff_donut = seg_aff_counts.to_pandas()
                fig_aff_donut = px.pie(
                    df_aff_donut,
                    values="count",


        # 5. Comportementale (Barres)
        with g5:
            if "segmentation_comportementale" in df_filtered.columns and total > 0:
                df_comp_bar = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True).to_pandas()
            if seg_comp_counts is not None:
                df_comp_bar = seg_comp_counts.to_pandas()
                fig_comp = px.bar(
                    df_comp_bar,
                    x="segmentation_comportementale",


        # 6. Heatmap Principalisation × Marketing
        with g6:
            if "segmentation_principalisation" in df_filtered.columns and "segmentation_marketing" in df_filtered.columns:
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
