"""Motifs de mouvement des pales.

Chaque motif recoit deux appels :

    sur_beat()      au moment ou un beat tombe
    tic(energie)    en continu, energie valant 0.0 a 1.0

et rend un couple (vitesse_gauche, vitesse_droite, contra) que la boucle
principale envoie aux moteurs. Un motif ne parle jamais a l'I2C lui meme :
cela laisse tester la choregraphie sans robot, et evite de saturer le bus.

Regle de fond du repertoire : ON VEUT DES A COUPS. Une pale qui tourne a
vitesse constante ne raconte rien — on ne voit plus la musique, seulement un
moteur. Chaque motif doit donc donner un COUP au temps detecte, et retomber
franchement entre deux. Les motifs evenementiels retombent a zero, le seul
motif continu garde une rotation de fond mais y ajoute un coup de fouet qui
s'eteint en quelques dixiemes de seconde.
"""

from microbit import running_time

import random


class Motif:
    nom = "?"

    # Un motif continu entretient une rotation de fond, que les temps viennent
    # moduler. Un motif evenementiel ne bouge QUE sur un temps et retombe a zero
    # entre deux : dans le silence, il laisse les pales strictement immobiles.
    continu = False

    def sur_beat(self):
        pass

    def tic(self, energie):
        return (0, 0, False)


class Pulsation(Motif):
    """Une impulsion breve a chaque beat, puis extinction. Le motif par defaut.

    C'est l'a coup a l'etat pur, et le plus lisible de tous : entre deux temps
    les moteurs sont a l'arret franc, donc chaque temps se voit. Avec des pales
    rigides on voit le quart de tour ; avec des rubans on obtient un claquement.
    """

    nom = "pulsation"

    def __init__(self, force=255, duree=110):
        self.force = force
        self.duree = duree
        # None et non 0 : running_time() vaut presque zero au demarrage, donc un
        # debut a 0 declencherait une impulsion pleine puissance avant meme le
        # premier temps.
        self.debut = None

    def sur_beat(self):
        self.debut = running_time()

    def tic(self, energie):
        if self.debut is None:
            return (0, 0, True)
        if running_time() - self.debut > self.duree:
            return (0, 0, True)
        # Impulsion CARREE, et non une decroissance : une rampe qui redescend
        # laisse une longue queue a faible couple, juste assez pour entretenir
        # la rotation sans jamais la marquer. Pleine puissance d'un coup, puis
        # rien — c'est le contraste qui fait l'a coup, pas la duree.
        v = int(self.force * (0.6 + 0.4 * energie))
        return (v, v, True)


class Balancier(Motif):
    """Les deux pales alternent, une roue par beat.

    Dissymetrique et plus organique que la ronde : le mouvement se passe d'un
    cote a l'autre du robot, comme une respiration.
    """

    nom = "balancier"

    def __init__(self, vitesse=245, duree=150):
        self.vitesse = vitesse
        self.duree = duree
        self.cote = 0
        self.debut = None   # voir Pulsation : pas de coup de fouet au demarrage

    def sur_beat(self):
        self.cote = 1 - self.cote
        self.debut = running_time()

    def tic(self, energie):
        if self.debut is None:
            return (0, 0, True)
        if running_time() - self.debut > self.duree:
            return (0, 0, True)
        # Meme choix que Pulsation : impulsion carree, arret franc.
        v = int(self.vitesse * (0.6 + 0.4 * energie))
        return (v, 0, True) if self.cote else (0, v, True)


class Tourbillon(Motif):
    """Rotation par bouffees, qui s'inverse tous les quatre beats.

    L'inversion tombe sur le premier temps quand la detection suit une mesure a
    quatre temps. Les rubans se retournent, ce qui produit l'accent visuel le
    plus fort du repertoire. Le moteur est arrete brievement avant chaque
    inversion : lancer le sens oppose a pleine vitesse fait caler le pont en H.

    Entre deux temps la rotation redescend a une trainee lente et non a la
    vitesse pleine : c'est ce qui donne la respiration, sans quoi on ne voit
    plus que l'inversion une fois par mesure.
    """

    nom = "tourbillon"
    continu = True

    def __init__(self, vitesse=255, trainee=70, mesure=4, pause=90, retombee=0.86):
        self.vitesse = vitesse
        self.trainee = trainee
        self.mesure = mesure
        self.pause = pause
        self.retombee = retombee
        self.compte = 0
        self.contra = True
        self.inversion = 0
        self.coup = 0.0

    def sur_beat(self):
        self.compte += 1
        self.coup = 1.0
        if self.compte % self.mesure == 0:
            self.contra = not self.contra
            self.inversion = running_time()

    def tic(self, energie):
        if running_time() - self.inversion < self.pause:
            self.coup = 0.0
            return (0, 0, self.contra)
        # Le coup s'eteint en quelques tours de boucle : a 50 Hz, 0.86 par tour
        # laisse environ deux dixiemes de seconde de poussee. C'est court expres,
        # c'est ce qui fait l'a coup.
        self.coup *= self.retombee
        v = int(self.trainee + (self.vitesse - self.trainee) * self.coup
                * (0.5 + 0.5 * energie))
        return (v, v, self.contra)


class Ronde(Motif):
    """Rotation continue, vitesse proportionnelle a l'energie sonore.

    Le seul motif du repertoire qui ne s'arrete jamais, et donc le plus doux :
    la force centrifuge deploie les rubans et ils tracent un disque net. Le
    temps s'y lit comme une accélération breve — un coup de fouet qui retombe
    en un tiers de seconde sur la rotation de fond — et non comme un arret.

    A reserver aux rubans : c'est le motif ou le rythme se voit le moins.
    """

    nom = "ronde"
    continu = True

    def __init__(self, mini=70, maxi=255, coup=110, retombee=0.88):
        self.mini = mini
        self.maxi = maxi
        self.force_coup = coup
        self.retombee = retombee
        self.fond = mini
        self.coup = 0.0

    def sur_beat(self):
        self.coup = self.force_coup

    def tic(self, energie):
        # La rotation de fond suit l'energie en douceur : elle porte le morceau,
        # pas le temps.
        cible = self.mini + (self.maxi - self.mini) * energie * 0.6
        self.fond += (cible - self.fond) / 12
        self.coup *= self.retombee
        return (int(min(self.maxi, self.fond + self.coup)),
                int(min(self.maxi, self.fond + self.coup)),
                True)


# Les motifs simples, ceux qui font vraiment tourner les pales. Aleatoire pioche
# la dedans, il ne peut donc pas se tirer lui meme.
REPERTOIRE_SIMPLE = (Pulsation, Balancier, Tourbillon, Ronde)

# Duree d'un motif avant que Aleatoire n'en tire un autre.
DUREE_TIRAGE = 60000


class Aleatoire(Motif):
    """Tire un motif au sort et en change toutes les minutes.

    Le motif d'une installation qu'on laisse tourner : sans lui, une soiree
    entiere se passe sur la meme choregraphie et l'oeil s'y fait au bout de
    quelques morceaux. La minute est un compromis — assez long pour qu'un motif
    s'installe et qu'on le reconnaisse, assez court pour qu'on ne se demande pas
    si le robot est bloque.

    Le tirage exclut le motif en cours : sur quatre possibilites, retomber sur
    le meme donnerait deux minutes identiques et l'on croirait a une panne.

    Ce motif ne pilote rien lui meme, il delegue. `continu` vaut True parce que
    ce qu'il enveloppe peut l'etre : c'est la valeur prudente.
    """

    nom = "aleatoire"
    continu = True

    def __init__(self, duree=DUREE_TIRAGE):
        self.duree = duree
        self.debut = 0
        self.motif = None
        self.tire()

    def tire(self):
        courant = type(self.motif) if self.motif else None
        choix = [c for c in REPERTOIRE_SIMPLE if c is not courant]
        self.motif = random.choice(choix)()
        self.debut = running_time()

    def sur_beat(self):
        self.motif.sur_beat()

    def tic(self, energie):
        if running_time() - self.debut > self.duree:
            self.tire()
        return self.motif.tic(energie)


# Ordre de defilement avec le bouton A. Le premier est celui qui demarre, et
# c'est deliberement le plus percussif : au premier essai, on veut voir la
# musique dans les pales, pas un moteur qui ronronne.
REPERTOIRE = REPERTOIRE_SIMPLE + (Aleatoire,)
