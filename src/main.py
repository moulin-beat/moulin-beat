"""moulin-beat : le micro:Maqueen fait tourner ses pales sur la musique.

Le robot est pose sur un berceau, roues en l'air. Chaque roue porte une croix
de pales, ou des rubans. Le micro:bit v2 ecoute la piece et entraine les roues
au rythme detecte.

Commandes
    bouton A   motif suivant
    bouton B   demarrer / mettre en pause
    secousse   arret d'urgence, repasse en pause

Le programme demarre TOUJOURS en pause : au sortir du flash le robot est encore
souvent sur la table, et des roues qui se lancent seules le font tomber.
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


class Moulin:
    def __init__(self):
        self.detecteur = beat.Detecteur()
        self.index = 0
        self.motif = choregraphie.REPERTOIRE[0]()
        self.actif = False
        self.flash = 0

    def motif_suivant(self):
        self.index = (self.index + 1) % len(choregraphie.REPERTOIRE)
        self.motif = choregraphie.REPERTOIRE[self.index]()
        # Le chiffre du motif, brievement, pour savoir ou l'on en est.
        display.show(str(self.index + 1))
        sleep(400)
        display.clear()

    def pause(self):
        self.actif = False
        maqueen.arret()
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

        self.pause()

        while True:
            if button_a.was_pressed():
                self.motif_suivant()

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

            if self.detecteur.silence(SILENCE_MS):
                maqueen.arret()
                display.show(Image.ASLEEP)
                sleep(PERIODE_MS)
                continue

            gauche, droite, contra = self.motif.tic(self.detecteur.energie)
            maqueen.pales(gauche, droite, contra)

            # Un coeur qui bat sur la matrice, cale sur les beats detectes :
            # c'est le seul moyen de regler la sensibilite sans oscilloscope.
            if running_time() - self.flash < 80:
                display.show(Image.HEART)
            else:
                display.clear()

            sleep(PERIODE_MS)


try:
    Moulin().boucle()
finally:
    # Quoi qu'il arrive, y compris une erreur de programmation, les moteurs
    # s'arretent. Des pales lancees dans un robot plante sont dangereuses.
    maqueen.arret()
