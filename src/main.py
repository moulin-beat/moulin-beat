"""moulin-beat : le micro:Maqueen fait tourner ses pales sur la musique.

Le robot est pose sur un berceau, roues en l'air. Chaque roue porte une croix
de pales, ou des rubans. Le micro:bit v2 ecoute la piece et entraine les roues
au rythme detecte.

Commandes
    bouton A   en marche : motif suivant
               en pause  : sequence de test des deux roues
    bouton B   demarrer / mettre en pause
    secousse   arret d'urgence, repasse en pause

Le programme demarre TOUJOURS en pause : au sortir du flash le robot est encore
souvent sur la table, et des roues qui se lancent seules le font tomber. Avant
cela il mesure une seconde de bruit ambiant, carre plein affiche, pour caler la
moyenne glissante sur laquelle repose toute la detection.

A chaque temps detecte, la matrice montre le rang du temps dans la mesure et les
phares avant clignotent : les deux sur le premier temps, un seul sur les autres.
"""

from microbit import (
    display, button_a, button_b, accelerometer, sleep, Image, running_time,
)

import maqueen
import beat
import choregraphie

# Au dela de ce silence, les pales s'arretent d'elles memes : une piece vide ne
# doit pas laisser le robot tourner toute la nuit.
SILENCE_MS = 4000

# Periode de la boucle. 20 ms suffisent a suivre un beat au millier de BPM et
# laissent le bus I2C respirer.
PERIODE_MS = 20

# Duree du flash visuel, matrice et phares. Assez bref pour rester net a tempo
# rapide, assez long pour etre vu.
FLASH_MS = 90


class Moulin:
    def __init__(self):
        self.detecteur = beat.Detecteur()
        self.index = 0
        self.motif = choregraphie.REPERTOIRE[0]()
        self.actif = False
        self.flash = 0
        # Cote du prochain phare hors accent. Une bascule, et non le rang du
        # temps : sur une mesure a quatre temps, alterner selon le rang ferait
        # toujours tomber deux temps sur trois du meme cote.
        self.cote_phare = False

    def motif_suivant(self):
        self.index = (self.index + 1) % len(choregraphie.REPERTOIRE)
        self.motif = choregraphie.REPERTOIRE[self.index]()
        # Le chiffre du motif, brievement, pour savoir ou l'on en est.
        display.show(str(self.index + 1))
        sleep(400)
        display.clear()

    def test_roues(self):
        """Diagnostic moteur, sur le bouton A quand le robot est en pause.

        Fait tourner chaque roue separement puis les deux ensemble. Permet de
        distinguer d'un coup d'oeil les pannes qui se ressemblent toutes depuis
        la matrice : moteur mort, cablage, ou chassis hors tension.

        Point important : le controleur I2C du Maqueen est alimente par le 3,3 V
        du micro:bit, donc par l'USB seul, alors que l'etage de puissance des
        moteurs ne l'est que par les piles. Un chassis eteint accepte donc les
        ordres sans broncher et ne bouge pas. Si cette sequence affiche OK sans
        qu'aucune roue ne tourne, le diagnostic est l'alimentation, pas le code.
        """
        display.scroll("TEST", delay=60)

        # Compte a rebours : de quoi rattraper un robot pose sur une table.
        for reste in (3, 2, 1):
            display.show(str(reste))
            sleep(600)

        etapes = (
            (Image.ARROW_W, maqueen.VITESSE_TEST, 0),
            (Image.ARROW_E, 0, maqueen.VITESSE_TEST),
            (Image.SQUARE, maqueen.VITESSE_TEST, maqueen.VITESSE_TEST),
        )

        transmis = True
        for image, gauche, droite in etapes:
            display.show(image)
            if gauche:
                transmis &= maqueen.roue(maqueen.GAUCHE, maqueen.HORAIRE, gauche)
            if droite:
                transmis &= maqueen.roue(maqueen.DROITE, maqueen.ANTIHORAIRE, droite)
            sleep(1200)
            maqueen.arret()
            sleep(400)

        # On ne peut affirmer que la transmission des ordres, pas la rotation :
        # rien ici ne renseigne le robot sur ce que ses roues ont fait.
        display.scroll("OK" if transmis else "I2C KO", delay=60)
        self.pause()

    def pause(self):
        self.actif = False
        maqueen.arret()   # coupe aussi les phares
        display.show(Image.SQUARE_SMALL)

    def demarre(self):
        self.actif = True
        display.clear()

    def boucle(self):
        # Premier contact avec le controleur moteur. Sans ce reveil, la trame
        # suivante partirait en ENODEV et emporterait le programme.
        if not maqueen.reveille():
            # Le Maqueen ne repond pas du tout : inutile d'aller plus loin, on
            # le dit franchement plutot que de laisser croire a une panne de
            # detection sonore.
            while True:
                display.scroll("Maqueen muet - verifier alim et micro:bit")

        # Le detecteur mesure le bruit de fond avant de commencer, sinon sa
        # moyenne glissante part de zero et les premieres secondes se remplissent
        # de faux temps.
        display.show(Image.SQUARE)
        self.detecteur.calibre()
        display.clear()

        self.pause()

        while True:
            if button_a.was_pressed():
                if self.actif:
                    self.motif_suivant()
                else:
                    # A l'arret, le bouton A sert au diagnostic : c'est le
                    # moment ou l'on cherche pourquoi rien ne tourne.
                    self.test_roues()

            if button_b.was_pressed():
                if self.actif:
                    self.pause()
                else:
                    self.demarre()

            # Arret d'urgence : on veut pouvoir couper les moteurs a la main,
            # sans chercher un bouton, si une pale accroche quelque chose.
            if accelerometer.was_gesture("shake"):
                self.pause()

            if not self.actif:
                sleep(PERIODE_MS)
                continue

            if self.detecteur.ecoute():
                self.motif.sur_beat()
                self.flash = running_time()
                # Les deux phares sur le premier temps de la mesure, un seul
                # sur les autres : l'accent se voit d'un coup d'oeil, meme de
                # loin et meme quand la matrice est illisible sous les pales.
                if self.detecteur.accent():
                    maqueen.phares(True, True)
                else:
                    self.cote_phare = not self.cote_phare
                    maqueen.phares(self.cote_phare, not self.cote_phare)

            if self.detecteur.silence(SILENCE_MS):
                maqueen.arret()
                display.show(Image.ASLEEP)
                sleep(PERIODE_MS)
                continue

            gauche, droite, contra = self.motif.tic(self.detecteur.energie)
            maqueen.pales(gauche, droite, contra)

            # Le rang du temps dans la mesure, affiche a chaque temps detecte.
            # C'est le seul moyen de regler la sensibilite sans oscilloscope :
            # si les chiffres defilent en mesure, la choregraphie suivra.
            if running_time() - self.flash < FLASH_MS:
                display.show(str(self.detecteur.temps()))
            else:
                display.clear()
                maqueen.phares(False, False)

            sleep(PERIODE_MS)


try:
    Moulin().boucle()
finally:
    # Quoi qu'il arrive, y compris une erreur de programmation, les moteurs
    # s'arretent. Des pales lancees dans un robot plante sont dangereuses.
    maqueen.arret()
