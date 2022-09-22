
<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="https://bicchiere.eu.pythonanywhere.com/static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logo"/></p>

## Yet another Python web (WSGI) micro-framework

Following [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Bottle](https://bottlepy.org/docs/dev/) footsteps, adding a bit of italian flavor :-)

## Install  
```bash
pip install bicchiere
```

## [Project Demo App](https://bicchiere.eu.pythonanywhere.com)

Current version: 0.12.1

[![Downloads](https://pepy.tech/badge/bicchiere)](https://pepy.tech/project/bicchiere)

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
Details at [the wiki (under construction)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-Websocket) 