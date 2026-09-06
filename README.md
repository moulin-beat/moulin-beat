# moulin-beat

Une sculpture cinétique qui écoute la musique et fait tourner des pales de
moulin au rythme détecté.

Le cœur du dispositif est un robot **DFRobot micro:Maqueen** détourné de sa
fonction : posé sur un berceau, roues en l'air, il ne roule plus. Chaque roue
devient un axe d'entraînement portant une croix de pales ou une gerbe de rubans.
Le **micro:bit v2** enfiché dessus écoute la pièce avec son microphone intégré,
détecte les temps, et pilote les moteurs pour que les pales pulsent, tournoient
ou s'inversent en mesure.

Pas de câble audio, pas de réseau, pas de fichier musical embarqué : le robot
réagit à ce qu'il entend, quelle que soit la source.

---

## Sommaire

- [Ce qu'il faut](#ce-quil-faut) · [Montage](#montage) · [Installation](#installation)
- [Commandes](#commandes) · [Les voyants](#les-voyants) · [Les cinq motifs](#les-cinq-motifs)
- [Comment ça marche](#comment-ça-marche) : [la détection](#1-la-détection-du-rythme), [les à-coups](#2-les-à-coups), [le silence](#3-quand-la-musique-sarrête)
- [Tous les réglages](#tous-les-réglages) — la référence complète
- [Alimentation](#alimentation) · [Architecture](#architecture) · [Tests](#tests)
- [Sécurité](#sécurité) · [Le robot ne fait rien ?](#le-robot-ne-fait-rien-)

---

## Ce qu'il faut

| Élément | Détail |
|---|---|
| micro:bit **v2** | obligatoire — le micro intégré et le logo tactile n'existent pas sur le v1 |
| DFRobot micro:Maqueen | testé sur une **Maqueen Lite V4.2** : phares sur P8/P12, 4 LED RGB sur P15, port de charge `CHG` |
| Un berceau | boîte, socle imprimé, cale en bois : **les roues ne doivent pas toucher le sol** |
| Pales ou rubans | carton plume, plastique fin, rubans de satin |
| Alimentation | accu lithium 3,7 V du châssis — voir [Alimentation](#alimentation), c'est le piège n°1 |

## Montage

Le point de conception à ne pas rater : **c'est une sculpture, pas un véhicule**.
Si les roues touchent une surface, le robot part en trombe au premier beat.
Voir [docs/montage.md](docs/montage.md) pour le berceau, la fixation des pales
et l'équilibrage.

## Installation

```bash
make check    # le micro:bit est-il vu et accessible ?
make flash    # fusionne les modules et flashe le robot
make test     # rejoue la détection et les motifs sur PC, sans robot
```

`make flash` fusionne les quatre modules de `src/` en un script unique, que
`uflash` dépose par le **volume USB de masse**. Cette voie ne touche jamais au
port série, donc elle fonctionne même quand le REPL est bloqué — ce qui arrive
dès que le programme tourne, ou qu'un autre outil tient le port.

`make modules` fait l'inverse : les modules restent séparés sur la carte, plus
agréable pour bidouiller au REPL, mais entièrement suspendu au port série. À
réserver au confort, pas au dépannage.

### `outils/flash.py` — pourquoi le flash ne passe plus par `uflash` seul

Le hex fusionné fait près de deux mégaoctets. Écrit par le canal ordinaire, il
part dans le cache du noyau et se vide paresseusement vers la carte ; si le
processus rend la main avant la fin, DAPLink voit un transfert qui traîne et
finit par déclarer `The transfer timed out`. Le micro:bit affiche alors un
visage triste et un **code 5xx** — les codes 500-599 sont des erreurs de
**flashage**, pas d'exécution
([codes d'erreur micro:bit](https://support.microbit.org/support/solutions/articles/19000016969-micro-bit-error-codes)).

`outils/flash.py` traite les trois volets du problème :

1. **`fsync()`** force l'écriture jusqu'au matériel avant de rendre la main.
   C'est la correction de fond : le transfert n'est plus à moitié dans le cache
   quand le processus se termine.
2. **Vérification** du verdict de DAPLink. `uflash` ne sait rien de ce qui se
   passe après la copie ; sans contrôle, `make flash` annonçait « Fait » pendant
   que la carte continuait de tourner sur **l'ancien programme**. Ça ressemble
   exactement à « ma modification n'a rien changé », et ça fait chercher le bug
   dans le code pendant des heures. Le verdict n'est lisible qu'**après** le
   remontage du volume, plus trois secondes de repos : vérifier trop tôt rend un
   faux succès, ce qui est pire que ne pas vérifier.
3. **Trois essais**, la panne étant déclarée « transient » par DAPLink elle-même.

En dernier ressort, il confirme par le port série que le programme tourne
vraiment. Si les trois essais échouent : changer de câble, brancher en direct
plutôt que sur un hub, puis `make modules`, qui passe par le port série et
ignore complètement le volume de masse.

Si `make check` signale des permissions en `crw-rw-r--` sur `/dev/bus/usb/...`,
il manque une règle udev — voir [docs/linux.md](docs/linux.md).

Alternative sans rien installer : ouvrir [python.microbit.org](https://python.microbit.org),
créer un fichier par module de `src/`, et flasher depuis le navigateur.

---

## Commandes

Le programme **se lance seul** dès la mise sous tension, après un compte à
rebours de deux secondes affiché sur la matrice. C'est ce qu'on veut d'une
installation qu'on branche et qu'on laisse : personne ne doit avoir à chercher un
bouton. En contrepartie, **brancher c'est lancer** — un robot posé à plat sur une
table part au premier temps. Les deux secondes servent à le rattraper ;
`COMPTE_A_REBOURS` les règle, ou les supprime.

| Commande | Effet |
|---|---|
| **bouton A** | motif suivant, de 1 à 5, **en boucle** |
| **bouton B** | amortissement, de 0 à 5, **en boucle** |
| **logo tactile** | remet l'amortissement par défaut, puis joue les tests |
| **secousse** | arrêt d'urgence — on en ressort par le logo |

Un bouton par réglage, et chacun tourne en boucle. Pas de sens de retour, pas
d'appui long : les deux réglages étant **affichés en permanence** sur la
matrice, on appuie jusqu'à voir ce qu'on veut. Avec six crans d'amortissement,
revenir à zéro depuis le maximum coûte un appui, pas dix.

### L'amortissement

Il dit à quel point la pale est arrêtée net entre deux temps, sur six crans de
**0 à 5**, 6 ms de contresens par cran.

| Niveau | Freinage | Rendu |
|---|---|---|
| **0** | aucun | roue libre, élan long, rotation fluide — le rythme ne se lit plus |
| **3** | 18 ms | réglage d'usine |
| **5** | 30 ms | frein sec, pale quasi immobile entre deux temps |

Six crans et non dix : le maximum vaut le nombre de LED d'une colonne de la
matrice, ce qui permet de l'afficher **en permanence comme une jauge**, une LED
par cran, sans chiffre à interpréter. Au-delà de 30 ms, l'impulsion commencerait
à relancer la pale à l'envers sans rien gagner en netteté.

C'est aussi le premier levier d'autonomie : le freinage pèse environ **un quart
du budget moteur**.

### Les tests

Le **logo tactile** remet l'amortissement à 6 et joue le diagnostic complet.
C'est le geste de celui qui ne comprend plus ce que fait le robot — et la façon
de repartir après un arrêt d'urgence.

**Les phares d'abord**, ils ne demandent pas de dégager les pales. Trois
clignotements sur `P`, la voie des broches P8 et P12, puis trois sur `I`, la voie
I2C des Maqueen V5 et Plus. Si les phares ne s'allument que sur `I`, passer
`PHARES_I2C` à `True`. Si aucune des deux, c'est le châssis.

**Les roues ensuite.** Compte à rebours de trois secondes, puis la roue gauche
seule, la droite seule, les deux. **Les deux sont essayées même si l'une est
désactivée** : c'est un test du matériel, pas de la sculpture. La matrice affiche
`OK` si les ordres sont passés.

> Attention à ce que ce `OK` signifie : il atteste que les trames I2C ont été
> **acceptées**, rien de plus. Le robot n'a aucun retour sur la rotation réelle
> de ses roues. Un `OK` sans qu'aucune roue ne bouge désigne l'alimentation,
> pas le code.

---

## Les voyants

Trois afficheurs, trois portées différentes.

### La matrice — les deux réglages, en permanence

La matrice 5×5 est un tableau de bord, pas un compteur. Elle porte les deux
choses que les boutons commandent, tout le temps :

```
colonnes 0-2        3        4
  le motif       (vide)   la jauge d'amortissement
   1 à 5                  0 à 5 LED, remplie par le bas
```

```
 # # # . #      motif 3, amortissement 5
 . . # . #
 # # # . #
 . . # . #
 # # # . #

 # . # . .      motif 4, amortissement 2
 # . # . .
 # # # . .
 . . # . #
 . . # . #
```

**Trois colonnes pour le chiffre et non quatre**, alors que la matrice en
laisse quatre : la quatrième reste vide et sert de **séparateur**. Un chiffre
collé à la jauge se lit comme un seul dessin, et l'on ne sait plus où finit l'un
et où commence l'autre. La colonne perdue est ce qui rend les deux lisibles.

**Une jauge et non un chiffre** pour l'amortissement : elle se lit sans rien
interpréter, et son remplissage va dans le même sens que ce qu'elle commande —
plus elle monte, plus la pale est arrêtée net.

Auparavant la matrice comptait les temps, et les réglages n'apparaissaient que
400 ms après un appui. On réglait donc de mémoire — en bloquant la boucle
pendant ce temps, qui plus est. Les temps, eux, sont déjà montrés par les
phares, et de bien plus loin.

L'image n'est reconstruite que lorsqu'un des deux réglages change : sans ce
cache, on fabriquerait un objet `Image` cinquante fois par seconde pour rien.

Les autres affichages prennent temporairement la matrice :

| Affichage | Sens |
|---|---|
| `2`, `1` | compte à rebours de démarrage |
| visage endormi | plus de musique depuis quatre secondes |
| petit carré | arrêt d'urgence |
| `TEST`, `P`, `I`, `OK` | séquence de diagnostic |

### Les phares avant

Ils clignotent à chaque temps : **les deux** sur le premier temps de la mesure,
**un seul** en alternance sur les autres. L'accent se voit d'un coup d'œil, de
loin, et même quand les pales masquent la matrice.

L'alternance est une bascule et non le rang du temps : sur une mesure à quatre
temps, alterner selon le rang ferait toujours tomber deux temps sur trois du
même côté.

### Le cadran — les 4 LED RGB sous le châssis

Les [WS2812 sur P15](https://wiki.dfrobot.com/rob0148-en-lb/docs/21454) forment
le tableau de bord. Elles tournent **aussi pendant le silence**, ce qui montre
que le dispositif écoute toujours au lieu d'être planté.

| LED | Rôle | Lecture |
|---|---|---|
| **RGB0** | volume brut | carte de couleurs |
| **RGB1** | signal moteur | **vert** = entraîne (luminosité ∝ vitesse), **rouge** = freinage |
| **RGB2** | réglage du seuil | se lit **au vert** |
| **RGB3** | régularité du tempo | se lit **au froid**, éteint si pas de tempo |

**La valeur est portée par la teinte, pas par la luminosité.** L'œil ne sait pas
juger une luminosité absolue : il en juge le contraste avec ce qui l'entoure,
donc la lecture changerait avec la distance, l'éclairage de la pièce, et selon
qu'une pale passe devant. Une teinte se **nomme** d'un coup d'œil et reste la
même à trois mètres.

```
bleu ──── cyan ──── vert ──── jaune ──── rouge
bas                                        haut
```

**RGB2 — le réglage du seuil.** Où le seuil se situe entre la nappe sonore et
les crêtes :

| Couleur | Sens | Quoi faire |
|---|---|---|
| **bleu** | le seuil est au-dessus des crêtes | rien ne sera jamais détecté — baisser `sensibilite` |
| **vert** | à mi-chemin | c'est le réglage sain, ne rien toucher |
| **rouge** | descendu au niveau de la nappe | tout le déclenche, c'est la rafale — monter `sensibilite` |

**RGB3 — la régularité du tempo.** L'écart moyen entre deux intervalles :

| Couleur | Sens |
|---|---|
| **éteint** | aucun tempo en cours : silence, ou rien de détecté |
| **bleu** | régulier comme un métronome |
| **rouge** | erratique — ce qui est détecté n'est pas un rythme |

Rien dans le dispositif ne sait si un temps détecté correspond à un vrai temps
de la musique. Mais **un train de temps irréguliers ne peut pas être de la
musique** : c'est la seule mesure de qualité disponible, et elle suffit. Mesure
sur signal simulé, quatre graines : une musique à 120 BPM donne une gigue de
**0,00**, un bruit sans rythme de **0,14 à 0,25**.

> **Pourquoi des diagnostics et non des grandeurs.** Une première version
> affichait le seuil et la moyenne mobile — deux valeurs brutes — et
> n'apprenaient rien. La moyenne mobile d'une nappe, c'est la nappe : elle
> montrait la même couleur que RGB0 entre deux temps. Et le seuil, qui se tient
> par construction juste sous les crêtes, ne bougeait pratiquement pas. Les deux
> demandaient à l'œil de **comparer** trois lumières pour en tirer une
> conclusion. RGB2 et RGB3 tirent la conclusion.

---

## Les cinq motifs

| # | Motif | Mouvement | Rend le mieux avec |
|---|---|---|---|
| 1 | **pulsation** | une impulsion carrée par temps, puis arrêt freiné | des pales rigides, dont on voit le quart de tour |
| 2 | **balancier** | les deux côtés alternent, une roue par temps | une composition dissymétrique, à **deux** roues |
| 3 | **tourbillon** | bouffées de rotation, inversées tous les 4 temps | des rubans longs, qui se retournent sur l'accent |
| 4 | **ronde** | rotation continue, coup de fouet à chaque temps | des rubans, déployés en disque par la force centrifuge |
| 5 | **aléatoire** | tire un des quatre au sort et en change **toutes les minutes** | une installation qu'on laisse tourner une soirée |

Le motif 5 ne pilote rien lui-même : il enveloppe les autres. Sans lui, une
soirée entière se passe sur la même chorégraphie et l'œil s'y fait au bout de
quelques morceaux. La minute est un compromis — assez long pour qu'un motif
s'installe et qu'on le reconnaisse, assez court pour qu'on ne se demande pas si
le robot est bloqué. **Le tirage exclut le motif en cours** : sur quatre
possibilités, retomber sur le même donnerait deux minutes identiques et l'on
croirait à une panne.

La règle du répertoire : **on veut des à-coups**. Une pale qui tourne à vitesse
constante ne raconte rien — on ne voit plus la musique, seulement un moteur.
Chaque motif donne donc un coup sur le temps et retombe franchement avant le
suivant ; `test_chaque_motif_marque_le_temps` le vérifie sur les quatre, en
exigeant que chacun redescende sous 80 % de son sommet avant le temps suivant.

Mesuré sur un cycle, creux ÷ sommet : pulsation **0,00**, balancier **0,12**,
tourbillon **0,34**, ronde **0,62**.

C'est aussi pourquoi le motif de départ est **pulsation**, le plus percussif : au
premier essai, on veut voir le rythme, pas un ronronnement.

Les motifs marqués `continu = True` (tourbillon, ronde) gardent entre deux temps
une rotation de fond plus lente au lieu de s'arrêter. Les autres ne bougent
**que** sur un temps : dans le silence, ils laissent les pales strictement
immobiles.

Avec une seule roue active, `balancier` perd la moitié de ses temps par
construction.

---

## Comment ça marche

### 1. La détection du rythme

Le micro:bit v2 mesure un niveau sonore de 0 à 255. Ni FFT ni budget CPU pour
une vraie analyse spectrale : on détecte l'énergie. Un temps est une **montée
brusque** du niveau au-dessus de sa moyenne récente.

Trois suiveurs entretenus en permanence, qui ne regardent pas la même chose :

| Suiveur | Portée | Rôle |
|---|---|---|
| `moyenne` | ~1,5 s | le niveau moyen du morceau. Le seuil s'y rapporte |
| `fond` | descend en 0,25 s, remonte en 1 min | le **silence** de la salle, et non son niveau moyen |
| `pic` | redescend en ~4 s | le sommet récent. Donne l'échelle réelle du morceau |

**`moyenne` doit rester plus lente que le tempo.** C'est le point le plus
délicat de tout le projet. À 120 BPM un temps tombe toutes les 500 ms ; une
moyenne calée sur un tiers de seconde monte avec chaque temps, le seuil monte
avec elle, et plus rien ne dépasse jamais. Symptôme : **les moteurs tournent
sans le moindre à-coup**. C'est exactement le défaut qu'avait la première
version, où `INERTIE_MOYENNE` valait 16 — sur une minute de musique simulée,
elle détectait **0 temps sur 120**.

**`fond` est dissymétrique**, prompt à descendre et lent à monter. C'est ce qui
en fait le niveau des creux, et non celui du morceau : une moyenne lente
finirait à hauteur de la musique et interdirait toute détection après une heure
de morceau fort.

**Un temps exige une montée**, pas seulement un niveau haut : `niveau >
précédent`. Sans cette condition, un passage fort et soutenu — un refrain
saturé, une nappe — tient le seuil en continu et fait déclarer un temps à chaque
tour de boucle, ce qui revient à n'en déclarer aucun.

Le seuil est donc le plus haut de trois termes :

```python
max(moyenne * sensibilite,   # la montée
    plancher,                # le plancher absolu
    fond * MARGE_FOND)       # le plancher relatif au silence de la salle
```

`MARGE_FOND` vaut **1,25** et non 1,6. La valeur haute datait de l'époque où
`fond` était une moyenne sur une minute, donc un niveau de salle. Depuis qu'il
suit les creux de la musique, 1,6 fois ce creux tombe juste sous les crêtes : ce
terme devenait le seuil réel et `sensibilite` ne servait plus à rien, alors que
c'est le réglage documenté. Mesure : le seuil passe de 140 à 111, la détection
reste à 120 BPM (59 temps sur 60 attendus en 30 s), et l'indicateur RGB2 passe de
0,15 — collé en butée bleue — à **0,66**, en plein dans la bande saine.

**Aucune calibration**, ni au démarrage ni ensuite. Une installation qui tourne
des heures traverse seule les changements de morceau, la salle qui se remplit et
les variations de volume. Les suiveurs se calent d'autant plus vite qu'ils ont vu
peu d'échantillons, ce qui évite d'attendre au démarrage sans laisser passer de
rafale de faux temps.

### 2. Les à-coups

Commander la vitesse zéro **ne suffit pas**. À zéro, le pont en H laisse le
moteur en roue libre : chargé d'une croix de pales, l'axe continue sur son erre
pendant une bonne seconde. De loin on ne voit plus qu'un moteur qui tourne en
continu, alors que le programme a bien commandé l'arrêt à chaque fois.

`maqueen.pales()` **freine** donc au passage à zéro : une impulsion à contresens,
assez pour bloquer l'axe, trop brève pour l'emmener à l'envers. Elle n'est
envoyée qu'au moment où la roue s'arrête, jamais à chaque tic de silence — sinon
la roue vibrerait en permanence et le bus serait saturé pour rien.

Sur dix secondes de musique à 120 BPM, chaîne complète, la roue est **alimentée
22 % du temps et à l'arrêt 78 %**.

Le `temps_mort` de 250 ms n'est pas là que pour la caisse claire : il garantit
qu'une impulsion de 110 ms est **terminée et la roue freinée** avant le temps
suivant. À 150 ms les impulsions se recouvraient et la rotation redevenait
continue.

Les impulsions sont **carrées**, jamais décroissantes : une rampe qui redescend
laisse une longue queue à faible couple, juste assez pour entretenir la rotation
sans jamais la marquer. C'est le contraste qui fait l'à-coup, pas la durée.

### 3. Quand la musique s'arrête

Après quatre secondes sans aucun temps détecté, les pales et les phares
s'arrêtent et le micro:bit affiche un dormeur. **La détection continue de
tourner** : les pales repartent d'elles-mêmes dès que le son revient, sans
intervention. C'est ce qui permet de laisser l'installation seule entre deux
passages musicaux.

---

## Tous les réglages

### `src/beat.py` — la détection

```python
beat.Detecteur(sensibilite=1.18, temps_mort=250, plancher=12)
```

| Réglage | Défaut | Rôle |
|---|---|---|
| `sensibilite` | `1.18` | rapport au-dessus de la moyenne pour déclarer un temps. La montée devant aussi être franche, on descend plus bas qu'avec un seuil seul — mais sous `1.10` la détection s'emballe sur du bruit continu |
| `temps_mort` | `250` ms | aveuglement après un temps. Plafonne à 240 BPM **et** garantit l'arrêt freiné avant le temps suivant |
| `plancher` | `12` | plancher **absolu**, en niveau brut. **À monter en premier** si le robot s'agite dans une pièce silencieuse |
| `INERTIE_MOYENNE` | `70` (~1,5 s) | **la plus délicate** — trop basse, plus rien n'est détecté |
| `INERTIE_FOND` | `3000` (~1 min) | vitesse de remontée du fond : adaptation à une salle qui change |
| `INERTIE_DESCENTE` | `12` (~0,25 s) | vitesse de descente du fond : il doit coller aux creux |
| `INERTIE_PIC` | `200` (~4 s) | décroissance du sommet, qui donne l'échelle du morceau |
| `INERTIE_TEMPO` | `8` temps | fenêtre sur laquelle la régularité (RGB3) se juge |
| `MARGE_FOND` | `1.25` | hauteur du plancher au-dessus du silence — voir plus haut |
| `NIVEAU_PLEIN` | `180` | niveau sonore auquel les motifs tournent à plein régime |
| `AMORCE` | `25` | échantillons de silence avant la première détection |

### `src/maqueen.py` — le matériel

| Réglage | Défaut | Rôle |
|---|---|---|
| `ROUE_GAUCHE_ACTIVE` | `True` | roue montée. Une roue coupée ne reçoit **jamais** de vitesse |
| `ROUE_DROITE_ACTIVE` | `False` | idem — la sculpture n'a qu'une croix de pales |
| `AMORTISSEMENT_DEFAUT` | `3` | cran au démarrage et après le logo tactile |
| `AMORTISSEMENT_MAX` | `5` | dernier cran — vaut la hauteur de la matrice, d'où la jauge |
| `FREIN_MS_MAX` | `30` ms | contresens au cran maximal ; chaque cran vaut `FREIN_MS_MAX / 5` |
| `FREIN_VITESSE` | `200` | puissance de l'impulsion de freinage |
| `VITESSE_MIN` | `40` | sous ce seuil le moteur bourdonne sans tourner. **Zéro reste zéro** |
| `VITESSE_MAX` | `255` | plafond de la trame I2C |
| `VITESSE_TEST` | `120` | vitesse du diagnostic, assez lente pour rattraper le robot |
| `PHARES_I2C` | `False` | `True` pour les Maqueen V5 et Plus, phares RGB sur le bus |
| `PHARE_COULEUR` | `7` | couleur des phares I2C : 1 rouge, 2 vert, 4 bleu, 7 blanc |
| `SOL_PIXELS` | `4` | nombre de LED RGB sous le châssis |

Constantes matérielles, à ne changer que si la carte change : `ADRESSE = 0x10`,
`GAUCHE = 0x00` / `DROITE = 0x02`, `HORAIRE = 0x00` / `ANTIHORAIRE = 0x01`,
phares sur `pin8` et `pin12`, LED de sol sur `pin15`, phares I2C aux registres
`0x0B` et `0x0C`.

### `src/main.py` — la boucle et le cadran

| Réglage | Défaut | Rôle |
|---|---|---|
| `COMPTE_A_REBOURS` | `2` s | délai de grâce au démarrage automatique. `0` le supprime |
| `SILENCE_MS` | `4000` | silence au-delà duquel les pales s'arrêtent |
| `PERIODE_MS` | `20` | période de boucle, soit 50 Hz |
| `FLASH_MS` | `90` | durée du flash matrice et phares sur un temps |
| `SOL_TOUS_LES` | `3` tics | rafraîchissement du cadran, soit 60 ms |
| `SOL_LUM` | `40` | **plafond de luminosité par canal** — voir ci-dessous |
| `SOL_COMPRESSION` | `0.7` | exposant qui étale le bas de l'échelle |
| `SOL_MARGE` | `1.12` | marge au-dessus du sommet du morceau |
| `SOL_CARTE` | bleu→rouge | les cinq points d'appui de la carte de couleurs |

`SOL_LUM` n'est pas qu'une question de goût : une WS2812 à fond tire 60 mA, soit
**240 mA pour les quatre — plus que les moteurs**. À 40 elles coûtent une
vingtaine de milliampères.

`SOL_COMPRESSION` est mesuré, pas choisi par goût. En linéaire tout se tasse en
bas : les crêtes d'un morceau sont brèves, donc la nappe ne quitte jamais le
bleu. À la racine carrée (0,5) c'est le haut qui se tasse, et le contretemps
finit dans le rouge avec le temps. **0,7** sépare les repères sur toute la carte.

`SOL_MARGE` existe parce que sans elle, le seuil — qui se tient par construction
juste sous les crêtes — saturait en haut de la carte.

### `src/choregraphie.py` — les motifs

| Motif | Paramètres |
|---|---|
| `Pulsation` | `force=255`, `duree=110` ms |
| `Balancier` | `vitesse=245`, `duree=150` ms |
| `Tourbillon` | `vitesse=255`, `trainee=70`, `mesure=4`, `pause=90` ms, `retombee=0.86` |
| `Ronde` | `mini=70`, `maxi=255`, `coup=110`, `retombee=0.88` |
| `Aleatoire` | `duree=60000` ms — `DUREE_TIRAGE`, l'intervalle entre deux tirages |

`REPERTOIRE_SIMPLE` liste les quatre motifs qui pilotent vraiment les pales ;
`Aleatoire` pioche dedans, il ne peut donc pas se tirer lui-même. `REPERTOIRE`
les rassemble et donne l'ordre de défilement du bouton A. Le `pause` du
tourbillon arrête brièvement le moteur avant chaque inversion : lancer le sens
opposé à pleine vitesse fait caler le pont en H.

---

## Alimentation

**Le piège n°1 de ce projet.** Deux alimentations distinctes cohabitent, et
elles ne se rejoignent jamais :

| Ce qui est alimenté | Par quoi |
|---|---|
| micro:bit, contrôleur I2C, phares, LED de sol | le **3,3 V** — l'USB suffit |
| **étage de puissance des moteurs** | **uniquement l'accu du châssis** |

Un châssis sans accu accepte donc tous les ordres I2C sans broncher, répond `OK`
au diagnostic, et ne bouge pas d'un millimètre. Aucun garde-fou logiciel ne peut
distinguer ce cas d'un fonctionnement normal : `reveille()` teste la
communication, pas la puissance.

Trois fausses pistes, toutes vérifiées :

- **le câble USB du micro:bit** — n'alimente que le logique ;
- **la prise blanche du micro:bit** — connecteur JST-PH **3 V max**, en amont du
  régulateur du micro:bit. Elle ne va pas plus loin que lui, et y mettre 5 V le
  détruit ;
- **le port `CHG 5V` du châssis, seul** — c'est une entrée de **charge**, pas une
  alimentation. Elle entre sur un circuit type TP4056 dont la sortie va sur la
  cellule ; sans cellule au bout, elle oscille au lieu de tenir une tension.

Le seul point d'entrée vers les moteurs est le **connecteur d'accu**. Deux
solutions :

1. **Accu lithium 3,7 V + `CHG` branché en permanence** — la bonne pour une
   installation. L'accu tamponne les pointes de courant du freinage, le chargeur
   compense la consommation moyenne. Alim USB **5 V ≥ 1 A**.
2. **Alim 5 V 2 A directement sur le connecteur d'accu** — dans la plage
   annoncée (3,5–5 V). Respecter la polarité, et **pas d'accu branché en même
   temps**.

### Autonomie

Estimation, musique continue à 120 BPM, une seule roue :

| Poste | Moyenne |
|---|---|
| micro:bit + logique Maqueen | ~25 mA |
| phares | ~4 mA |
| LED de sol à `SOL_LUM = 40` | ~20 mA |
| moteur (alimenté 22 % du temps) | ~55 mA |
| impulsions de freinage | ~30 mA |
| **total** | **~135 mA** |

Soit de l'ordre de **7 à 8 h** sur un accu 1000 mAh. En silence tout se coupe :
~50 mA, plusieurs jours. Les leviers, dans l'ordre : `SOL_LUM`, `FREIN_MS_MAX`,
puis la `duree` des impulsions.

Si le micro:bit **redémarre** sur un à-coup, c'est l'alimentation qui s'effondre
sous la pointe de courant du freinage, pas le code.

---

## Architecture

```
src/
├── maqueen.py       moteurs (I2C 0x10), phares, LED de sol, freinage
├── beat.py          détection d'énergie, seuil adaptatif, diagnostics
├── choregraphie.py  les cinq motifs, sans aucun accès au matériel
└── main.py          boucle, boutons, cadran, sécurités
```

`choregraphie.py` ne parle jamais à l'I2C : un motif reçoit les temps et rend un
couple de vitesses. On peut donc écrire et tester une chorégraphie sans robot, et
l'ajouter au `REPERTOIRE`.

`outils/build_mono.py` fusionne les quatre modules en un script unique pour
`uflash`, en supprimant commentaires et docstrings si le résultat dépasse les
20 151 octets qu'`uflash` accepte.

`outils/flash.py` dépose ce script sur la carte et **vérifie** que DAPLink l'a
accepté — voir [plus haut](#outilsflashpy--pourquoi-le-flash-ne-passe-plus-par-uflash-seul).

## Tests

```bash
make test
```

31 tests, sans matériel : `tests/microbit.py` et `tests/neopixel.py` remplacent
les modules du micro:bit par une horloge que l'on fait avancer à la main.

- `test_beat.py` — l'adaptation sans calibration, le seuil qui suit une salle
  qui monte puis se calme, l'absence de faux temps au démarrage, et les deux
  diagnostics du cadran. `test_la_marge_dit_ou_le_seuil_est_place` tient
  `MARGE_FOND` en laisse : c'est lui qui a attrapé le réglage à 1,6.
- `test_choregraphie.py` — les vitesses dans les bornes, et surtout que **chaque
  motif marque le temps** : un motif qui ne retomberait pas serait une rotation
  continue déguisée. Le motif aléatoire y est joué sous graine fixe : sans
  cela le test passerait ou non selon le tirage, ce qui est la pire espèce de
  test.
- `test_maqueen.py` — les **trames réellement écrites** sur le bus, pas les
  intentions : l'arrêt transmis, l'impulsion de freinage présente, pas de
  freinage répété dans le silence, et la roue coupée qui ne reçoit jamais de
  vitesse.

## Sécurité

Des pales lancées à 255 sur un moteur à réducteur ont du couple. Quelques
principes tenus par le code, à ne pas défaire :

- **compte à rebours de deux secondes** au démarrage automatique ;
- arrêt d'urgence à la secousse, sans avoir à viser un bouton ;
- un `finally` coupe les moteurs même si le programme plante ;
- l'arrêt **freine**, il ne laisse pas les pales finir leur élan ;
- extinction automatique après quatre secondes de silence.

Le programme se lançant seul, **brancher c'est lancer**. Poser le robot sur son
berceau avant de mettre sous tension.

Côté matériel : pales légères et souples de préférence, bien équilibrées, et rien
qui dépasse du berceau à hauteur de visage.

## Le robot ne fait rien ?

Dans l'ordre :

1. **La matrice affiche-t-elle un visage triste et un nombre ?** Un code
   **5xx** est une erreur de flashage : relancer `make flash`, qui vérifie
   maintenant le transfert. La carte tournait sur l'ancien programme.
2. **`Maqueen muet` défile ?** Le contrôleur I2C ne répond pas : châssis hors
   tension, interrupteur, ou micro:bit mal enfiché.
3. **Toucher le logo** pour lancer le diagnostic. Les phares clignotent-ils ?
   Les roues tournent-elles ?
4. **`OK` sans qu'une roue ne bouge** → [Alimentation](#alimentation). C'est le
   cas qui trompe le plus, et il n'est pas dans le code.
5. **Le cadran est-il éteint en RGB3, ou rouge ?** Rien n'est détecté, ou ce qui
   l'est n'est pas un rythme. Regarder RGB2 : bleu, baisser `sensibilite` ;
   rouge, la monter.
6. **Une seule roue tourne ?** C'est le réglage : `ROUE_DROITE_ACTIVE = False`.
7. **Le mouvement change tout seul toutes les minutes ?** C'est le motif 5,
   aléatoire. Bouton A pour en choisir un fixe.

Un piège matériel coûteux — le Maqueen ignore la première trame I2C après sa
mise sous tension, absorbée par `reveille()` — est détaillé dans
[docs/linux.md](docs/linux.md).

## Licence

MIT — voir [LICENSE](LICENSE).
