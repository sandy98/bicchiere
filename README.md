
<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="https://bicchiere.sytes.net/static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logo"/></p>

## Yet another Python web (WSGI) micro-framework

Following [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Bottle](https://bottlepy.org/docs/dev/) footsteps, adding a bit of italian flavor :-)

## Install  
```bash
pip install bicchiere
```

## [Project Demo App](https://bicchiere.sytes.net)

Current version: 1.9.1

<p>
    <a href="https://pypi.python.org/pypi/bicchiere" target="_blank" rel="nofollow"><img alt="GitHub tag (latest by date)" src="https://img.shields.io/github/v/tag/sandy98/bicchiere?color=%230cc000&label=bicchiere"></a>           
    &nbsp;&nbsp;&nbsp;
    <a href="https://pepy.tech/project/bicchiere" rel="nofollow" target="_blank">
        <img src="https://static.pepy.tech/personalized-badge/bicchiere?period=total&units=international_system&left_color=black&right_color=blue&left_text=Downloads"/>
    </a>
</p>


## A drop from Bicchiere

```python
from bicchiere import Bicchiere

app = Bicchiere()
or
app = Bicchiere("La mia bella App")

@app.get("/")
def home():
    return "Bon giorno, cosa bevete oggi?"
    
if __name__ == "__main__":
    #This will run default server on http://localhost:8086
    app.run()
```

... and this is just about the classical WSGI **Hello, World**, for everything else please refer to [Bicchiere Wiki](https://github.com/sandy98/bicchiere/wiki)

Well... not really. A bit of rationale is in order here.

So, why Bicchiere?

- For one thing, reinventing the wheel is not only fun but highly educational, so, by all means, do it!

- I like Flask and Bottle. A lot. Both have things that I highly appreciate, simplicity in the first 
  place. But it doesn't end there.
- There's also the single file/no dependencies approach (Bottle), which I intend to mimic with Bicchiere. Although not a   mandatory thing, I like  it that way. 
- Built-in sessions (Flask). Although the user of the library must be free to choose whatever he likes regarding sessions or any other component of the application for that matter, I think session-handling is one of those must-have things in any web app these days. So, I provided basic session handling mechanism, in 3 flavors: memory, filesystem, and sqlite. This was the most that could be done without falling out of the boundaries of the Python Standard Library. Details on this at [the wiki (under construction)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-session) 
- Built-in templating mechanism (Bottle). Similar considerations apply. In my opinion, this is also a must have, regardless how micro is the framework/library. Then again, end-user must be free to choose. As a good WSGI compliant middleware, Bicchiere doesn't come in the way of the user if he prefers to use [Mako](https://www.makotemplates.org/), [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/), [Genshi](https://genshi.edgewall.org/) or whatever he likes. Details at [the wiki (under construction)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-templates)
- WebSockets handling: to me, this is the fruit on the cake, for various reasons:
    1. It's been said that it can't be done under WSGI, reason the more to do it.
    2. Real time communication looks like another must have in the current landscape of web app development
    3. Then again, its a lot of fun. A lot of pain, too...
In any case, Bicchiere comes bundled with native WebSocket support - just taken out from the oven :-))
Details at [the wiki (under construction)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-Websocket) . Regretably, [the original Demo App](https://bicchiere.eu.pythonanywhere.com) won't work with websockets, because **Pythonanywhere** hasn't yet implemented the feature. As of now, there's a mirror at [bicchiere.sytes.net](http://bicchiere.sytes.net) which works fine, test at the home page and all. In any case, these issues are related to reverse proxy configuration and have nothing to see with the app/library itself.
- And still, there's a lot of stuff to be mentioned. More to come...