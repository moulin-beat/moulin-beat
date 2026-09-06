"""Detection du rythme au micro integre du micro:bit v2.

Le micro:bit v2 mesure un niveau sonore de 0 a 255. On n'a ni FFT ni budget CPU
pour une vraie analyse spectrale, donc on detecte l'energie : un temps est une
montee brusque du niveau au dessus de sa moyenne recente.

Tout repose sur DEUX moyennes glissantes, entretenues en permanence, qui ne
regardent pas la meme echelle de temps :

  moyenne   rapide, environ une seconde. Elle suit l'intensite du morceau en
            cours sans suivre le beat lui meme. Le seuil de detection s'y
            rapporte : un temps, c'est un niveau qui la depasse d'un facteur.

  fond      tres lente, environ une minute. C'est le niveau general de la
            salle. Il sert de plancher : en dessous, on refuse de detecter quoi
            que ce soit, ce qui empeche le silence et les bruits de public de
            se faire passer pour un rythme.

Aucune calibration ponctuelle, donc : les deux moyennes se recalent seules en
continu. Une installation qui tourne des heures traverse ainsi les changements
de morceau, la salle qui se remplit et les variations de volume sans qu'on ait
a y toucher. Les deux se calent d'autant plus vite qu'elles ont vu peu
d'echantillons, ce qui evite d'attendre au demarrage.
"""

from microbit import running_time, microphone

# Inerties, en nombre d'echantillons. La boucle principale tourne a environ
# 50 Hz, donc 16 vaut le tiers d'une seconde et 3000 valent une minute.
INERTIE_MOYENNE = 16
INERTIE_FOND = 3000

# Le fond seul ferait un plancher trop bas : on demande une marge au dessus du
# niveau general de la salle pour qu'un temps compte.
MARGE_FOND = 1.6

# Le temps de laisser les moyennes se caler avant de detecter quoi que ce soit.
AMORCE = 25


class Detecteur:
    def __init__(self, sensibilite=1.30, temps_mort=150, plancher=12):
        """
        sensibilite  rapport au dessus de la moyenne rapide pour declarer un
                     temps. Plus bas = plus sensible. En dessous de 1.15 la
                     detection part en vrille sur du bruit continu.
        temps_mort   duree en ms pendant laquelle on ignore les pics apres un
                     temps. Une caisse claire produit plusieurs pics rapproches
                     qu'il ne faut compter qu'une fois. 150 ms plafonnent la
                     detection a 400 BPM.
        plancher     plancher ABSOLU, en niveau sonore brut. Le plancher reel
                     est le plus haut des deux : celui ci, et celui que le fond
                     impose. Monter cette valeur si le robot s'agite dans une
                     piece silencieuse.
        """
        self.sensibilite = sensibilite
        self.temps_mort = temps_mort
        self.plancher = plancher

        self.moyenne = 0
        self.fond = 0
        self.echantillons = 0

        self.dernier_beat = 0
        self.intervalle = 0
        self.energie = 0

        # Nombre total de temps depuis l'allumage, et rang du temps dans la
        # mesure. Les motifs s'en servent pour accentuer, l'affichage pour
        # montrer ou l'on en est.
        self.compte = 0
        self.mesure = 4

    def seuil(self):
        """Niveau a depasser pour qu'un temps soit declare.

        Deux conditions, et il faut les deux : depasser la moyenne rapide d'un
        facteur, ce qui detecte la montee ; et depasser le plancher, ce qui
        interdit au silence de produire du rythme.
        """
        return max(self.moyenne * self.sensibilite,
                   self.plancher,
                   self.fond * MARGE_FOND)

    def ecoute(self):
        """A appeler aussi souvent que possible. True quand un temps tombe."""
        niveau = microphone.sound_level()
        self.echantillons += 1

        # Moyennes glissantes exponentielles. Tant qu'on a vu peu
        # d'echantillons, l'inertie est reduite d'autant : les moyennes se
        # calent en quelques dixiemes de seconde au lieu de partir de zero et
        # de laisser passer une rafale de faux temps au demarrage.
        self.moyenne += (niveau - self.moyenne) / min(self.echantillons,
                                                      INERTIE_MOYENNE)
        self.fond += (niveau - self.fond) / min(self.echantillons,
                                                INERTIE_FOND)

        # Energie normalisee 0..1, utilisee pour moduler la vitesse des pales.
        self.energie = min(1.0, niveau / 255)

        if self.echantillons < AMORCE:
            return False

        maintenant = running_time()
        if maintenant - self.dernier_beat < self.temps_mort:
            return False
        if niveau < self.seuil():
            return False

        if self.dernier_beat:
            self.intervalle = maintenant - self.dernier_beat
        self.dernier_beat = maintenant
        self.compte += 1
        return True

    def temps(self):
        """Rang du temps courant dans la mesure, de 1 a `mesure`."""
        if not self.compte:
            return 0
        return (self.compte - 1) % self.mesure + 1

    def accent(self):
        """True sur le premier temps de la mesure."""
        return self.temps() == 1

    def bpm(self):
        """Tempo estime, 0 tant qu'aucun intervalle n'a ete mesure."""
        if not self.intervalle:
            return 0
        return int(60000 / self.intervalle)

    def silence(self, depuis=3000):
        """True si plus aucun temps n'a ete detecte depuis `depuis` ms.

        Sert a couper les pales quand la musique s'arrete : une salle vide ne
        doit pas laisser l'installation tourner toute la nuit. La detection
        continue pendant ce temps, donc les pales repartent d'elles memes des
        que la musique reprend.
        """
        if not self.dernier_beat:
            # Rien n'a jamais ete detecte : on compte depuis l'allumage.
            return running_time() > depuis
        return running_time() - self.dernier_beat > depuis
