"""Pilotage des moteurs du DFRobot micro:Maqueen V4.2.

Les deux moteurs sont commandes par I2C a l'adresse 0x10. Chaque ordre est une
trame de trois octets : [moteur, sens, vitesse].

    moteur   0x00 = gauche, 0x02 = droite
    sens     0x00 = horaire, 0x01 = antihoraire
    vitesse  0 a 255

Dans moulin-beat les roues ne roulent pas : elles portent les pales. Le robot
est pose sur un berceau, roues en l'air. "Avant" et "arriere" n'ont donc pas de
sens ici, on parle de sens de rotation des pales.
"""

from microbit import i2c, sleep, pin8, pin12, pin15

import neopixel

ADRESSE = 0x10

GAUCHE = 0x00
DROITE = 0x02

HORAIRE = 0x00
ANTIHORAIRE = 0x01

# En dessous de ce seuil le moteur bourdonne sans tourner : le couple ne suffit
# pas a vaincre le frottement, encore moins a entrainer des pales. Toute vitesse
# non nulle demandee est remontee a ce plancher.
VITESSE_MIN = 40
VITESSE_MAX = 255

# Roues effectivement montees. Une sculpture n'a pas forcement deux croix de
# pales : couper la roue inutilisee lui evite de tourner pour rien, d'user les
# piles et de faire du bruit. Le diagnostic du bouton A, lui, essaie toujours
# les deux — c'est un test du materiel, pas de la sculpture.
ROUE_GAUCHE_ACTIVE = True
ROUE_DROITE_ACTIVE = False

# Freinage. C'est LE point qui fait ou defait les a coups : un moteur charge de
# pales ne s'arrete pas parce qu'on lui coupe le courant. Vitesse zero laisse le
# pont en H en roue libre, et l'inertie des pales entretient la rotation pendant
# une bonne seconde — de loin, on ne voit plus qu'un moteur qui tourne en
# continu, meme si le programme a bien commande l'arret a chaque fois.
#
# Une breve impulsion en sens INVERSE bloque l'axe net. Elle est courte expres :
# assez pour tuer l'inertie, trop breve pour lancer la rotation a l'envers.
FREIN_VITESSE = 200

# L'AMORTISSEMENT est le reglage de scene, celui qu'on retouche devant le
# public avec les boutons A et B. Il dit a quel point la pale est arretee net
# entre deux temps :
#
#   0   aucun freinage. Roue libre, elan long, mouvement fluide et continu.
#       C'est le rendu d'avant le freinage : joli avec des rubans, mais le
#       rythme ne se lit plus.
#   3   le reglage d'usine, 18 ms de contresens.
#   5   frein sec. A-coup maximal, pale quasi immobile entre deux temps.
#
# Six paliers de 6 ms, de 0 a 5. Le maximum vaut le nombre de LED d'une colonne
# de la matrice : l'amortissement s'affiche en permanence comme une jauge, une
# LED par cran, et le reglage se lit sans chiffre a interpreter.
# Monter au dela de 30 ms ne serait pas plus net : la pale est deja bloquee,
# l'impulsion commencerait a la relancer a l'envers, et l'autonomie en patirait.
FREIN_MS_MAX = 30
AMORTISSEMENT_MAX = 5
AMORTISSEMENT_DEFAUT = 3

# Liste et non entier : une variable de module reaffectee depuis une fonction
# demanderait un `global`, que le script fusionne rend fragile.
_amortissement = [AMORTISSEMENT_DEFAUT]

# Un freinage vient il de partir ? Le VU-metre le montre, ce qui permet de
# regler l'amortissement en le VOYANT agir plutot qu'a l'oreille. Remis a faux
# a la lecture : c'est un evenement, pas un etat.
_frein_vu = [False]

# Vitesse de la sequence de diagnostic : assez pour qu'une roue chargee de
# pales tourne franchement, assez peu pour qu'un robot pose au sol ne parte pas
# en trombe le temps de le rattraper.
VITESSE_TEST = 120

# Phares avant. Sur le micro:Maqueen V4.2 ce sont deux LED blanches en tout ou
# rien, cablees sur deux broches du micro:bit : elles ne passent pas par l'I2C
# et fonctionnent donc meme quand le controleur moteur ne repond pas.
PHARE_GAUCHE = pin8
PHARE_DROIT = pin12

# Les revisions plus recentes (Maqueen V5, Maqueen Plus) ont remplace ces deux
# LED par des phares RVB pilotes en I2C, aux registres 11 et 12 du meme
# controleur : sur ces cartes, P8 et P12 ne sont plus relies a rien et les
# phares restent obstinement eteints. Mettre PHARES_I2C a True pour les
# adresser a l'autre facon. Le diagnostic du bouton A (voir main.py) essaie
# successivement les deux voies : c'est le moyen de savoir quelle carte on a.
PHARES_I2C = False
PHARE_I2C_GAUCHE = 0x0B
PHARE_I2C_DROIT = 0x0C
# Couleur allumee sur les cartes RVB. 1 = rouge, 2 = vert, 4 = bleu, 7 = blanc.
PHARE_COULEUR = 7


# Les quatre LED RVB sous le chassis, en WS2812 sur la broche P15, format GRB.
# Elles ne servent pas a eclairer : c'est le VU-metre du dispositif, la seule
# facon de voir ce que le micro entend quand les pales masquent la matrice.
#
# La luminosite est PLAFONNEE tres bas, et pas seulement par gout : une WS2812
# a fond tire 60 mA, soit 240 mA pour les quatre — plus que les moteurs. A ce
# niveau la elles coutent une vingtaine de milliamperes en tout, ce qui reste
# lisible dans une piece sombre.
SOL_BROCHE = pin15
SOL_PIXELS = 4

_sol = None


def sol(couleurs):
    """Allume les LED de sol. `couleurs` : quatre triplets (r, v, b).

    Le bandeau est cree au premier appel : une installation dont les LED sont
    absentes ou mortes ne doit pas payer l'allocation au demarrage, ni tomber.
    """
    global _sol
    if _sol is None:
        _sol = neopixel.NeoPixel(SOL_BROCHE, SOL_PIXELS)
    for rang in range(SOL_PIXELS):
        _sol[rang] = couleurs[rang]
    _sol.show()


def sol_eteint():
    """Eteint les LED de sol. Fait partie de l'arret : plus rien ne bouge."""
    if _sol is None:
        return
    sol([(0, 0, 0)] * SOL_PIXELS)


def _borne(vitesse):
    vitesse = int(vitesse)
    if vitesse <= 0:
        return 0
    if vitesse < VITESSE_MIN:
        return VITESSE_MIN
    if vitesse > VITESSE_MAX:
        return VITESSE_MAX
    return vitesse


def roue(moteur, sens, vitesse, essais=3):
    """Fait tourner une roue. Voir les constantes du module.

    Le controleur moteur du Maqueen n'acquitte pas le tout premier echange qui
    suit sa mise sous tension : cette ecriture la, et elle seule, part en
    OSError ENODEV. On reessaie donc, faute de quoi le programme meurt sur la
    toute premiere trame envoyee. Un echec persistant est avale plutot que
    propage : la boucle principale repasse cinquante fois par seconde et se
    rattrape au tic suivant, ce qui vaut mieux qu'un plantage pales lancees.

    Rend True si la trame est passee.
    """
    trame = bytearray([moteur, sens, _borne(vitesse)])
    for reste in range(essais, 0, -1):
        try:
            i2c.write(ADRESSE, trame)
            return True
        except OSError:
            if reste > 1:
                sleep(2)
    return False


def reveille():
    """Etablit le dialogue avec le controleur moteur.

    A appeler une fois au demarrage, avant toute chose, pour absorber l'echec
    du premier echange et partir sur un bus sain. Rend False si le Maqueen ne
    repond toujours pas : robot hors tension, interrupteur sur OFF, piles a
    plat, ou micro:bit mal enfiche.
    """
    return roue(GAUCHE, HORAIRE, 0, essais=5)


# Une roue tournait elle au tic precedent ? Sert a ne freiner qu'au moment ou
# elle s'arrete, et non cinquante fois par seconde pendant tout le silence.
_lancee = [False, False]


def pales(vitesse_gauche, vitesse_droite, contra=False):
    """Entraine les deux roues d'un coup.

    contra=True fait tourner les roues en sens opposes. Vues de l'exterieur du
    robot, les deux pales tournent alors dans le meme sens apparent : c'est ce
    qu'on veut pour un moulin symetrique. contra=False donne deux sens
    apparents opposes, plus tourbillonnant.

    Une vitesse nulle ne se contente pas de couper le courant : elle FREINE.
    C'est ce qui rend l'a coup visible, voir FREIN_MS.
    """
    if not ROUE_GAUCHE_ACTIVE:
        vitesse_gauche = 0
    if not ROUE_DROITE_ACTIVE:
        vitesse_droite = 0
    sens_droite = ANTIHORAIRE if contra else HORAIRE
    _mene(0, GAUCHE, HORAIRE, vitesse_gauche)
    _mene(1, DROITE, sens_droite, vitesse_droite)


def _mene(rang, moteur, sens, vitesse):
    """Une roue, avec freinage au passage a zero."""
    vitesse = _borne(vitesse)
    if vitesse:
        _lancee[rang] = True
        roue(moteur, sens, vitesse)
        return
    if _lancee[rang]:
        _lancee[rang] = False
        freine(moteur, sens)
    roue(moteur, sens, 0)


def amortissement():
    """Niveau d'amortissement courant, de 0 a AMORTISSEMENT_MAX."""
    return _amortissement[0]


def regle_amortissement(niveau):
    """Fixe l'amortissement, borne aux paliers existants. Rend le niveau retenu."""
    if niveau < 0:
        niveau = 0
    elif niveau > AMORTISSEMENT_MAX:
        niveau = AMORTISSEMENT_MAX
    _amortissement[0] = niveau
    return niveau


def frein_ms():
    """Duree de l'impulsion de freinage pour l'amortissement courant."""
    return FREIN_MS_MAX * _amortissement[0] // AMORTISSEMENT_MAX


def frein_declenche():
    """True si un freinage est parti depuis le dernier appel. Consomme l'evenement."""
    vu = _frein_vu[0]
    _frein_vu[0] = False
    return vu


def freine(moteur, sens):
    """Bloque une roue lancee par une impulsion a contresens.

    Le temps d'attente bloque la boucle principale le temps d'un tic. C'est
    accepte : cela n'arrive qu'au moment precis ou une roue s'arrete, et un a
    coup net vaut mieux qu'un tic de detection.

    A l'amortissement zero on ne freine pas du tout — pas d'impulsion, pas
    d'attente : la roue part en roue libre, ce qui est bien le mouvement
    demande a ce reglage.
    """
    duree = frein_ms()
    if not duree:
        return
    _frein_vu[0] = True
    inverse = ANTIHORAIRE if sens == HORAIRE else HORAIRE
    roue(moteur, inverse, FREIN_VITESSE)
    sleep(duree)


def phares(gauche, droit):
    """Allume ou eteint les deux phares avant, chacun a True ou False."""
    if PHARES_I2C:
        phares_i2c(gauche, droit)
    else:
        phares_broches(gauche, droit)


def phares_broches(gauche, droit):
    """Voie des broches, celle du micro:Maqueen V4.2."""
    PHARE_GAUCHE.write_digital(1 if gauche else 0)
    PHARE_DROIT.write_digital(1 if droit else 0)


def phares_i2c(gauche, droit):
    """Meme chose, pour les cartes dont les phares sont RVB et sur le bus.

    Les echecs sont avales comme ailleurs : un phare qui ne repond pas ne doit
    jamais emporter le programme, pales lancees.
    """
    for registre, allume in ((PHARE_I2C_GAUCHE, gauche),
                             (PHARE_I2C_DROIT, droit)):
        try:
            i2c.write(ADRESSE, bytearray([registre,
                                          PHARE_COULEUR if allume else 0]))
        except OSError:
            pass


def arret():
    """Coupe les deux moteurs. Insiste : c'est la fonction de securite.

    Freine d'abord si les roues tournaient — a l'arret d'urgence sur secousse,
    on veut que les pales s'immobilisent, pas qu'elles finissent leur elan.
    """
    for rang, moteur in ((0, GAUCHE), (1, DROITE)):
        if _lancee[rang]:
            _lancee[rang] = False
            freine(moteur, HORAIRE)
    gauche = roue(GAUCHE, HORAIRE, 0, essais=8)
    droite = roue(DROITE, HORAIRE, 0, essais=8)
    phares(False, False)
    sol_eteint()
    return gauche and droite
