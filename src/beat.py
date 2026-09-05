"""Detection du rythme au micro integre du micro:bit v2.

Le micro:bit v2 mesure un niveau sonore de 0 a 255. On n'a ni FFT ni budget
CPU pour une vraie analyse spectrale, donc on detecte l'energie : un beat est
une montee brusque du niveau au dessus de sa moyenne recente.

Trois garde-fous rendent la detection utilisable en salle :

  moyenne glissante  le seuil suit le volume ambiant, donc la detection
                     fonctionne autant sur une musique douce que forte
  plancher de bruit  empeche le silence de se faire detecter comme un rythme,
                     puisque le moindre souffle depasse une moyenne quasi nulle
  temps mort         apres un beat, on ignore les montees pendant quelques
                     dizaines de ms : une caisse claire produit plusieurs pics
                     rapproches qu'il ne faut compter qu'une fois
"""

from microbit import running_time, microphone, sleep


class Detecteur:
    def __init__(self, sensibilite=1.30, temps_mort=150, plancher=12):
        """
        sensibilite  rapport au dessus de la moyenne pour declarer un beat.
                     Plus bas = plus sensible. En dessous de 1.15 la detection
                     part en vrille sur du bruit continu.
        temps_mort   duree en ms pendant laquelle on ignore les pics apres un
                     beat. 150 ms plafonne la detection a 400 BPM.
        plancher     niveau sonore minimal pour qu'un beat compte. Monter cette
                     valeur si le robot s'agite dans une piece silencieuse.
        """
        self.sensibilite = sensibilite
        self.temps_mort = temps_mort
        self.plancher = plancher

        self.moyenne = 0
        self.dernier_beat = 0
        self.intervalle = 0
        self.energie = 0

        # Nombre total de temps depuis l'allumage, et rang du temps dans la
        # mesure. Les motifs s'en servent pour accentuer, l'affichage pour
        # montrer ou l'on en est.
        self.compte = 0
        self.mesure = 4

    def calibre(self, duree=1200):
        """Mesure le bruit de fond avant de commencer a detecter.

        Sans cela la moyenne glissante part de zero, et pendant les premieres
        secondes le moindre souffle la depasse : le robot voit une rafale de
        faux temps a l'allumage, juste au moment ou l'on cherche a regler la
        sensibilite. On echantillonne donc la piece a vide, et on installe cette
        valeur comme point de depart.

        Rend le niveau ambiant mesure.
        """
        debut = running_time()
        total = 0
        echantillons = 0
        while running_time() - debut < duree:
            total += microphone.sound_level()
            echantillons += 1
            sleep(5)

        if echantillons:
            self.moyenne = total / echantillons

        # Le plancher ne descend jamais sous celui demande a la construction :
        # une piece calme ne doit pas rendre le detecteur hypersensible.
        self.plancher = max(self.plancher, self.moyenne * 1.2)
        return self.moyenne

    def temps(self):
        """Rang du temps courant dans la mesure, de 1 a `mesure`."""
        if not self.compte:
            return 0
        return (self.compte - 1) % self.mesure + 1

    def accent(self):
        """True sur le premier temps de la mesure."""
        return self.temps() == 1

    def ecoute(self):
        """A appeler aussi souvent que possible. True quand un beat tombe."""
        niveau = microphone.sound_level()

        # Moyenne glissante exponentielle. Le facteur 16 donne une memoire
        # d'environ une seconde a la cadence de la boucle principale : assez
        # long pour ne pas suivre le beat lui meme, assez court pour s'adapter
        # quand un morceau change d'intensite.
        self.moyenne += (niveau - self.moyenne) / 16

        # Energie normalisee 0..1, utilisee pour moduler la vitesse des pales.
        self.energie = min(1.0, niveau / 255)

        maintenant = running_time()
        if maintenant - self.dernier_beat < self.temps_mort:
            return False
        if niveau < self.plancher:
            return False
        if niveau < self.moyenne * self.sensibilite:
            return False

        if self.dernier_beat:
            self.intervalle = maintenant - self.dernier_beat
        self.dernier_beat = maintenant
        self.compte += 1
        return True

    def bpm(self):
        """Tempo estime, 0 tant qu'aucun intervalle n'a ete mesure."""
        if not self.intervalle:
            return 0
        return int(60000 / self.intervalle)

    def silence(self, depuis=3000):
        """True si plus aucun beat depuis `depuis` ms."""
        return running_time() - self.dernier_beat > depuis
