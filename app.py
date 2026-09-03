import streamlit as st
import polars as pl
import zipfile
import io
import plotly.express as px

-----------------------------

CONFIG

-----------------------------
st.setpageconfig(page_title="Dashboard Ultra-Performant", layout="wide")
st.title("🏦 Dashboard Ultra-Performant Portefeuille Client")

-----------------------------

UPLOAD ZIP / CSV

-----------------------------
uploadedfile = st.fileuploader(
    "Déposez un fichier ZIP ou CSV (jusqu’à ~100 Mo, séparateur ;)",
    type=["zip", "csv"]
)

@st.cache_resource
def loadcsvstream(file_bytes):
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
        with z.open(csvname) as csvfile:
            return loadcsvstream(csv_file)

-----------------------------

MAIN LOGIC

-----------------------------
if uploaded_file is not None:
    try:
        # Chargement
        if uploaded_file.name.lower().endswith(".zip"):
            df = loadzip(uploadedfile)
        else:
            df = loadcsvstream(uploaded_file)

        # Nettoyage texte
        df = df.with_columns([
            pl.col(pl.Utf8).str.strip_chars()
        ])

        st.success("Chargement terminé ✔️")

        # -----------------------------
        # FILTRES DYNAMIQUES
        # -----------------------------
        st.sidebar.header("🔍 Filtres globaux")

        df_filtered = df

        def addfilter(colname, label):
            nonlocal df_filtered
            if col_name in df.columns:
                values = df[colname].unique().tolist()
                values = [v for v in values if v is not None]
                values = sorted([str(v) for v in values])
                values = ["Tous"] + values
                selected = st.sidebar.selectbox(label, values)
                if selected != "Tous":
                    dffiltered = dffiltered.filter(pl.col(col_name).cast(pl.Utf8) == selected)

        add_filter("region", "Région")
        add_filter("agence", "Agence")
        add_filter("grappe", "Grappe")
        add_filter("conseiller", "Conseiller")

        total = len(df_filtered)

        # -----------------------------
        # 4 KPIs PRINCIPAUX
        # -----------------------------
        st.subheader("📊 KPIs Principaux")

        k1, k2, k3, k4 = st.columns(4)

        # 1. Clients uniques
        nbclients = dffiltered["clientid"].nunique() if "clientid" in dffiltered.columns else total
        k1.metric("Clients uniques", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment marketing dominant
        if "segmentationmarketing" in dffiltered.columns and total > 0:
            segmkt = dffiltered["segmentationmarketing"].valuecounts().sort("count", descending=True)
            segdommkt = segmkt["segmentationmarketing"][0]
            k2.metric("Segment Marketing Dominant", str(segdommkt))
        else:
            k2.metric("Segment Marketing Dominant", "N/A")

        # 3. % Digital autonomes
        if "segdigauto" in df_filtered.columns:
            dfdig = dffiltered.filter(
                pl.col("segdigauto").cast(pl.Utf8).str.tolowercase().isin(["oui", "1", "actif", "autonome"])
            )
            pctdig = (len(dfdig) / total) * 100 if total > 0 else 0
            k3.metric("% Digital Autonomes", f"{pct_dig:.1f}%")
        else:
            k3.metric("% Digital Autonomes", "N/A")

        # 4. Segment comportemental dominant + %
        if "segmentationcomportementale" in dffiltered.columns and total > 0:
            dfcomp = dffiltered["segmentationcomportementale"].valuecounts().sort("count", descending=True)
            segcompdom = dfcomp["segmentationcomportementale"][0]
            pctcompdom = (df_comp["count"][0] / total) * 100
            k4.metric("Segment Comportemental Dominant", f"{segcompdom}", f"{pctcompdom:.1f}%")
        else:
            k4.metric("Segment Comportemental Dominant", "N/A")

        # -----------------------------
        # SEGMENT AFFINITAIRE GLOBAL + RANG
        # -----------------------------
        st.markdown("---")
        st.subheader("🏆 Segment Affinitaire Dominant + Classement Global")

        if "segmentaffinitaire" in dffiltered.columns and total > 0:
            dfaffglobal = df_filtered.filter(
                pl.col("segmentaffinitaire").isnot_null() &
                (pl.col("segmentaffinitaire").cast(pl.Utf8).str.stripchars() != "") &
                (pl.col("segmentaffinitaire").cast(pl.Utf8).str.tolowercase() != "none")
            )

            if len(dfaffglobal) > 0:
                dfrankglobal = (
                    dfaffglobal["segment_affinitaire"]
                    .value_counts()
                    .sort("count", descending=True)
                    .with_columns([
                        pl.col("count").alias("nb_clients"),
                        (pl.col("count") / total * 100).alias("pct")
                    ])
                ).to_pandas()

                segaffdomglobal = dfrankglobal["segmentaffinitaire"][0]
                pctaffglobal = dfrankglobal["pct"][0]

                st.metric(
                    label="Segment Affinitaire Dominant",
                    value=str(segaffdom_global),
                    delta=f"{pctaffglobal:.1f}% du portefeuille"
                )

                st.write("### 📊 Classement complet des segments affinitaires")
                st.dataframe(dfrankglobal, usecontainerwidth=True)

        # -----------------------------
        # GRAPHIQUES SEGMENTATIONS
        # -----------------------------
        st.markdown("---")
        st.subheader("📈 Graphiques des Segmentations")

        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)
        g5, g6 = st.columns(2)

        # 1. Principalisation (Donut)
        with g1:
            if "segmentationprincipalisation" in dffiltered.columns and total > 0:
                dfprin = dffiltered["segmentationprincipalisation"].valuecounts().to_pandas()
                fig_prin = px.pie(
                    df_prin,
                    values="count",
                    names="segmentation_principalisation",
                    title="Segmentation Principalisation",
                    hole=0.45,
                    colordiscretesequence=px.colors.qualitative.Pastel
                )
                st.plotlychart(figprin, usecontainerwidth=True)
            else:
                st.info("Aucune donnée de principalisation.")

        # 2. Marketing (Donut)
        with g2:
            if "segmentationmarketing" in dffiltered.columns and total > 0:
                dfmkt = dffiltered["segmentationmarketing"].valuecounts().to_pandas()
                fig_mkt = px.pie(
                    df_mkt,
                    values="count",
                    names="segmentation_marketing",
                    title="Segmentation Marketing",
                    hole=0.45,
                    colordiscretesequence=px.colors.qualitative.Safe
                )
                st.plotlychart(figmkt, usecontainerwidth=True)
            else:
                st.info("Aucune segmentation marketing disponible.")

        # 3. Affinitaire (Barres)
        with g3:
            if "segmentaffinitaire" in dffiltered.columns and total > 0:
                dfaffbar = df_filtered.filter(
                    pl.col("segmentaffinitaire").isnot_null() &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.stripchars() != "") &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.tolowercase() != "none")
                )["segmentaffinitaire"].valuecounts().sort("count", descending=True).to_pandas()

                figaffbar = px.bar(
                    dfaffbar,
                    x="segment_affinitaire",
                    y="count",
                    title="Segments Affinitaires (Classement)",
                    text_auto=True,
                    color="count",
                    colorcontinuousscale="Blues"
                )
                st.plotlychart(figaffbar, usecontainer_width=True)
            else:
                st.info("Aucune donnée affinitaire.")

        # 4. Affinitaire (Donut)
        with g4:
            if "segmentaffinitaire" in dffiltered.columns and total > 0:
                dfaffdonut = df_filtered.filter(
                    pl.col("segmentaffinitaire").isnot_null() &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.stripchars() != "") &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.tolowercase() != "none")
                )["segmentaffinitaire"].valuecounts().to_pandas()

                figaffdonut = px.pie(
                    dfaffdonut,
                    values="count",
                    names="segment_affinitaire",
                    title="Répartition Affinitaire",
                    hole=0.45,
                    colordiscretesequence=px.colors.qualitative.Set3
                )
                st.plotlychart(figaffdonut, usecontainer_width=True)
            else:
                st.info("Aucune donnée affinitaire.")

        # 5. Comportementale (Barres)
        with g5:
            if "segmentationcomportementale" in dffiltered.columns and total > 0:
                dfcompbar = dffiltered["segmentationcomportementale"].valuecounts().sort("count", descending=True).topandas()
                fig_comp = px.bar(
                    dfcompbar,
                    x="segmentation_comportementale",
                    y="count",
                    title="Segmentation Comportementale",
                    text_auto=True,
                    color="count",
                    colorcontinuousscale="Viridis"
                )
                st.plotlychart(figcomp, usecontainerwidth=True)
            else:
                st.info("Aucune segmentation comportementale.")

        # 6. Heatmap Principalisation × Marketing
        with g6:
            if "segmentationprincipalisation" in dffiltered.columns and "segmentationmarketing" in dffiltered.columns:
                df_cross = (
                    df_filtered
                    .groupby(["segmentationprincipalisation", "segmentation_marketing"])
                    .count()
                    .to_pandas()
                )

                figcross = px.densityheatmap(
                    df_cross,
                    x="segmentation_principalisation",
                    y="segmentation_marketing",
                    z="count",
                    title="Croisement Principalisation × Marketing",
                    colorcontinuousscale="Blues"
                )
                st.plotlychart(figcross, usecontainerwidth=True)
            else:
                st.info("Impossible de croiser principalisation et marketing.")

        # -----------------------------
        # TOPS + SEGMENTS AFFINITAIRES + RANG
        # -----------------------------
        st.markdown("---")
        st.subheader("🎯 TOPs + Segments Affinitaires Dominants + Classement")

        top_columns = [
            ("TOPTERRITORIALENGAGE", "🌍 Territorial Engagé"),
            ("TOPOPTIMISATEURMULTIBANCARISE", "🔄 Optimisateur Multibancarisé"),
            ("TOPJOUEURINVESTISSEUR", "🎲 Joueur Investisseur"),
            ("TOPPRUDENTINSTALLE", "🛡️ Prudent Installé"),
            ("TOPPROFESSIONNELINDEPENDANT", "💼 Professionnel / Indépendant")
        ]

        for colname, label in topcolumns:
            st.markdown(f"### {label}")

            if colname in dffiltered.columns:
                dftop = dffiltered.with_columns(
                    pl.col(colname).cast(pl.Utf8).str.stripchars().cast(pl.Int64, strict=False)
                ).filter(pl.col(col_name) == 1)

                nbtop = len(dftop)
                pcttop = (nbtop / total) * 100 if total > 0 else 0

                dfafftop = df_top.filter(
                    pl.col("segmentaffinitaire").isnot_null() &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.stripchars() != "") &
                    (pl.col("segmentaffinitaire").cast(pl.Utf8).str.tolowercase() != "none")
                )

                if len(dfafftop) > 0:
                    dfranktop = (
                        dfafftop["segment_affinitaire"]
                        .value_counts()
                        .sort("count", descending=True)
                        .with_columns([
                            pl.col("count").alias("nb_clients"),
                            (pl.col("count") / nb_top * 100).alias("pct")
                        ])
                    ).to_pandas()

                    segaffdomtop = dfranktop["segmentaffinitaire"][0]

                    st.metric(
                        label=f"{label}",
                        value=f"{nb_top:,}".replace(",", " "),
                        delta=f"{pcttop:.1f}% | Affinité dominante : {segaffdomtop}",
                        delta_color="normal"
                    )

                    st.write("Classement affinitaire du TOP :")
                    st.dataframe(dfranktop, usecontainerwidth=True)
                else:
                    st.metric(label=label, value=f"{nb_top}", delta="Aucune affinité détectée")
            else:
                st.metric(label=label, value="N/A", delta="Colonne absente")

        # -----------------------------
        # APERÇU + EXPORT
        # -----------------------------
        st.markdown("---")
        st.subheader("📋 Aperçu (100 premières lignes)")

        st.dataframe(dffiltered.head(100).topandas(), usecontainerwidth=True)

        @st.cache_data
        def exportcsv(dfexport):
            buffer = io.BytesIO()
            dfexport.writecsv(buffer, separator=";")
            return buffer.getvalue()

        st.download_button(
            f"💾 Télécharger les {total:,} lignes filtrées (CSV ;)",
            data=exportcsv(dffiltered),
            filename="exportfiltre.csv",
            mime="text/csv",
            usecontainerwidth=True
        )

    except Exception as e:
        st.error(f"Erreur : {e}")
        st.info("Vérifiez que le fichier est bien au format CSV ; ou ZIP contenant un CSV ;")
else:
    st.info("⏳ En attente d’un fichier ZIP ou CSV…")
`
