<h1 align="center">Bicchiere</h1>


<p align="center"><img title="Un bel bicchiere di Campari" src="https://bicchiere.sytes.net/static/img/bicchiere-rosso-2.jpg" alt="Bicchiere Logo"/></p>

## Un altro micro-framework Web Python (WSGI)

Seguendo le orme di [Flask](https://flask.palletsprojects.com/en/2.1.x/) e [Bottle](https://bottlepy.org/docs/dev/), aggiungendo un po' di italiano sapore :-)

## Installa
```bash
pip install bicchiere
```

## [Applicazione Demo Progetto](https://bicchiere.sytes.net)

Versione corrente: 1.8.3

<p>
    <a href="https://pypi.python.org/pypi/bicchiere" target="_blank" rel="nofollow"><img alt="GitHub tag (latest by date)" src="https://img.shields.io/github/v/tag/sandy98/bicchiere?color=%230cc000&label=bicchiere"></a>           
    &nbsp;&nbsp;&nbsp;
    <a href="https://pepy.tech/project/bicchiere" rel="nofollow" target="_blank">
        <img src="https://static.pepy.tech/personalized-badge/bicchiere?period=total&units=international_system&left_color=black&right_color=blue&left_text=Downloads"/>
    </a>
</p>

## Una goccia di Bicchiere

```pithon
from bicchiere import Bicchiere

app = Bicchiere()
oppure
app = Bicchiere("La mia bellissima app")

@app.get("/")
def main():
    return "Bon giorno, cosa bevete oggi?"
    
if __name__ == "__main__":
    #Questo eseguirà il server predefinito su http://localhost:8086
    app.run()
```

...e questa è la classica versione WSGI di **Hello World**, per tutto il resto vedi [Bicchiere Wiki](https://github.com/sandy98/bicchiere/wiki)

Beh, non proprio. Qui è necessario un po' di giustificazione.

Allora perché Bicchiere?

- Da un lato, reinventare la ruota non è solo divertente, ma anche molto educativo, quindi fallo con tutti i mezzi!

- Mi piace Flask and Bottle. Tanto. Entrambi hanno cose che apprezzo molto, la semplicità in primo luogo. Ma non finisce qui.
- Esiste anche l'approccio file singolo/nessuna dipendenza (Bottle), che intendo imitare con Bicchiere. Anche se non è obbligatorio, mi piace così.
- Sessioni integrate (Flask). Anche se l'utente della libreria dovrebbe essere libero di scegliere quello che vuole per quanto riguarda le sessioni o qualsiasi altro componente dell'applicazione, penso che la gestione delle sessioni sia uno di quei must in qualsiasi applicazione web di questi tempi. Quindi, ho fornito un meccanismo di base per la gestione delle sessioni, in 3 varianti: memoria, filesystem e sqlite. Questo era il massimo che si poteva fare senza uscire dai limiti della libreria standard di Python. Dettagli a riguardo su [il wiki (in costruzione)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-session)
- Meccanismo modello incorporato (Bottle). Si applicano considerazioni simili. IMO anche questo è un must, indipendentemente da quanto sia micro il framework/libreria. D'altra parte, l'utente finale deve essere libero di scegliere. Essendo un buon middleware conforme a WSGI, Bicchiere non intralcia l'utente se preferisce usare [Mako](https://www.makotemplates.org/), [Jinja2](https://jinja. palletsprojects .com/en/3.1.x/), [Genshi](https://genshi.edgewall.org/) o qualunque cosa lei/lui voglia. Dettagli su [il wiki (in costruzione)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-templates)
- Gestione dei WebSocket: per me questa è la ciliegina sulla torta, per diversi motivi:
    1. È stato detto che non può essere fatto sotto WSGI, motivo in più per farlo.
    2. La comunicazione in tempo reale sembra un altro imperativo nel panorama odierno dello sviluppo di applicazioni web.
    3. D'altra parte, è molto divertente. anche troppo doloroso...
In ogni caso Bicchiere viene fornito con supporto WebSocket nativo, appena sfornato :-))
Dettagli su [il wiki (in costruzione)](https://github.com/sandy98/bicchiere/wiki/Bicchiere-Websocket) . Sfortunatamente, [l'app demo da origine](https://bicchiere.eu.pythonanywhere.com) non funzionerà con i websocket, perché **Pythonanywhere** non ha ancora implementato la funzionalità. A partire da ora, c'è un mirror su [bicchiere.sytes.net](http://bicchiere.sytes.net) che funziona bene, prova la home page e tutto. In ogni caso, questi problemi sono correlati alle impostazioni del proxy inverso e non hanno nulla a che fare con l'app/libreria stessa.
- E ancora, ci sono molte cose da menzionare. E c'è dell'altro...