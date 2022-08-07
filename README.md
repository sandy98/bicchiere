
<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logo"/></p>

## Yet another python web (WSGI) micro-framework

Following [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Bottle](https://bottlepy.org/docs/dev/) footsteps, adding a bit of italian flavor :-)

This is a work in progress at a very initial stage, so it won't be available to install through Python official repository ([PyPI](https://pypi.org/)) for a while.

So, as of now, only available means of installing/using it is through git clone, or just raw downloading bicchiere.py as Bicchiere follows the footsteps of Bottle.py in the sense of being a single file framework.

## [Project home page](https://bicchiere.eu.pythonanywhere.com "Project Home Page - Demo App")

## A drop from Bicchiere

```python
from bicchiere import Bicchiere

app = Bicchiere(__name__)

@app.get("/")
def home():
    return "Bon giorno, bebiamo un bon bicchiere?"
    
if __name__ == "__main__":
    #This will run default server on http://localhost:8086
    app.run()
```

... and this is just about the classical WSGI **Hello, World** but there's more to come...

