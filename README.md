# moulin-beat

Une sculpture cinétique qui écoute la musique et fait tourner des pales de
moulin au rythme détecté.

Le cœur du dispositif est un robot **DFRobot micro:Maqueen V4.2** détourné de sa
fonction : posé sur un berceau, roues en l'air, il ne roule plus. Chaque roue
devient un axe d'entraînement portant une croix de pales ou une gerbe de rubans.
Le **micro:bit v2** enfiché dessus écoute la pièce avec son microphone intégré,
détecte les temps, et pilote les deux moteurs pour que les pales pulsent,
tournoient ou s'inversent en mesure.

Pas de câble audio, pas de réseau, pas de fichier musical embarqué : le robot
réagit à ce qu'il entend, quel que soit la source.

## Ce qu'il faut

| Élément | Détail |
|---|---|
| micro:bit **v2** | obligatoire — le micro intégré n'existe pas sur le v1 |
| DFRobot micro:Maqueen V4.2 | le châssis à deux moteurs |
| Un berceau | boîte, socle imprimé, cale en bois : **les roues ne doivent pas toucher le sol** |
| Pales ou rubans | carton plume, plastique fin, rubans de satin |
| Alimentation | piles du Maqueen, ou USB si le robot reste près d'un ordinateur |

## Montage

Le point de conception à ne pas rater : **c'est une sculpture, pas un véhicule**.
Si les roues touchent une surface, le robot part en trombe au premier beat.
Voir [docs/montage.md](docs/montage.md) pour le berceau, la fixation des pales
et l'équilibrage.

## Installation

Le projet se flashe avec un `make`, depuis Linux :

```bash
make check    # le micro:bit est-il vu et accessible ?
make flash    # fusionne les modules et flashe le robot
```

`make flash` fusionne les quatre modules en un script unique, que `uflash`
dépose par le **volume USB de masse**. Cette voie ne touche jamais au port
série, donc elle fonctionne même quand le REPL est bloqué — ce qui arrive dès
que le programme tourne, ou qu'un autre outil tient le port.

`make modules` fait l'inverse : les modules restent séparés sur la carte, ce qui
est plus agréable pour bidouiller au REPL, mais dépend entièrement du port
série. À réserver au confort, pas au dépannage.

Si `make check` signale des permissions en `crw-rw-r--` sur `/dev/bus/usb/...`,
il manque une règle udev — voir [docs/linux.md](docs/linux.md).

Une alternative sans rien installer : ouvrir [python.microbit.org](https://python.microbit.org),
créer un fichier par module de `src/`, et flasher depuis le navigateur.

## Utilisation

Le programme démarre **toujours en pause**, un petit carré affiché sur la
matrice. C'est délibéré : au sortir du flash le robot est encore souvent sur la
table, et des roues qui se lancent seules le font tomber.

| Commande | Effet |
|---|---|
| **bouton B** | démarrer / mettre en pause |
| **bouton A** — en marche | motif suivant, son numéro s'affiche |
| **bouton A** — en pause | séquence de test des deux roues |
| **secousse** | arrêt d'urgence, retour en pause |

Le **test des roues** est le diagnostic à lancer quand rien ne tourne. Après un
compte à rebours de trois secondes — de quoi rattraper un robot posé sur une
table — il fait tourner la roue gauche seule, la droite seule, puis les deux, et
affiche `OK` si les ordres sont passés.

Attention à ce que ce `OK` signifie : il atteste que les trames I2C ont été
**acceptées**, rien de plus. Le robot n'a aucun retour sur la rotation réelle de
ses roues. Un `OK` sans qu'aucune roue ne bouge désigne l'alimentation, pas le
code — voir ci-dessous.

Un cœur bat sur la matrice à chaque temps détecté. C'est l'outil de réglage :
si le cœur bat en mesure, la chorégraphie suivra.

Après quatre secondes de silence les pales s'arrêtent seules, et le micro:bit
affiche un visage endormi.

## Les quatre motifs

| # | Motif | Mouvement | Rend le mieux avec |
|---|---|---|---|
| 1 | **ronde** | rotation continue, vitesse suivant l'énergie sonore | des rubans, déployés en disque par la force centrifuge |
| 2 | **pulsation** | une impulsion brève par temps, puis extinction | des pales rigides, dont on voit le quart de tour |
| 3 | **tourbillon** | rotation continue qui s'inverse tous les 4 temps | des rubans longs, qui se retournent sur l'accent |
| 4 | **balancier** | les deux côtés alternent, une roue par temps | une composition dissymétrique, plus organique |

Les motifs marqués `continu = True` (ronde, tourbillon) entretiennent une
rotation de fond que les temps viennent moduler. Les autres ne bougent **que**
sur un temps et retombent à zéro entre deux : dans le silence, ils laissent les
pales strictement immobiles.

## Réglages

Toute la sensibilité tient dans `src/beat.py` :

```python
beat.Detecteur(sensibilite=1.30, temps_mort=150, plancher=12)
```

- **sensibilite** — rapport au-dessus de la moyenne glissante pour déclarer un
  temps. Baisser rend plus réactif ; sous `1.15` la détection s'emballe sur du
  bruit continu.
- **temps_mort** — durée en ms d'aveuglement après un temps. Une caisse claire
  produit plusieurs pics rapprochés qu'il ne faut compter qu'une fois.
- **plancher** — niveau sonore minimal. **À monter en premier** si le robot
  s'agite dans une pièce silencieuse.

Le seuil est une moyenne glissante, pas une valeur fixe : le dispositif s'adapte
tout seul à une salle bruyante comme à un morceau doux.

## Architecture

```
src/
├── maqueen.py       moteurs : I2C 0x10, trame [moteur, sens, vitesse]
├── beat.py          détection d'énergie sur le micro, seuil adaptatif
├── choregraphie.py  les quatre motifs, sans aucun accès au matériel
└── main.py          boucle principale, boutons, sécurités
```

`choregraphie.py` ne parle jamais à l'I2C : un motif reçoit les temps et rend un
couple de vitesses. On peut donc écrire et tester une chorégraphie sans robot,
et l'ajouter au `REPERTOIRE` en fin de fichier.

## Tests

```bash
make test
```

Les tests rejouent une seconde de musique simulée dans chaque motif, sans
matériel : `tests/microbit.py` remplace le module du micro:bit par une horloge
que l'on fait avancer à la main. Ils vérifient que les vitesses restent dans les
bornes, que les pales bougent, que le tourbillon s'inverse bien sur la mesure,
et qu'un motif événementiel n'entraîne rien dans le silence — cette dernière
vérification a déjà attrapé un vrai défaut, une impulsion pleine puissance au
démarrage avant le moindre temps détecté.

## Sécurité

Des pales lancées à 255 sur un moteur à réducteur ont du couple. Quelques
principes tenus par le code, à ne pas défaire :

- démarrage en pause, jamais au flash ;
- arrêt d'urgence à la secousse, sans avoir à viser un bouton ;
- un `finally` coupe les moteurs même si le programme plante ;
- extinction automatique après quatre secondes de silence.

Côté matériel : pales légères et souples de préférence, bien équilibrées, et
rien qui dépasse du berceau à hauteur de visage.

## Le robot ne fait rien ?

Dans l'ordre : le programme démarre **en pause**, appuyer sur **B**. Puis
`make ls` pour vérifier que les quatre modules sont bien sur la carte. Puis
l'alimentation du châssis, si la matrice fait défiler `Maqueen muet`.

**Le cas qui trompe le plus.** Les beats s'affichent bien, le test des roues
répond `OK`, et pourtant rien ne tourne. Deux alimentations distinctes
cohabitent sur le Maqueen :

| Ce qui est alimenté | Par quoi |
|---|---|
| micro:bit et contrôleur I2C du châssis | le 3,3 V, donc **l'USB suffit** |
| étage de puissance des moteurs | **uniquement les piles**, via l'interrupteur du châssis |

Un châssis dont l'interrupteur est sur OFF accepte donc tous les ordres I2C sans
broncher et ne bouge pas d'un millimètre. Aucun garde-fou logiciel ne peut
distinguer ce cas d'un fonctionnement normal : `reveille()` teste la
communication, pas la puissance.

Le détail, ainsi qu'un piège matériel coûteux — le Maqueen ignore la première
trame I2C après sa mise sous tension — est dans [docs/linux.md](docs/linux.md).

## Licence

MIT — voir [LICENSE](LICENSE).
