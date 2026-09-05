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

from microbit import i2c

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


def _borne(vitesse):
    vitesse = int(vitesse)
    if vitesse <= 0:
        return 0
    if vitesse < VITESSE_MIN:
        return VITESSE_MIN
    if vitesse > VITESSE_MAX:
        return VITESSE_MAX
    return vitesse


def roue(moteur, sens, vitesse):
    """Fait tourner une roue. Voir les constantes du module."""
    i2c.write(ADRESSE, bytearray([moteur, sens, _borne(vitesse)]))


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
    roue(GAUCHE, HORAIRE, 0)
    roue(DROITE, HORAIRE, 0)
