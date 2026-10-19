# op0p_catbridge

Pont CAT local pour le cluster [cluster.op0p.be](https://cluster.op0p.be) (OP0P
CC-Cluster) : permet de cliquer une fréquence depuis le cluster (ou depuis un
téléphone/tablette sur le même réseau WiFi) et de faire commuter la radio
connectée à l'ordinateur via Hamlib/rigctld.

Ce dépôt sert uniquement à fabriquer automatiquement un exécutable Windows
autonome (`PontCAT-OP0P.exe`, aucune installation de Python requise) via
GitHub Actions à chaque mise à jour du fichier `op0p_catbridge.py`. Le
résultat apparaît dans l'onglet **Releases** du dépôt, et à l'adresse stable :

```
https://github.com/<utilisateur>/<ce-depot>/releases/latest/download/PontCAT-OP0P.exe
```

Voir la page [cluster.op0p.be/cat.html](https://cluster.op0p.be/cat.html) pour
le mode d'emploi complet.
