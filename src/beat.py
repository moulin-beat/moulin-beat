"""Detection du rythme au micro integre du micro:bit v2.

Le micro:bit v2 mesure un niveau sonore de 0 a 255. On n'a ni FFT ni budget CPU
pour une vraie analyse spectrale, donc on detecte l'energie : un temps est une
MONTEE brusque du niveau au dessus de sa moyenne recente.

Trois suiveurs, entretenus en permanence, qui ne regardent pas la meme chose :

  moyenne   niveau moyen sur environ une seconde et demie. Le seuil s'y
            rapporte : un temps, c'est un niveau qui la depasse d'un facteur.
            Elle doit rester PLUS LENTE que le tempo, sinon elle suit le beat
            lui meme, monte avec lui, et plus rien ne depasse jamais : les
            pales tournent alors d'un bloc, sans le moindre a coup.

  fond      le silence de la salle, et non son niveau moyen. Il descend vite et
            remonte tres lentement, donc il colle aux creux entre deux temps au
            lieu de se laisser tirer vers le haut par la musique. C'est ce qui
            lui permet de servir de plancher meme apres une heure de morceau
            fort : une moyenne lente, elle, finirait a hauteur de la musique et
            interdirait toute detection.

  pic       le sommet recent, qui redescend en quelques secondes. Avec le fond,
            il donne l'echelle reelle du morceau : l'energie rendue aux motifs
            balaie alors vraiment 0 a 1, au lieu de stagner autour de 0,3 comme
            le ferait un simple niveau / 255.

Aucune calibration ponctuelle : tout se recale seul en continu. Une installation
qui tourne des heures traverse ainsi les changements de morceau, la salle qui se
remplit et les variations de volume sans qu'on ait a y toucher. Les suiveurs se
calent d'autant plus vite qu'ils ont vu peu d'echantillons, ce qui evite
d'attendre au demarrage.
"""

from microbit import running_time, microphone

# Inerties, en nombre d'echantillons. La boucle principale tourne a environ
# 50 Hz, donc 70 valent une seconde et demie et 3000 valent une minute.
#
# 70 et pas 16 : a 120 BPM un temps tombe toutes les 500 ms, soit 25
# echantillons. Une moyenne calee sur un tiers de seconde monte avec chaque
# temps et le seuil monte avec elle — c'est le defaut qui faisait tourner les
# moteurs sans aucun a coup des que la musique durait.
INERTIE_MOYENNE = 70
INERTIE_FOND = 3000
INERTIE_DESCENTE = 12
INERTIE_PIC = 200

# Niveau sonore considere comme "plein regime" pour l'energie rendue aux motifs.
# Le micro du micro:bit ne monte a 255 que colle a une enceinte : rapporter
# l'energie a 255 la ferait stagner vers 0,3 et les pales n'auraient jamais
# leur pleine course.
NIVEAU_PLEIN = 180

# Marge demandee au dessus du silence de la salle pour qu'un temps compte.
#
# 1.25 et non 1.6 : la valeur haute datait de l'epoque ou `fond` etait une
# moyenne sur une minute, donc un niveau de salle. Depuis qu'il suit les CREUX
# de la musique, 1.6 fois ce creux tombe juste sous les cretes — ce terme
# devenait alors le seuil reel et `sensibilite` ne servait plus a rien, alors
# que c'est le reglage documente. Mesure sur signal de reference : le seuil
# passe de 140 a 111, la detection reste a 120 BPM (59 temps sur 60 attendus en
# 30 secondes), et la marge de reglage passe de 0,15 — indicateur colle en
# butee — a 0,66, en plein dans la bande saine.
#
# Ce terme redevient ce qu'il doit etre : un PLANCHER, qui ne mord que dans une
# piece calme, et non la regle du jeu.
MARGE_FOND = 1.25

# Le temps de laisser les suiveurs se caler avant de detecter quoi que ce soit.
AMORCE = 25

# Nombre de temps sur lesquels la regularite du tempo se juge. Huit couvrent
# deux mesures : assez pour qu'un morceau s'affirme, assez peu pour qu'un
# changement de tempo se voie sans attendre.
INERTIE_TEMPO = 8


class Detecteur:
    def __init__(self, sensibilite=1.18, temps_mort=250, plancher=12):
        """
        sensibilite  rapport au dessus de la moyenne pour declarer un temps.
                     Plus bas = plus sensible. La montee devant aussi etre
                     franche (voir `ecoute`), on peut descendre plus bas qu'avec
                     un seuil seul : en dessous de 1.10 la detection part
                     malgre tout en vrille sur du bruit continu.
        temps_mort   duree en ms pendant laquelle on ignore les pics apres un
                     temps. Une caisse claire produit plusieurs pics rapproches
                     qu'il ne faut compter qu'une fois. 250 ms plafonnent la
                     detection a 240 BPM, et surtout garantissent qu'une
                     impulsion de 110 ms est terminee, roue freinee, avant le
                     temps suivant : sans cette marge les impulsions se
                     recouvrent et la rotation redevient continue.
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
        self.pic = 0
        self.niveau = 0
        self.echantillons = 0

        self.dernier_beat = 0
        self.intervalle = 0
        self.intervalle_moyen = 0
        # Ecart moyen entre deux intervalles, rapporte a l'intervalle : 0 pour
        # un metronome, proche de 1 pour du bruit pris pour du rythme. C'est la
        # mesure de QUALITE de la detection, et la seule qu'on ait : rien ici ne
        # sait si un temps detecte correspond a un vrai temps de la musique,
        # mais un train de temps irreguliers ne peut pas etre de la musique.
        self.gigue = 0.0
        self.energie = 0

        # Nombre total de temps depuis l'allumage, et rang du temps dans la
        # mesure. Les motifs s'en servent pour accentuer, l'affichage pour
        # montrer ou l'on en est.
        self.compte = 0
        self.mesure = 4

    def seuil(self):
        """Niveau a depasser pour qu'un temps soit declare.

        Trois conditions, et il les faut toutes : depasser la moyenne d'un
        facteur, ce qui detecte la montee ; depasser le plancher absolu, ce qui
        interdit au silence de produire du rythme ; depasser le silence de la
        salle avec une marge, ce qui ecarte le brouhaha du public.
        """
        return max(self.moyenne * self.sensibilite,
                   self.plancher,
                   self.fond * MARGE_FOND)

    def ecoute(self):
        """A appeler aussi souvent que possible. True quand un temps tombe."""
        niveau = microphone.sound_level()
        precedent = self.niveau
        self.niveau = niveau
        self.echantillons += 1

        # Suiveurs exponentiels. Tant qu'on a vu peu d'echantillons, l'inertie
        # est reduite d'autant : ils se calent en quelques dixiemes de seconde
        # au lieu de partir de zero et de laisser passer une rafale de faux
        # temps au demarrage.
        vus = self.echantillons
        self.moyenne += (niveau - self.moyenne) / min(vus, INERTIE_MOYENNE)

        # Le fond, lui, est dissymetrique : prompt a descendre, lent a monter.
        # C'est ce qui en fait le niveau des creux, et non celui du morceau.
        if niveau < self.fond:
            self.fond += (niveau - self.fond) / min(vus, INERTIE_DESCENTE)
        else:
            self.fond += (niveau - self.fond) / min(vus, INERTIE_FOND)

        # Le pic est dissymetrique dans l'autre sens : il saute au sommet et en
        # redescend en quelques secondes.
        if niveau > self.pic:
            self.pic = niveau
        else:
            self.pic += (niveau - self.pic) / min(vus, INERTIE_PIC)

        # Energie 0..1 : la vigueur du morceau, et non la position dans la
        # mesure. C'est le bouton de puissance des motifs, il doit donc etre
        # STABLE — assis sur le pic, qui met quelques secondes a redescendre,
        # et non sur le niveau instantane qui saute a chaque temps.
        self.energie = min(1.0, self.pic / NIVEAU_PLEIN)

        if vus < AMORCE:
            return False

        maintenant = running_time()
        if maintenant - self.dernier_beat < self.temps_mort:
            return False
        if niveau < self.seuil():
            return False
        # Il faut une MONTEE, pas seulement un niveau haut. Sans cette
        # condition, un passage fort et soutenu — un refrain sature, une nappe —
        # tient le seuil en continu et fait declarer un temps a chaque tour de
        # boucle : les pales tournent alors sans jamais marquer le rythme.
        if niveau <= precedent:
            return False

        if self.dernier_beat:
            self.intervalle = maintenant - self.dernier_beat
            if self.intervalle_moyen:
                ecart = (abs(self.intervalle - self.intervalle_moyen)
                         / self.intervalle_moyen)
                if ecart > 1.0:
                    ecart = 1.0
                self.gigue += (ecart - self.gigue) / INERTIE_TEMPO
                self.intervalle_moyen += ((self.intervalle - self.intervalle_moyen)
                                          / INERTIE_TEMPO)
            else:
                self.intervalle_moyen = self.intervalle
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

    def marge(self):
        """Ou se situe le seuil entre la nappe et les cretes. 0 a 1.

        C'est le DIAGNOSTIC du reglage, et non une grandeur du son. Il repond a
        la seule question qu'on se pose devant l'installation : le seuil est il
        bien place ?

            <= 0   le seuil est au dessus des cretes. Rien ne sera jamais
                   detecte : il est trop haut.
             0.5   le seuil est a mi chemin entre la nappe et les cretes.
                   C'est le reglage sain, celui qui laisse passer les temps et
                   arrete le reste.
               1   le seuil est descendu au niveau de la nappe. Tout le declenche,
                   la detection part en rafale : il est trop bas.

        Un rapport, et non une difference : il reste juste que la musique soit
        forte ou douce, ce qui est tout l'interet pour une installation qui
        traverse une soiree entiere.
        """
        seuil = self.seuil()
        if seuil >= self.pic:
            # Le seuil couvre les cretes : rien ne passera. Le cas se produit
            # aussi sur un signal parfaitement plat, ou il n'y a pas de crete.
            return 0.0
        haut = self.pic - self.moyenne
        if haut <= 0:
            return 1.0
        part = (self.pic - seuil) / haut
        if part < 0:
            return 0.0
        return part if part < 1 else 1.0

    def tempo_etabli(self, depuis=2500):
        """True si un tempo regulier est en cours d'observation.

        Sert a distinguer « detection parfaitement reguliere » de « aucune
        detection », que la seule gigue confondrait : les deux valent zero.
        """
        return self.compte >= 3 and not self.silence(depuis)

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
