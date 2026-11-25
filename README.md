# Agenda institucional

Agregador de agendas oficiales de administraciones, partidos y entidades.
Recoge los actos de varias fuentes, los normaliza a un formato común,
detecta altas, cambios de hora y cancelaciones, y los publica ordenados
por día y lugar en una web estática.

No hay servidor ni base de datos. Un workflow de GitHub Actions ejecuta
el recolector varias veces al día, escribe un JSON en `docs/datos/` y lo
commitea al propio repositorio. GitHub Pages sirve `docs/` como web.

## Puesta en marcha

1. Crea un repositorio nuevo en GitHub y sube estos ficheros.
2. En Settings, Pages, elige la rama `main` y la carpeta `/docs`.
3. En Settings, Actions, General, Workflow permissions, marca
   *Read and write permissions*. Sin esto el workflow no puede commitear.
4. Ve a la pestaña Actions y lanza *Recolectar agendas* a mano con
   *Run workflow*. A partir de ahí se ejecuta solo cada dos horas.

En local

```bash
pip install -r requirements.txt
python -m recolector.main --dias-adelante 10 --dias-atras 1
python -m http.server -d docs 8000
```

## Cómo está organizado

```
recolector/
  modelo.py          Acto, cálculo de id y extracción de lugar
  fechas.py          lectura de fechas en prosa, catalán y castellano
  almacen.py         fusión con lo anterior y detección de cambios
  main.py            orquestador y CLI
  fuentes/
    base.py          clase base, descarga con pausa y cabecera honesta
    moncloa.py       agenda del Gobierno de España, una URL por día
    acn.py           previsions de l'ACN, listado del día
    ajbcn.py         convocatòries de premsa de l'Ajuntament de Barcelona
herramientas/
  volcar.py          descarga una URL y guarda el HTML para inspeccionarlo
docs/
  index.html         la web
  datos/actos.json   generado por el recolector
  datos/cambios.json histórico de las últimas 500 modificaciones
```

## Cómo funciona la detección de cambios

El identificador de un acto se calcula con fuente, fecha, persona y
título normalizado, deliberadamente sin la hora. Así, si Moncloa mueve
un acto de las 10:00 a las 12:30, el acto se reconoce como el mismo y se
marca como `modificado` en lugar de aparecer como uno nuevo.

Cada pasada compara solo los días que ha visitado. Lo que estaba y ya no
aparece se marca `cancelado` en lugar de borrarse, para que quede
rastro. Todo queda además en `cambios.json` y en el historial de commits
de git, que es un registro de auditoría gratis.

La contrapartida es que si una fuente reescribe el texto de un acto a
fondo, se verá como una baja más un alta. Es asumible y se nota a simple
vista en la web.

## Qué se vigila, en config.yaml

Todo lo que se monitoriza vive en `config.yaml`, no en el código. Hay dos
bloques. `temas` agrupa palabras clave con sus variantes en castellano y
catalán, porque las fuentes están en los dos idiomas y conviene que
"residus" y "residuos" cuenten como lo mismo. `fuentes` lista cada web
con las personas y los temas que interesan de ella.

Un acto se marca relevante si menciona a una persona vigilada o si casa
con alguna palabra de alguno de sus temas. Una fuente sin personas ni
temas declarados da por relevante todo lo suyo, que es lo que interesa
por ejemplo en las convocatorias de prensa del Ayuntamiento.

Nada se descarta nunca. Lo no relevante se guarda igual, marcado, y en
la web se ve desapretando el botón *Solo lo que vigilo*. Así, cuando un
filtro se quede corto, se nota y se corrige en el yaml sin volver a
recolectar.

El campo `activa` controla qué fuentes entran en la recolección. Las que
aún no tienen parser están en `false`.

## Dos maneras de publicar agenda

Hay fuentes con una URL por día, como La Moncloa, y fuentes que son un
listado, como la ACN o las convocatorias del Ayuntamiento. Las primeras
se recorren día a día. Las segundas se visitan una vez por pasada y se
quedan con las fechas que el listado llegue a mostrar.

Eso cambia la reconciliación, y por eso cada fuente declara en
`ambito_fechas` qué días ha mirado de verdad. Un día que una fuente no
ha llegado a enseñar no se toca, para no marcar como cancelado lo que
en realidad no se ha visto.

## Preparar una fuente nueva

Antes de escribir nada, mira cómo publica esa web de verdad

```bash
python herramientas/volcar.py https://la-web/agenda volcado.html
```

Guarda el HTML y avisa si la página parece montarse con JavaScript. Si
es el caso, no hace falta un navegador sin cabeza. Abre la pestaña de
red del navegador, busca la llamada que trae los datos en JSON y tira
de esa, que además es más estable que el HTML.

## Añadir una fuente nueva

Antes de escribir un parser, busca si esa institución publica la agenda
en datos abiertos, en iCal o en RSS. Mucha administración lo hace y es
infinitamente más estable que raspar HTML. Mira en datos.gob.es y en el
portal de transparencia del organismo.

Si toca raspar, crea `recolector/fuentes/mifuente.py`

```python
from ..modelo import Acto
from .base import Fuente

class MiFuente(Fuente):
    clave = "mifuente"
    nombre = "Agenda de ..."
    organismo = "..."

    def recolectar_dia(self, fecha):
        html = self.descargar(f"https://...{fecha:%Y%m%d}")
        # devuelve una lista de Acto
        return []
```

y regístrala en `recolector/fuentes/__init__.py`. El resto, fusión,
detección de cambios y web, funciona sin tocar nada más.

Candidatas razonables para la siguiente tanda. Govern de Catalunya,
Parlament de Catalunya, Congreso de los Diputados, Senado, Ayuntamiento
de Madrid, Ayuntamiento de Barcelona y las agendas de transparencia de
las comunidades autónomas.

## Sobre los parsers de HTML

El de La Moncloa no se apoya en clases CSS, que son lo primero que
cambia en un rediseño, sino en los encabezados `h2` con el nombre de la
persona y en el patrón de hora `09:00 h.`. Aun así, si algún día la
recolección devuelve cero actos, lo primero que hay que revisar es ese
fichero. El test de `tests/` usa una copia local de la página, así que
sirve para comprobar la lógica sin salir a la red.

## Buenas maneras

El `User-Agent` identifica el proyecto, hay una pausa de segundo y medio
entre peticiones y solo se piden unos pocos días por pasada. Son webs
públicas, pero conviene no castigarlas. Cada acto guarda la URL de
origen, que además es lo que hace el agregador fiable.
