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

from microbit import i2c, sleep

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

# Vitesse de la sequence de diagnostic : assez pour qu'une roue chargee de
# pales tourne franchement, assez peu pour qu'un robot pose au sol ne parte pas
# en trombe le temps de le rattraper.
VITESSE_TEST = 120


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


def pales(vitesse_gauche, vitesse_droite, contra=False):
    """Entraine les deux roues d'un coup.

    contra=True fait tourner les roues en sens opposes. Vues de l'exterieur du
    robot, les deux pales tournent alors dans le meme sens apparent : c'est ce
    qu'on veut pour un moulin symetrique. contra=False donne deux sens
    apparents opposes, plus tourbillonnant.
    """
    sens_droite = ANTIHORAIRE if contra else HORAIRE
    roue(GAUCHE, HORAIRE, vitesse_gauche)
    roue(DROITE, sens_droite, vitesse_droite)


def arret():
    """Coupe les deux moteurs. Insiste : c'est la fonction de securite."""
    gauche = roue(GAUCHE, HORAIRE, 0, essais=8)
    droite = roue(DROITE, HORAIRE, 0, essais=8)
    return gauche and droite
