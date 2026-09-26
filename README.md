#  Scraping de precios de móviles en MediaMarkt

Scraper que recoge **cada día** el precio de todos los smartphones de la
[categoría de móviles de MediaMarkt España](https://www.mediamarkt.es/es/category/smartphones-263.html)
y los va acumulando en un histórico, para poder analizar cómo evolucionan los precios y los descuentos.

Se ejecuta de forma automática con **GitHub Actions**, sin necesidad de tener ningún ordenador encendido.

##  Cómo funciona

1. Recorre todas las páginas de la categoría (`?page=1`, `?page=2`, …) con `requests`.
2. De cada página extrae los datos estructurados **JSON-LD** (schema.org) que la web incluye en el HTML:
   nombre, precio, valoración y URL. El precio original (tachado) se obtiene de la tarjeta de producto
   mediante sus atributos `data-test`.
3. Se detiene cuando una página ya no aporta productos nuevos.
4. Añade las filas del día a `datos/historico_precios.csv`. Si se ejecuta dos veces el mismo día,
   sustituye los datos de ese día en lugar de duplicarlos.

> **Por qué JSON-LD y no clases CSS:** la primera versión (Selenium + clases como `sc-f2f38da6-1 jTiKtv`)
> dejó de funcionar porque esas clases se generan automáticamente y cambian con cada despliegue de la web.
> Los datos JSON-LD y los atributos `data-test` son mucho más estables.

##  Datos

`datos/historico_precios.csv`: una fila por móvil y día.

| Columna | Descripción |
|---|---|
| `fecha` | Fecha de la captura (AAAA-MM-DD) |
| `id_producto` | Identificador del producto en MediaMarkt |
| `nombre` | Nombre completo del producto |
| `marca` | Marca (primera palabra del nombre) |
| `almacenamiento` | Capacidad de almacenamiento extraída del nombre (p. ej. `256 GB`) |
| `precio` | Precio actual en euros |
| `precio_original` | Precio antes del descuento (vacío si no hay oferta) |
| `descuento_pct` | Porcentaje de descuento |
| `moneda` | Moneda (`EUR`) |
| `valoracion` | Nota media de los clientes (0-5) |
| `num_valoraciones` | Número de valoraciones |
| `url` | Enlace al producto |

##  Ejecución en local

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python ScrappingMediaMarkt.py
```

El registro de cada ejecución se guarda en `logs/scraper.log`.

##  Ejecución automática

El workflow [`.github/workflows/scraper_diario.yml`](.github/workflows/scraper_diario.yml) se lanza
todos los días a las 07:00 UTC, ejecuta el scraper y guarda el CSV actualizado en el repositorio.
También se puede lanzar a mano desde la pestaña **Actions → Scraper diario MediaMarkt → Run workflow**.

##  Tecnologías

Python · requests · BeautifulSoup · pandas · GitHub Actions

##  Aviso

Proyecto con fines educativos y de portafolio. El scraper hace pocas peticiones, con pausas entre ellas,
para no sobrecargar la web.
