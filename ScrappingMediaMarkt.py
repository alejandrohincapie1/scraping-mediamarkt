"""
Scraper diario de precios de moviles en MediaMarkt.es

- Recorre todas las paginas de la categoria Smartphones (?page=1, 2, 3...)
- Lee los datos del bloque JSON-LD que la web incluye en el HTML (nombre, precio,
  valoracion, url). Es mucho mas estable que las clases CSS (sc-xxxx), que cambian
  con cada despliegue de la web.
- Añade los resultados del dia a datos/historico_precios.csv (una fila por movil y dia).
  Si se ejecuta dos veces el mismo dia, sustituye los datos de ese dia.

Uso:  python ScrappingMediaMarkt.py
"""

import json
import logging
import random
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup as bs

try:
    # Usa los certificados de Windows (evita CERTIFICATE_VERIFY_FAILED en algunos equipos)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


URL_CATEGORIA = 'https://www.mediamarkt.es/es/category/smartphones-263.html'
MAX_PAGINAS = 200  # Tope de seguridad
REINTENTOS = 3

CARPETA = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA / 'datos'
CARPETA_LOGS = CARPETA / 'logs'
ARCHIVO_HISTORICO = CARPETA_DATOS / 'historico_precios.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/140.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
}

log = logging.getLogger('mediamarkt')


# Descarga de paginas

def descargar_pagina(sesion, numero_pagina):
    for intento in range(1, REINTENTOS + 1):
        try:
            respuesta = sesion.get(URL_CATEGORIA, params={'page': numero_pagina}, timeout=30)
            respuesta.raise_for_status()
            return respuesta.text
        except requests.RequestException as e:
            log.warning('Pagina %s, intento %s fallido: %s', numero_pagina, intento, e)
            time.sleep(5 * intento)
    raise RuntimeError(f'No se pudo descargar la pagina {numero_pagina}')


# Extraccion de datos

def texto_a_precio(texto):
    """'1.138,00€' -> 1138.0"""
    encontrados = re.findall(r'(\d[\d.]*,\d{2})\s*€', texto)
    if not encontrados:
        return None
    return float(encontrados[-1].replace('.', '').replace(',', '.'))


def id_producto(url):
    encontrado = re.search(r'-(\d+)\.html', url)
    return encontrado.group(1) if encontrado else url


def extraer_almacenamiento(nombre):
    encontrado = re.search(r'(\d+)\s*(GB|TB)(?!\s*(?:de\s*)?RAM)', nombre, re.I)
    return f'{encontrado.group(1)} {encontrado.group(2).upper()}' if encontrado else None


def extraer_productos(html):
    soup = bs(html, 'html.parser')

    # Precio original (tachado) de cada tarjeta, indexado por id de producto
    precios_originales = {}
    for tarjeta in soup.select('[data-test="mms-product-card"]'):
        enlace = tarjeta.select_one('a[href*="/product/"]')
        tachado = tarjeta.select_one('[data-test^="mms-strike-price"]')
        if enlace and tachado:
            precios_originales[id_producto(enlace['href'])] = texto_a_precio(tachado.get_text(' '))

    productos = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            datos = json.loads(script.string or '')
        except json.JSONDecodeError:
            continue
        if datos.get('@type') != 'ItemList':
            continue

        for elemento in datos.get('itemListElement', []):
            item = elemento.get('item', {})
            oferta = item.get('offers') or {}
            valoracion = item.get('aggregateRating') or {}
            url = item.get('url', '')
            pid = id_producto(url)
            precio = oferta.get('price')
            precio_original = precios_originales.get(pid)

            productos.append({
                'id_producto': pid,
                'nombre': item.get('name', '').strip(),
                'marca': item.get('name', '').replace('Móvil - ', '').split(' ')[0].capitalize(),
                'almacenamiento': extraer_almacenamiento(item.get('name', '')),
                'precio': float(precio) if precio is not None else None,
                'precio_original': precio_original,
                'descuento_pct': round((1 - float(precio) / precio_original) * 100, 1)
                                 if precio and precio_original else None,
                'moneda': oferta.get('priceCurrency'),
                'valoracion': valoracion.get('ratingValue'),
                'num_valoraciones': valoracion.get('reviewCount'),
                'url': url,
            })
    return productos


def scrapear_todo():
    sesion = requests.Session()
    sesion.headers.update(HEADERS)

    todos = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        productos = extraer_productos(descargar_pagina(sesion, pagina))
        nuevos = [p for p in productos if p['id_producto'] not in todos]

        # Pasada la ultima pagina, la web vuelve a mostrar la pagina 1: paramos
        if not nuevos:
            log.info('Pagina %s sin productos nuevos: fin', pagina)
            break

        for p in nuevos:
            todos[p['id_producto']] = p
        log.info('Pagina %s: %s productos (total %s)', pagina, len(nuevos), len(todos))
        time.sleep(random.uniform(1.5, 3.5))  # Pausa educada entre peticiones

    return list(todos.values())


# Guardado

def guardar(productos):
    CARPETA_DATOS.mkdir(exist_ok=True)
    hoy = date.today().isoformat()

    df_hoy = pd.DataFrame(productos)
    df_hoy.insert(0, 'fecha', hoy)

    if ARCHIVO_HISTORICO.exists():
        historico = pd.read_csv(ARCHIVO_HISTORICO, dtype={'id_producto': str})
        historico = historico[historico['fecha'] != hoy]  # Si se repite el dia, se sustituye
        df_hoy = pd.concat([historico, df_hoy], ignore_index=True)

    df_hoy.to_csv(ARCHIVO_HISTORICO, index=False, encoding='utf-8-sig')  # utf-8-sig: tildes OK en Excel


def main():
    CARPETA_LOGS.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.FileHandler(CARPETA_LOGS / 'scraper.log', encoding='utf-8'),
                  logging.StreamHandler()],
    )

    log.info('Inicio del scraping')
    productos = scrapear_todo()
    if not productos:
        # No se sobrescribe nada: probablemente la web ha cambiado o nos ha bloqueado
        raise RuntimeError('No se ha extraido ningun producto')

    guardar(productos)
    log.info('Guardados %s moviles en %s', len(productos), ARCHIVO_HISTORICO)


if __name__ == '__main__':
    main()
