"""Motifs de mouvement des pales.

Chaque motif recoit deux appels :

    sur_beat()      au moment ou un beat tombe
    tic(energie)    en continu, energie valant 0.0 a 1.0

et rend un couple (vitesse_gauche, vitesse_droite, contra) que la boucle
principale envoie aux moteurs. Un motif ne parle jamais a l'I2C lui meme :
cela laisse tester la choregraphie sans robot, et evite de saturer le bus.
"""

from microbit import running_time


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


class Ronde(Motif):
    """Rotation continue, vitesse proportionnelle a l'energie sonore.

    Le mouvement le plus lisible avec des rubans : la force centrifuge les
    deploie et ils tracent un disque net. Les passages calmes ralentissent le
    disque sans jamais le rompre.
    """

    nom = "ronde"
    continu = True

    def __init__(self, mini=60, maxi=255):
        self.mini = mini
        self.maxi = maxi
        self.vitesse = mini

    def sur_beat(self):
        # Le beat donne un coup de fouet, l'energie fait le reste.
        self.vitesse = min(self.maxi, self.vitesse + 35)

    def tic(self, energie):
        cible = self.mini + (self.maxi - self.mini) * energie
        # Approche douce de la cible : sans lissage, les pales saccadent et les
        # rubans s'enroulent autour de l'axe.
        self.vitesse += (cible - self.vitesse) / 8
        v = int(self.vitesse)
        return (v, v, True)


class Pulsation(Motif):
    """Une impulsion breve a chaque beat, puis extinction.

    Marque le tempo de facon tres lisible. Avec des pales rigides on voit le
    quart de tour ; avec des rubans on obtient un claquement.
    """

    nom = "pulsation"

    def __init__(self, force=255, duree=120):
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
        reste = running_time() - self.debut
        if reste > self.duree:
            return (0, 0, True)
        # Decroissance lineaire sur la duree de l'impulsion.
        v = int(self.force * (1 - reste / self.duree))
        return (v, v, True)


class Tourbillon(Motif):
    """Rotation continue qui s'inverse tous les quatre beats.

    L'inversion tombe sur le premier temps quand la detection suit une mesure a
    quatre temps. Les rubans se retournent, ce qui produit l'accent visuel le
    plus fort du repertoire. Le moteur est arrete brievement avant chaque
    inversion : lancer le sens oppose a pleine vitesse fait caler le pont en H.
    """

    nom = "tourbillon"
    continu = True

    def __init__(self, vitesse=200, mesure=4, pause=90):
        self.vitesse = vitesse
        self.mesure = mesure
        self.pause = pause
        self.compte = 0
        self.contra = True
        self.inversion = 0

    def sur_beat(self):
        self.compte += 1
        if self.compte % self.mesure == 0:
            self.contra = not self.contra
            self.inversion = running_time()

    def tic(self, energie):
        if running_time() - self.inversion < self.pause:
            return (0, 0, self.contra)
        v = int(self.vitesse * (0.5 + 0.5 * energie))
        return (v, v, self.contra)


class Balancier(Motif):
    """Les deux pales alternent, une roue par beat.

    Dissymetrique et plus organique que la ronde : le mouvement se passe d'un
    cote a l'autre du robot, comme une respiration.
    """

    nom = "balancier"

    def __init__(self, vitesse=220, duree=200):
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
        reste = running_time() - self.debut
        if reste > self.duree:
            return (0, 0, True)
        v = int(self.vitesse * (1 - reste / self.duree))
        return (v, 0, True) if self.cote else (0, v, True)


# Ordre de defilement avec le bouton A.
REPERTOIRE = (Ronde, Pulsation, Tourbillon, Balancier)
