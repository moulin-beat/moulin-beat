# Montage

## Le berceau, d'abord

Le micro:Maqueen est un robot roulant. Tout le projet consiste à l'empêcher de
rouler pour récupérer ses deux moteurs comme axes d'entraînement.

Il faut donc un support qui **surélève le châssis d'au moins la hauteur des
pales**, roues dans le vide. Trois solutions qui marchent :

- une boîte en carton rigide, découpée pour que le châssis s'y encastre ;
- deux cales de bois sous l'avant et l'arrière du châssis ;
- un socle imprimé en 3D, si le dispositif doit tourner longtemps.

Le robot doit être **fixé** au berceau, pas simplement posé : des pales
déséquilibrées le font marcher tout seul par vibration. Deux élastiques ou une
bande de scratch suffisent.

La roue folle avant du Maqueen ne sert plus à rien : elle peut rester.

## Les pales

Chaque roue devient un moyeu. Les pales se fixent sur le flanc extérieur du
pneu, pas sur la jante : la surface est plus grande et le caoutchouc accepte
l'adhésif double face.

Une croix de quatre pales donne un disque plein en rotation. Trois pales
tournent de façon plus visible parce que l'œil suit mieux l'asymétrie.

**Matériaux, du meilleur au pire :**

| Matériau | Comportement |
|---|---|
| Carton plume 3 mm | rigide, très léger, se découpe au cutter — le meilleur compromis |
| Plastique de chemise | souple, claque joliment sur les impulsions |
| Rubans de satin | ne tiennent pas seuls, à monter sur une armature |
| Carton ondulé | trop lourd, freine le moteur et chauffe le pont en H |
| Bois, métal | à proscrire — dangereux et bien au-delà du couple disponible |

## Les rubans

Les rubans ne se fixent pas directement sur le pneu : sans armature ils
s'enroulent autour de l'axe dès la première inversion de sens.

Monter d'abord une croix de pales courtes en carton plume, puis attacher les
rubans **au bout** de chaque pale. La force centrifuge les déploie et ils
tracent un disque flou très différent des pales seules.

Longueur : commencer court, 10 à 15 cm. Un ruban long a besoin de vitesse pour
se déployer, et le motif `pulsation` ne lui en donne jamais assez.

## Équilibrage

C'est ce qui distingue un dispositif qui tourne bien d'un dispositif qui
vibre.

1. Monter les pales, robot en pause.
2. Faire tourner une roue à la main. Si elle s'arrête toujours dans la même
   position, c'est qu'un côté est plus lourd.
3. Ajouter un morceau d'adhésif sur la pale opposée jusqu'à ce que la roue
   s'immobilise indifféremment.

Répéter pour l'autre roue. Un balourd se paie en vibrations, en bruit, et en
autonomie des piles.

## Choix du sens de rotation

`maqueen.pales(gauche, droite, contra)` prend un paramètre `contra` :

- `contra=True` — les roues tournent en sens opposés, donc les deux pales
  tournent dans le **même sens apparent** vues de l'extérieur. C'est le réglage
  d'un moulin symétrique, et celui de tous les motifs par défaut.
- `contra=False` — sens apparents opposés, effet plus tourbillonnant, moins
  lisible mais intéressant avec des rubans de deux couleurs.

## Réglage sonore sur place

Le cœur qui bat sur la matrice sert au réglage. Avant une représentation :

1. Lancer la musique au volume prévu.
2. Regarder battre le cœur, robot en pause — la détection tourne quand même.
3. Le cœur bat trop souvent → monter `sensibilite` ou `plancher`.
   Il ne bat pas assez → baisser `sensibilite`.

Une salle vide et une salle pleine n'ont pas la même acoustique : refaire le
réglage une fois le public installé si c'est possible.
