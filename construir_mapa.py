"""
Construir la tabla de equivalencias DOT -> IATA
===============================================

Para qué sirve
--------------
En octubre de 2015 el dataset trae el identificador numérico del DOT (10397)
en lugar del código IATA (ATL). Para arreglarlo hace falta una tabla de
equivalencia entre los dos códigos, y esa tabla NO existe publicada.

Este script la construye, la verifica y la deja lista para pegar dentro de
`fnNormalizaAeropuerto` en Power Query.

Fuentes (descargar y dejar junto a este script)
-----------------------------------------------
  L_AIRPORT_ID.csv   Bureau of Transportation Statistics, lookup oficial.
                     transtats.bts.gov -> Aviation -> Lookup Tables
                     Trae: código numérico + descripción de texto.
                     NO trae el código IATA. Ese es el problema.

  airport-codes.csv  Catálogo público de códigos IATA (datahub.io / ourairports).
                     Trae: código IATA, nombre, ciudad, estado y TIPO de
                     aeropuerto. El tipo es clave para verificar después.

El único puente entre las dos fuentes es EL NOMBRE del aeropuerto, y los
nombres no coinciden literalmente. De ahí todo lo que hace este script.

Uso
---
    python3 construir_mapa.py
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
CASO = AQUI.parent                      # donde está flights.csv


# ---------------------------------------------------------------- PASO 1
# Normalizar los nombres para poder compararlos
# ------------------------------------------------------------------------
# "Hartsfield-Jackson Atlanta International"  y
# "Hartsfield Jackson Atlanta International Airport"  son el mismo sitio.
# Hay que reducir los dos a la misma forma antes de compararlos.

RELLENO = [" international", " intl", " regional", " municipal", " airport",
           " field", " airpark", " air park", " metropolitan", " metro",
           " county", " memorial", " national", " airfield", " air terminal",
           " terminal", " airbase", " air force base", " afb", " station",
           " seaplane base"]


def normaliza(s):
    if not isinstance(s, str):
        return ""
    # OJO AL ORDEN: guiones y barras -> espacio ANTES de quitar acentos.
    # Si se hace al revés, el guión largo de "Minneapolis-Saint Paul"
    # desaparece sin dejar espacio y queda "minneapolissaint paul".
    s = re.sub(r"[‐-―\-/&]", " ", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = " " + s.lower() + " "
    for w in RELLENO:                   # quitar palabras que no distinguen nada
        s = s.replace(w, " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(saint)\b", "st", s)
    return " ".join(s.split())


def jaccard(a, b):
    """Parecido entre dos nombres: palabras en común / palabras totales.
    1,0 = idénticos. 0,6 = dos de cada tres palabras coinciden."""
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if (A | B) else 0.0


# ---------------------------------------------------------------- PASO 2
# Cargar y preparar las dos fuentes
# ------------------------------------------------------------------------

bts = pd.read_csv(AQUI / "L_AIRPORT_ID.csv", dtype=str)

# La descripción viene como "Atlanta, GA: Hartsfield-Jackson Atlanta International"
partes = bts["Description"].str.split(":", n=1, expand=True)
bts["apt_name"] = partes[1].str.strip()
ciudad_estado = partes[0].str.strip().str.rsplit(",", n=1, expand=True)
bts["city"] = ciudad_estado[0].str.strip()
bts["state"] = ciudad_estado[1].str.strip()
bts = bts.rename(columns={"Code": "DOT_CODE"})
bts = bts[bts["state"].str.len().eq(2)].copy()        # solo EE. UU.
bts["k_city"] = bts["city"].str.split("/").str[0].map(normaliza)
bts["k_name"] = bts["apt_name"].map(normaliza)
bts["comercial"] = bts["apt_name"].str.contains(
    "International|Regional|Municipal|Field|Airport", case=False, na=False)

ac = pd.read_csv(AQUI / "airport-codes.csv", dtype=str, low_memory=False)
ac = ac[ac["iso_country"].isin(["US", "PR", "VI", "GU", "AS", "MP"])
        & ac["iata_code"].notna()
        & ac["iata_code"].str.len().eq(3)].copy()
ac["state"] = ac["iso_country"].where(ac["iso_country"] != "US",
                                      ac["iso_region"].str.split("-").str[1])
ac["k_city"] = ac["municipality"].str.split("/").str[0].str.split(",").str[0].map(normaliza)
ac["k_name"] = ac["name"].map(normaliza)
ac = ac.rename(columns={"iata_code": "IATA_CODE"})

# Ranking de tamaño: sirve para desempatar y, sobre todo, para VERIFICAR
TAM = {"large_airport": 0, "medium_airport": 1, "small_airport": 2,
       "seaplane_base": 3, "heliport": 4, "closed": 5, "balloonport": 6}
ac["tam"] = ac["type"].map(TAM).fillna(9).astype(int)
ref = ac[["IATA_CODE", "state", "k_city", "k_name", "name",
          "municipality", "type", "tam"]]

print(f"BTS: {len(bts):,} aeropuertos    Catálogo IATA: {len(ref):,}")


# ---------------------------------------------------------------- PASO 3
# Emparejar en cuatro pasadas, de la más exigente a la más permisiva
# ------------------------------------------------------------------------
# Cada pasada trabaja SOLO sobre lo que quedó sin resolver en la anterior.
# Así los emparejamientos dudosos nunca pisan a los seguros.

resultados, resueltos = [], set()


def pasada(claves, umbral, etiqueta, solo_comerciales=False, por_tamano=False):
    global resueltos
    resto = bts[~bts["DOT_CODE"].isin(resueltos)]
    if solo_comerciales:
        resto = resto[resto["comercial"]]
    if resto.empty:
        return

    cand = (resto.merge(ref, on=claves, how="inner", suffixes=("_b", "_a"))
            if claves else resto.merge(ref, how="cross", suffixes=("_b", "_a")))
    if cand.empty:
        return

    cand["score"] = [jaccard(x, y) for x, y in zip(cand["k_name_b"], cand["k_name_a"])]

    if por_tamano:
        # Última red: el aeropuerto cambió de nombre y el parecido no sirve.
        # Solo vale si en esa ciudad hay UN ÚNICO aeropuerto grande o mediano.
        cand = cand[cand["tam"] <= 1]
        minimo = cand.groupby("DOT_CODE")["tam"].transform("min")
        unicos = cand.groupby("DOT_CODE")["tam"].transform(lambda s: (s == s.min()).sum())
        cand = cand[(cand["tam"] == minimo) & (unicos == 1)]
    else:
        cand = cand[cand["score"] >= umbral]

    if cand.empty:
        return

    cand["pasada"] = etiqueta
    cand["mismo_estado"] = (cand["state_b"] == cand["state_a"]).astype(int) \
        if "state_b" in cand.columns else 1
    cand = (cand.sort_values(["DOT_CODE", "score", "mismo_estado", "tam"],
                             ascending=[True, False, False, True])
                .drop_duplicates("DOT_CODE", keep="first"))
    resultados.append(cand)
    resueltos |= set(cand["DOT_CODE"])
    print(f"  pasada {etiqueta:<20} +{len(cand):>5}   (acumulado {len(resueltos):,})")


print("\nPASO 3 · Emparejando")
pasada(["state", "k_city"], 0.40, "1 ciudad+nombre")
pasada(["state"],           0.60, "2 estado+nombre")
pasada(None,                1.00, "3 nombre exacto")
pasada(["state", "k_city"], 0.00, "4 renombrados", solo_comerciales=True, por_tamano=True)

mapa = pd.concat(resultados)[["DOT_CODE", "IATA_CODE", "city", "state",
                              "apt_name", "type", "score", "pasada"]]
mapa.columns = ["DOT_CODE", "IATA_CODE", "CITY", "STATE",
                "AIRPORT_NAME", "AIRPORT_SIZE", "SCORE", "PASADA"]


# ---------------------------------------------------------------- PASO 4
# Correcciones manuales, todas verificadas a mano contra el lookup del BTS
# ------------------------------------------------------------------------
# CAUSA RAÍZ COMÚN: el catálogo IATA describe los aeropuertos de HOY y los
# datos son de 2015. Williston (ND) es el ejemplo claro: en 2015 volaba
# desde Sloulin Field (ISN); en 2019 abrió un aeropuerto nuevo (XWA) y el
# catálogo actual apunta allí. El emparejamiento acierta la ciudad y falla
# el año. Es un problema de datos maestros con vigencia temporal.

CORRECCIONES = {
    "12389": "ISN",   # Williston ND — asignaba XWA (abierto en 2019)
    "13158": "MAF",   # Midland TX — asignaba MDD (Midland Airpark, pequeño)
    "13433": "MOT",   # Minot ND — asignaba MIB (base aérea)
    "13459": "MQT",   # Marquette MI — asignaba HYR (otro estado).
                      # OJO: el catálogo trae SAW como local_code (FAA); el IATA es MQT.
    "15624": "VPS",   # Valparaiso FL — asignaba ECP (abierto en 2010, otra ciudad)
    "12016": "GUM",   # Guam — territorio, fuera del emparejamiento por estado
    "13796": "OAK",   # Oakland CA
    "14027": "PBI",   # West Palm Beach FL
}

for codigo, iata in CORRECCIONES.items():
    if (mapa["DOT_CODE"] == codigo).any():
        mapa.loc[mapa["DOT_CODE"] == codigo, "IATA_CODE"] = iata
    else:
        fila = bts.loc[bts["DOT_CODE"] == codigo]
        if len(fila):
            mapa = pd.concat([mapa, pd.DataFrame([{
                "DOT_CODE": codigo, "IATA_CODE": iata,
                "CITY": fila.iloc[0]["city"], "STATE": fila.iloc[0]["state"],
                "AIRPORT_NAME": fila.iloc[0]["apt_name"],
                "AIRPORT_SIZE": "large_airport", "SCORE": 1.0,
                "PASADA": "0 corrección"}])])

mapa = mapa.sort_values("DOT_CODE").reset_index(drop=True)
print(f"\nEmparejados: {len(mapa):,}   IATA distintos: {mapa.IATA_CODE.nunique():,}")


# ---------------------------------------------------------------- PASO 5
# Añadir a mano los que el emparejamiento no resolvió
# ------------------------------------------------------------------------
# El PASO 6 dirá cuáles faltan. Se buscan uno a uno en L_AIRPORT_ID.csv, se
# comprueban contra el catálogo IATA y se añaden aquí. Fueron siete.

FALTANTES = {
    "10157": "ACV",   # Arcata/Eureka, CA
    "11865": "GCC",   # Gillette Campbell County, WY
    "11982": "GRK",   # Robert Gray AAF, Killeen TX
    "12278": "ICT",   # Wichita Mid-Continent, KS
    "14307": "PVD",   # T. F. Green State, Providence RI
    "14543": "RKS",   # Rock Springs Sweetwater County, WY
    "14711": "SCE",   # University Park, State College PA
}

for codigo, iata in FALTANTES.items():
    if (mapa["DOT_CODE"] == codigo).any():
        mapa.loc[mapa["DOT_CODE"] == codigo, "IATA_CODE"] = iata
    else:
        fila = bts.loc[bts["DOT_CODE"] == codigo]
        mapa = pd.concat([mapa, pd.DataFrame([{
            "DOT_CODE": codigo, "IATA_CODE": iata,
            "CITY": fila.iloc[0]["city"], "STATE": fila.iloc[0]["state"],
            "AIRPORT_NAME": fila.iloc[0]["apt_name"],
            "AIRPORT_SIZE": "medium_airport", "SCORE": 1.0,
            "PASADA": "0 manual"}])])

mapa = mapa.sort_values("DOT_CODE").reset_index(drop=True)
mapa.to_csv(AQUI / "dot_to_iata_map.csv", index=False)
print(f"\nMapa completo: {len(mapa):,} equivalencias  ->  dot_to_iata_map.csv")


# ---------------------------------------------------------------- PASO 6
# Quedarse solo con los códigos que aparecen de verdad en el dataset
# ------------------------------------------------------------------------
# El mapa completo tiene ~1.700 equivalencias. Meterlas todas en el código M
# sería cargar el .pbix con 1.400 entradas que nunca se van a usar.

print("\nPASO 6 · Recortar a lo que aparece en el dataset")
vuelos = pd.read_csv(CASO / "flights.csv",
                     usecols=["ORIGIN_AIRPORT", "DESTINATION_AIRPORT"],
                     dtype="string")
codigos = pd.unique(pd.concat([vuelos.ORIGIN_AIRPORT, vuelos.DESTINATION_AIRPORT]))
codigos = sorted(c for c in codigos if isinstance(c, str) and c.isdigit())
print(f"  Códigos DOT distintos en el fichero: {len(codigos)}")

usado = mapa[mapa.DOT_CODE.isin(codigos)].sort_values("DOT_CODE").reset_index(drop=True)
faltan = sorted(set(codigos) - set(usado.DOT_CODE))
print(f"  Sin equivalencia: {len(faltan)}   <- debe ser 0"
      + ("" if not faltan else f"\n  {faltan}\n  Búscalos en L_AIRPORT_ID.csv y añádelos a FALTANTES."))
if faltan:
    raise SystemExit("Faltan equivalencias: no sigas hasta resolverlas.")


# ---------------------------------------------------------------- PASO 7
# Verificar. Tres comprobaciones que NO dependen unas de otras.
# ------------------------------------------------------------------------
# Un emparejamiento por similitud siempre acierta casi todo y falla en
# algunos, y los que fallan NO AVISAN: devuelven un código que existe y
# parece válido. Por eso no se entrega nada de esto sin verificarlo, y por
# eso se verifica de tres formas independientes. Se comprueban las 307 que
# de verdad se usan, no las 1.700 del mapa completo (muchas de ellas son
# aeropuertos históricos que no vuelan en 2015).

print("\nPASO 7 · Verificación de las equivalencias que se usan")
usadas = dict(zip(usado.DOT_CODE, usado.IATA_CODE))

# 7a · Hubs conocidos. Lista escrita a mano: se saben de antemano.
#      Detecta errores justo donde más daño harían, en los que más vuelan.
HUBS = {"10397": "ATL", "13930": "ORD", "11298": "DFW", "12892": "LAX",
        "11292": "DEN", "12478": "JFK", "14771": "SFO", "14107": "PHX",
        "13487": "MSP", "11433": "DTW", "14747": "SEA", "12266": "IAH",
        "11057": "CLT", "13204": "MCO", "12889": "LAS", "14869": "SLC",
        "11618": "EWR", "10721": "BOS", "12953": "LGA", "13232": "MDW",
        "14679": "SAN", "10693": "BNA", "11278": "DCA", "12264": "IAD",
        "12191": "HOU", "14683": "SAT", "13495": "MSY", "10529": "BDL",
        "12451": "JAX", "14524": "RIC", "10821": "BWI", "14492": "RDU",
        "13796": "OAK", "14570": "RNO", "11066": "CMH", "14057": "PDX",
        "14027": "PBI", "10800": "BUR", "12173": "HNL", "11540": "ELP",
        "13851": "OKC", "14730": "SDF", "11697": "FLL", "13303": "MIA",
        "14122": "PIT", "13198": "MCI", "11193": "CVG", "10423": "AUS",
        "10140": "ABQ", "10299": "ANC", "11042": "CLE", "12339": "IND",
        "13342": "MKE", "14635": "RSW", "14843": "SJU", "14893": "SMF",
        "13830": "OGG", "12016": "GUM"}
comprobables = {c: e for c, e in HUBS.items() if c in usadas}
fallos = [(c, usadas[c], e) for c, e in comprobables.items() if usadas[c] != e]
print(f"  7a hubs conocidos     {len(comprobables) - len(fallos)}/{len(comprobables)} correctos"
      + ("" if not fallos else f"   <- FALLOS (dot, asignado, correcto): {fallos}"))

# 7b · Ningún código IATA puede aparecer dos veces: dos números del DOT
#      apuntando al mismo sitio significa que uno de los dos está mal.
dups = usado[usado.duplicated("IATA_CODE", keep=False)]
print(f"  7b IATA duplicados    {len(dups)}   <- debe ser 0")
if len(dups):
    print(dups[["DOT_CODE", "IATA_CODE", "CITY", "AIRPORT_NAME"]].to_string(index=False))

# 7c · Coherencia de tipo: un aeropuerto con decenas de miles de vuelos no
#      puede haber emparejado con una pista pequeña o un helipuerto.
print("  7c tipos:", usado.AIRPORT_SIZE.value_counts().to_dict())
raros = usado[usado.AIRPORT_SIZE.isin(["heliport", "closed", "balloonport"])]
print(f"     tipos imposibles   {len(raros)}   <- debe ser 0")

# 7d · La más importante y la que se olvida: cada IATA que produzcamos tiene que
#      existir en airports.csv, el catálogo del propio caso. Si no existe, esa
#      fila quedará huérfana al relacionar y caerá en "(En blanco)" — que es
#      EXACTAMENTE el problema que estamos arreglando.
#      Este control detectó que 13459 se había mapeado a SAW, que es el código
#      local de la FAA; su código IATA real es MQT.
cat = set(pd.read_csv(CASO / "airports.csv")["IATA_CODE"].dropna())
fuera = sorted(set(usado.IATA_CODE) - cat)
print(f"  7d fuera del catálogo {len(fuera)}   <- debe ser 0"
      + ("" if not fuera else f"   {fuera}"))

if fallos or len(dups) or len(raros) or fuera:
    raise SystemExit("La verificación no pasa: revísalo antes de seguir.")


# ---------------------------------------------------------------- PASO 8
# Generar las dos cadenas de ancho fijo que van en fnNormalizaAeropuerto
# ------------------------------------------------------------------------
# Van embebidas en el código M para que el .pbix no dependa de ningún
# fichero externo. Ancho fijo (5 y 3) para que Power Query las parta con
# Splitter.SplitTextByRepeatedLengths sin necesidad de separadores.

cadena_dot = "".join(usado.DOT_CODE.str.zfill(5))
cadena_iata = "".join(usado.IATA_CODE)
assert len(cadena_dot) == len(usado) * 5
assert len(cadena_iata) == len(usado) * 3

(AQUI / "_m_codigos.txt").write_text(cadena_dot)
(AQUI / "_m_iatas.txt").write_text(cadena_iata)

print("\nPASO 8 · Cadenas para el código M")
print(f"  {len(usado)} equivalencias, cobertura 100%")
print(f"  _m_codigos.txt  {len(cadena_dot):,} caracteres  ({len(usado)} x 5)")
print(f"  _m_iatas.txt    {len(cadena_iata):,} caracteres  ({len(usado)} x 3)")
print("\nPega el contenido de cada fichero entre las comillas de Codigos e")
print("Iatas en fnNormalizaAeropuerto (01_PowerQuery_M.txt).")
