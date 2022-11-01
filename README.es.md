<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="https://bicchiere.sytes.net/static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logotipo"/></p>

## Otro micro-marco web de Python (WSGI)

Siguiendo los pasos de [Flask](https://flask.palletsprojects.com/en/2.1.x/) y [Bottle](https://bottlepy.org/docs/dev/), añadiendo un poco de sabor italiano :- )

## Instalar
```bash
pip install bicchiere
```

## [Aplicación de demostración del proyecto](https://bicchiere.sytes.net)

Versión actual: 1.9.0

<p>
    <a href="https://pypi.python.org/pypi/bicchiere" target="_blank" rel="nofollow"><img alt="GitHub tag (latest by date)" src="https://img.shields.io/github/v/tag/sandy98/bicchiere?color=%230cc000&label=bicchiere"></a>           
    &nbsp;&nbsp;&nbsp;
    <a href="https://pepy.tech/project/bicchiere" rel="nofollow" target="_blank">
        <img src="https://static.pepy.tech/personalized-badge/bicchiere?period=total&units=international_system&left_color=black&right_color=blue&left_text=Downloads"/>
    </a>
</p>

## Una gota de Bicchiere

```pithon
from bicchiere import Bicchiere

app = Bicchiere()
o
app = Bicchiere("La mia bella app")

@app.get("/")
def main():
    return "Bon giorno, cosa bevete oggi?"
    
if __name__ == "__main__":
    #Esto ejecutará el servidor predeterminado en http://localhost:8086
    app.run()
```

... y esto es el clásico **Hola, mundo** versión WSGI, para todo lo demás, consulte [Bicchiere Wiki](https://github.com/sandy98/bicchiere/wiki)

Bueno en realidad no. Un poco de justificación está en orden aquí.

Entonces, ¿por qué Bicchiere?

- Por un lado, reinventar la rueda no solo es divertido, sino también muy educativo, así que, por todos los medios, ¡hazlo!

- Me gustan Flask and Bottle. Mucho. Ambos tienen cosas que aprecio mucho, la sencillez en el primero lugar. Pero no termina ahí.
- También está el enfoque de archivo único/sin dependencias (Bottle), que pretendo imitar con Bicchiere. Aunque no es algo obligatorio, me gusta así.
- Sesiones integradas (Flask). Aunque el usuario de la biblioteca debe ser libre de elegir lo que quiera con respecto a las sesiones o cualquier otro componente de la aplicación, creo que el manejo de sesiones es una de esas cosas imprescindibles en cualquier aplicación web en estos días. Entonces, proporcioné un mecanismo básico de manejo de sesión, en 3 variantes: memoria, sistema de archivos y sqlite. Esto fue lo máximo que se pudo hacer sin salirse de los límites de la biblioteca estándar de Python. Detalles sobre esto en [la wiki (en construcción)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-session)
- Mecanismo de plantilla incorporado (Bottle). Se aplican consideraciones similares. En mi opinión, esto también es imprescindible, independientemente de cuán micro sea el marco/biblioteca. Por otra parte, el usuario final debe ser libre de elegir. Como buen middleware compatible con WSGI, Bicchiere no se interpone en el camino del usuario si este prefiere usar [Mako](https://www.makotemplates.org/), [Jinja2](https://jinja.palletsprojects .com/en/3.1.x/), [Genshi](https://genshi.edgewall.org/) o lo que quiera. Detalles en [la wiki (en construcción)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-templates)
- Manejo de WebSockets: para mí, esta es la fruta del pastel, por varias razones:
    1. Se ha dicho que no se puede hacer bajo WSGI, razón de más para hacerlo.
    2. La comunicación en tiempo real parece otra necesidad imperiosa en el panorama actual del desarrollo de aplicaciones web.
    3. Por otra parte, es muy divertido. Mucho dolor también...
En cualquier caso, Bicchiere viene con soporte nativo para WebSocket, recién sacado del horno :-))
Detalles en [la wiki (en construcción)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-Websocket) . Lamentablemente, [la aplicación original de demostración](https://bicchiere.eu.pythonanywhere.com) no funcionará con websockets, porque **Pythonanywhere** aún no ha implementado la función. A partir de ahora, hay un espejo en [bicchiere.sytes.net](http://bicchiere.sytes.net) que funciona bien, prueba en la página de inicio y todo. En cualquier caso, estos problemas están relacionados con la configuración del proxy inverso y no tienen nada que ver con la aplicación/biblioteca en sí.
- Y aún así, hay muchas cosas que mencionar. Más por venir...