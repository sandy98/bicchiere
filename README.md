
<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="https://bicchiere.eu.pythonanywhere.com/static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logo"/></p>

## Yet another python web (WSGI) micro-framework

Following [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Bottle](https://bottlepy.org/docs/dev/) footsteps, adding a bit of italian flavor :-)

## Install  
```bash
pip install bicchiere
```

## [Project Demo App](https://bicchiere.eu.pythonanywhere.com)

Current version: 0.6.1

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

