"""
Tests unitaires des transformations du job bronze_to_silver
NYC Taxi Data Platform

Ces tests valident les principales règles de qualité et de transformation
appliquees lors du passage de la couche Bronze a la couche Silver :
  - filtrage des valeurs aberrantes
  - deduplication des enregistrements
  - pseudonymisation SHA-256 (conformite RGPD)
  - gestion des valeurs manquantes

Execution :  pytest test_transformations.py -v

Dependances : pyspark, pytest
  pip install pyspark pytest
"""

import hashlib
import pytest
from pyspark.sql import SparkSession, functions as F


# ---------------------------------------------------------------------------
# Fixture : session Spark locale partagee par tous les tests
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test_bronze_to_silver")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()


# ---------------------------------------------------------------------------
# Fonctions de transformation (a remplacer par un import de votre module reel,
# ex.  from src.bronze_to_silver import filter_outliers, deduplicate, ...)
# Elles sont redefinies ici pour rendre le fichier de test autonome.
# ---------------------------------------------------------------------------
def filter_outliers(df):
    """Supprime les courses aberrantes (distance/montant negatifs ou nuls,
    distance excessive)."""
    return df.filter(
        (F.col("trip_distance") > 0)
        & (F.col("trip_distance") < 100)
        & (F.col("total_amount") > 0)
    )


def deduplicate(df):
    """Supprime les enregistrements strictement dupliques."""
    return df.dropDuplicates()


def pseudonymize(df, column="VendorID"):
    """Pseudonymise une colonne par hachage SHA-256 (RGPD)."""
    return df.withColumn(column, F.sha2(F.col(column).cast("string"), 256))


def impute_missing(df, column, value):
    """Remplace les valeurs manquantes d'une colonne par une valeur donnee."""
    return df.fillna({column: value})


# ---------------------------------------------------------------------------
# Tests : filtrage des valeurs aberrantes
# ---------------------------------------------------------------------------
def test_filter_outliers_supprime_distances_negatives(spark):
    data = [
        (1, 5.0, 20.0),    # valide
        (2, -3.0, 15.0),   # distance negative -> rejete
        (3, 0.0, 10.0),    # distance nulle -> rejete
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])
    result = filter_outliers(df)
    assert result.count() == 1


def test_filter_outliers_supprime_montants_negatifs(spark):
    data = [
        (1, 5.0, 20.0),     # valide
        (2, 4.0, -8.0),     # montant negatif -> rejete
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])
    result = filter_outliers(df)
    assert result.count() == 1
    assert result.first()["total_amount"] == 20.0


def test_filter_outliers_supprime_distances_excessives(spark):
    data = [
        (1, 50.0, 120.0),    # valide
        (2, 250.0, 500.0),   # distance aberrante -> rejete
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])
    result = filter_outliers(df)
    assert result.count() == 1


# ---------------------------------------------------------------------------
# Tests : deduplication
# ---------------------------------------------------------------------------
def test_deduplicate_supprime_les_doublons(spark):
    data = [
        (1, 5.0, 20.0),
        (1, 5.0, 20.0),   # doublon exact
        (2, 3.0, 12.0),
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])
    result = deduplicate(df)
    assert result.count() == 2


def test_deduplicate_conserve_lignes_distinctes(spark):
    data = [
        (1, 5.0, 20.0),
        (1, 5.0, 21.0),   # meme VendorID mais montant different -> conserve
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])
    result = deduplicate(df)
    assert result.count() == 2


# ---------------------------------------------------------------------------
# Tests : pseudonymisation SHA-256 (RGPD)
# ---------------------------------------------------------------------------
def test_pseudonymize_masque_la_valeur_originale(spark):
    data = [(1, 5.0), (2, 3.0)]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance"])
    result = pseudonymize(df, "VendorID")
    valeurs = [r["VendorID"] for r in result.collect()]
    # La valeur d'origine "1" ou "2" ne doit plus apparaitre en clair
    assert "1" not in valeurs
    assert "2" not in valeurs


def test_pseudonymize_est_deterministe(spark):
    """Une meme entree doit toujours produire le meme hash (jointures possibles)."""
    data = [(1, 5.0)]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance"])
    result = pseudonymize(df, "VendorID")
    hash_obtenu = result.first()["VendorID"]
    hash_attendu = hashlib.sha256("1".encode()).hexdigest()
    assert hash_obtenu == hash_attendu


def test_pseudonymize_longueur_hash_sha256(spark):
    data = [(1, 5.0)]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance"])
    result = pseudonymize(df, "VendorID")
    # Un hash SHA-256 fait toujours 64 caracteres hexadecimaux
    assert len(result.first()["VendorID"]) == 64


# ---------------------------------------------------------------------------
# Tests : imputation des valeurs manquantes
# ---------------------------------------------------------------------------
def test_impute_missing_remplace_les_nuls(spark):
    data = [(1, 5.0), (2, None)]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance"])
    result = impute_missing(df, "trip_distance", 0.0)
    valeurs = [r["trip_distance"] for r in result.collect()]
    assert None not in valeurs
    assert 0.0 in valeurs


def test_impute_missing_ne_modifie_pas_les_valeurs_existantes(spark):
    data = [(1, 5.0), (2, None)]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance"])
    result = impute_missing(df, "trip_distance", 0.0)
    ligne_valide = result.filter(F.col("VendorID") == 1).first()
    assert ligne_valide["trip_distance"] == 5.0


# ---------------------------------------------------------------------------
# Test d'integration : chaine complete bronze -> silver
# ---------------------------------------------------------------------------
def test_pipeline_complet_bronze_to_silver(spark):
    data = [
        (1, 5.0, 20.0),
        (1, 5.0, 20.0),     # doublon
        (2, -3.0, 15.0),    # aberrant
        (3, 8.0, 30.0),
    ]
    df = spark.createDataFrame(data, ["VendorID", "trip_distance", "total_amount"])

    df = filter_outliers(df)     # retire la ligne aberrante
    df = deduplicate(df)         # retire le doublon
    df = pseudonymize(df, "VendorID")

    # Il ne doit rester que 2 lignes valides et distinctes
    assert df.count() == 2
    # La colonne VendorID doit etre pseudonymisee (64 caracteres)
    assert all(len(r["VendorID"]) == 64 for r in df.collect())
