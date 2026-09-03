import streamlit as st
import polars as pl
import plotly.express as px
import io

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Dashboard Portefeuille Bancaire",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard de Segmentation Portefeuille Client")
st.markdown("Analyse à haute performance de vos segments, profils et réseaux de conseillers.")

# Module d'Upload dans la barre latérale
uploaded_file = st.sidebar.file_uploader(
    "Déposez le fichier client (CSV séparateur point-virgule)", 
    type=["csv"]
)

@st.cache_data
def load_data(file):
    # CORRECTION : Utilisation explicite du séparateur ";" pour les CSV français
    df = pl.read_csv(file.getvalue(), separator=";")
    
    # Nettoyage automatique des colonnes textuelles (retire les espaces superflus)
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            df = df.with_columns(pl.col(col).str.strip_chars())
            
    return df

# Fonction optimisée pour convertir le DataFrame Polars filtré en bytes CSV pour l'export lourd
@st.cache_data(show_spinner="Génération du fichier CSV optimisé...")
def convert_df_to_csv(polars_df):
    buffer = io.BytesIO()
    polars_df.write_csv(buffer, separator=";") # On garde le format point-virgule à l'export
    return buffer.getvalue()

if uploaded_file is not None:
    try:
        df_raw = load_data(uploaded_file)
        
        # --- FILTRES SIDEBAR ---
        st.sidebar.header("🔍 Filtres Globaux")
        
        df_filtered = df_raw
        
        # Filtre par Région
        if "region" in df_filtered.columns:
            regions = ["Tous"] + sorted([str(r) for r in df_filtered["region"].unique().to_list() if r is not None])
            selected_region = st.sidebar.selectbox("Région", regions)
            if selected_region != "Tous":
                df_filtered = df_filtered.filter(pl.col("region") == selected_region)
                
        # Filtre par Agence
        if "agence" in df_filtered.columns:
            agences = ["Toutes"] + sorted([str(a) for a in df_filtered["agence"].unique().to_list() if a is not None])
            selected_agence = st.sidebar.selectbox("Agence", agences)
            if selected_agence != "Toutes":
                df_filtered = df_filtered.filter(pl.col("agence") == selected_agence)

        # Filtre par Grappe
        if "grappe" in df_filtered.columns:
            grappes = ["Toutes"] + sorted([str(g) for g in df_filtered["grappe"].unique().to_list() if g is not None])
            selected_grappe = st.sidebar.selectbox("Grappe", grappes)
            if selected_grappe != "Toutes":
                df_filtered = df_filtered.filter(pl.col("grappe") == selected_grappe)

        # Filtre par Conseiller
        if "conseiller" in df_filtered.columns:
            conseillers = ["Tous"] + sorted([str(c) for c in df_filtered["conseiller"].unique().to_list() if c is not None])
            selected_conseiller = st.sidebar.selectbox("Conseiller", conseillers)
            if selected_conseiller != "Tous":
                df_filtered = df_filtered.filter(pl.col("conseiller").cast(pl.Utf8) == selected_conseiller)

        # Total clients après application des filtres de la sidebar
        total_clients_filtre = len(df_filtered)

        # --- BLOC 1 : LES 5 KPIS PRINCIPAUX ---
        st.subheader("📊 Indicateurs Clés de Performance (Sélection)")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

        # 1. Nombre total de clients uniques
        nb_clients = df_filtered["client_id"].n_unique() if "client_id" in df_filtered.columns else total_clients_filtre
        kpi1.metric("Clients Total", f"{nb_clients:,}".replace(",", " "))

        # 2. Segment Marketing Dominant
        if "segmentation_marketing" in df_filtered.columns and total_clients_filtre > 0:
            seg_dom_mkt = df_filtered["segmentation_marketing"].value_counts().sort("count", descending=True)["segmentation_marketing"][0]
            kpi2.metric("Segment Mkt Dominant", str(seg_dom_mkt))
        else:
            kpi2.metric("Segment Mkt Dominant", "N/A")

        # 3. % de Digital Autonomes
        if "seg_dig_auto" in df_filtered.columns and total_clients_filtre > 0:
            df_dig = df_filtered.filter(pl.col("seg_dig_auto").cast(pl.Utf8).str.to_lowercase().is_in(["oui", "1", "actif", "autonome"]))
            pct_dig = (len(df_dig) / total_clients_filtre) * 100
            kpi3.metric("% Digital Autonomes", f"{pct_dig:.1f} %")
        else:
            kpi3.metric("% Digital Autonomes", "N/A")

        # 4. Affinité Dominante
        if "segment_affinitaire" in df_filtered.columns and total_clients_filtre > 0:
            aff_dom = df_filtered["segment_affinitaire"].value_counts().sort("count", descending=True)["segment_affinitaire"][0]
            kpi4.metric("Affinité Dominante", str(aff_dom))
        else:
            kpi4.metric("Affinité Dominante", "N/A")

        # 5. Nombre de Conseillers actifs
        if "conseiller" in df_filtered.columns:
            nb_conseillers = df_filtered["conseiller"].n_unique()
            kpi5.metric("Nombre de Conseillers", f"{nb_conseillers}")
        else:
            kpi5.metric("Nombre de Conseillers", "N/A")

               # --- BLOC 2 : GRAPHIQUES DE RÉPARTITION ---
        st.markdown("---")
        st.subheader("📈 Analyses Des Segmentations & Âges")
        
        g1, g2 = st.columns(2)
        g3, g4 = st.columns(2)

        # Graphique 1 : Répartition Segmentation Marketing (Donut)
        with g1:
            if "segmentation_marketing" in df_filtered.columns and total_clients_filtre > 0:
                df_mkt = df_filtered["segmentation_marketing"].value_counts().to_pandas()
                fig_mkt = px.pie(df_mkt, values="count", names="segmentation_marketing", 
                                 title="Répartition Marketing", hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_mkt, use_container_width=True)

        # Graphique 2 : Répartition Segmentation Comportementale (Barres)
        with g2:
            if "segmentation_comportementale" in df_filtered.columns and total_clients_filtre > 0:
                df_comp = df_filtered["segmentation_comportementale"].value_counts().sort("count", descending=True).to_pandas()
                fig_comp = px.bar(df_comp, x="segmentation_comportementale", y="count", 
                                  title="Profils Comportementaux", text_auto=True,
                                  labels={"count": "Nombre de clients", "segmentation_comportementale": "Segment"})
                st.plotly_chart(fig_comp, use_container_width=True)

        # Graphique 3 : Répartition Principalisation (Donut)
        with g3:
            if "segmentation_principalisation" in df_filtered.columns and total_clients_filtre > 0:
                df_prin = df_filtered["segmentation_principalisation"].value_counts().to_pandas()
                fig_prin = px.pie(df_prin, values="count", names="segmentation_principalisation", 
                                  title="Niveau de Principalisation", hole=0.5,
                                  color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_prin, use_container_width=True)

        # Graphique 4 : Structure des âges par tranches (Avec conversion forcée sécurisée)
        with g4:
            if "age" in df_filtered.columns and total_clients_filtre > 0:
                # Sécurité : On force la conversion de l'âge en nombre au cas où il contient du texte ou des espaces
                df_age_clean = df_filtered.with_columns(
                    pl.col("age").cast(pl.Utf8).str.strip_chars().cast(pl.Int64, strict=False)
                ).filter(pl.col("age").is_not_null())

                if len(df_age_clean) > 0:
                    df_age = df_age_clean.with_columns(
                        pl.when(pl.col("age") < 25).then(pl.lit("18-24 ans"))
                        .when(pl.col("age") < 35).then(pl.lit("25-34 ans"))
                        .when(pl.col("age") < 50).then(pl.lit("35-49 ans"))
                        .when(pl.col("age") < 65).then(pl.lit("50-64 ans"))
                        .otherwise(pl.lit("65 ans et +"))
                        .alias("tranche_age")
                    )
                    df_age_dist = df_age["tranche_age"].value_counts().sort("tranche_age").to_pandas()
                    fig_age = px.bar(df_age_dist, x="tranche_age", y="count", 
                                     title="Structure par Tranches d'Âge", text_auto=True,
                                     color_discrete_sequence=["#2b5c8f"])
                    st.plotly_chart(fig_age, use_container_width=True)
                else:
                    st.info("La colonne 'age' ne contient pas de données numériques valides.")


        # --- BLOC 3 : CARTES KPI POUR LES TOPS CLIENTS (Nettoyage 0 ou 1) ---
        st.markdown("---")
        st.subheader("🎯 Focus Profils Cibles (Tops Indicateurs)")
        
        top_columns = [
            ("TOP_TERRITORIAL_ENGAGE", "🌍 Territorial Engagé"),
            ("TOP_OPTIMISATEUR_MULTIBANCARISE", "🔄 Optimisateur Multibanc."),
            ("TOP_JOUEUR_INVESTISSEUR", "🎲 Joueur Investisseur"),
            ("TOP_PRUDENT_INSTALLE", "🛡️ Prudent Installé"),
            ("TOP_PROFESSIONNEL_INDEPENDANT", "💼 Pro / Indépendant")
        ]

        cols_top = st.columns(len(top_columns))

        for idx, (col_name, label) in enumerate(top_columns):
            with cols_top[idx]:
                if col_name in df_filtered.columns and total_clients_filtre > 0:
                    # Sécurité : On nettoie le texte et on force en nombre pour intercepter les ' 1 ' ou ' 0 '
                    df_top_active = df_filtered.with_columns(
                        pl.col(col_name).cast(pl.Utf8).str.strip_chars().cast(pl.Int64, strict=False)
                    ).filter(pl.col(col_name) == 1)
                    
                    nb_top = len(df_top_active)
                    pct_top = (nb_top / total_clients_filtre) * 100 if total_clients_filtre > 0 else 0
                    
                    st.metric(
                        label=label,
                        value=f"{nb_top:,}".replace(",", " "),
                        delta=f"{pct_top:.1f}% du port.",
                        delta_color="normal"
                    )
                else:
                    st.metric(label=label, value="N/A", delta="Colonne absente")


        # --- BLOC 4 : EXTRACTION ET EXPORT CSV ---
        st.markdown("---")
        st.subheader("📥 Extraction des données filtrées")
        
        # Génération du CSV lourd au format point-virgule (conserve les filtres actuels)
        csv_data = convert_df_to_csv(df_filtered)

        st.download_button(
            label=f"💾 Télécharger l'extraction complète des {total_clients_filtre:,} lignes (CSV ;)",
            data=csv_data,
            file_name="extraction_portefeuille.csv",
            mime="text/csv",
            use_container_width=True
        )


        # --- BLOC 5 : APERÇU SÉCURISÉ DES DONNÉES ---
        st.markdown("---")
        st.subheader(f"📋 Aperçu visuel (Limité aux 100 premiers clients sur {total_clients_filtre:,})")
        # On affiche proprement les colonnes bien séparées
        st.dataframe(df_filtered.head(100).to_pandas(), use_container_width=True)

    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'analyse : {e}")
        st.info("Vérifiez que votre fichier utilise bien le point-virgule (;) comme séparateur.")

else:
    st.info("👋 En attente de votre fichier CSV dans la barre latérale pour générer le dashboard d'analyse.")
