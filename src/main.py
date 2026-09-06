"""moulin-beat : le micro:Maqueen fait tourner ses pales sur la musique.

Le robot est pose sur un berceau, roues en l'air. Chaque roue porte une croix
de pales, ou des rubans. Le micro:bit v2 ecoute la piece et entraine les roues
au rythme detecte.

Commandes
    bouton A    motif suivant, de 1 a 5, en boucle
    bouton B    amortissement, de 0 a 5, en boucle
    logo tactile  remet l'amortissement par defaut, puis joue les tests
    secousse    arret d'urgence

La matrice affiche les DEUX reglages en permanence : le numero du motif a
gauche, la jauge d'amortissement dans la derniere colonne. Voir tableau().

Le programme DEMARRE SEUL des la mise sous tension. C'est ce qu'on veut d'une
installation qu'on branche et qu'on laisse : personne ne doit avoir a chercher
un bouton. En contrepartie il faut se souvenir que brancher, c'est lancer — un
robot pose a plat sur une table part au premier temps. Le compte a rebours de
deux secondes au demarrage sert a le rattraper ; le supprimer, c'est retirer
COMPTE_A_REBOURS.

Apres un arret d'urgence, on repart en touchant le logo.

A chaque temps detecte, la matrice montre le rang du temps dans la mesure et les
phares avant clignotent : les deux sur le premier temps, un seul sur les autres.
Les quatre LED sous le chassis forment le tableau de bord : volume, moteur, et
deux diagnostics qui disent si le reglage tient — voir eclaire_sol().

Entre deux temps les roues sont FREINEES, et non simplement mises a zero : voir
maqueen.pales(). Sans cela l'inertie des pales gomme les a coups et l'on ne voit
plus qu'un moteur qui tourne. C'est la force de ce freinage que les boutons A et
B reglent. Le nombre de roues montees se regle dans maqueen.py,
ROUE_GAUCHE_ACTIVE et ROUE_DROITE_ACTIVE.

Le detecteur se recale en continu sur le volume ambiant, sans calibration
ponctuelle : l'installation traverse les changements de morceau et les
variations de salle toute seule. Quand la musique s'arrete, les pales s'arretent
aussi, et repartent d'elles memes au retour du son.
"""

from microbit import (
    display, button_a, button_b, pin_logo, accelerometer, sleep, Image,
    running_time,
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

# Delai de grace au demarrage, le programme se lancant tout seul. Deux secondes,
# le temps de reposer le robot sur son berceau s'il etait encore en main.
COMPTE_A_REBOURS = 2

# Rafraichissement des LED de sol : un tic sur trois, soit 60 ms. L'oeil n'y
# verra pas de saccade et la boucle garde son temps pour l'ecoute.
SOL_TOUS_LES = 3

# Les cinq chiffres du repertoire, dessines sur trois colonnes et cinq lignes.
#
# Trois et non quatre, alors que la matrice en laisse quatre : la quatrieme
# reste vide et sert de SEPARATEUR avec la jauge. Un chiffre colle a la jauge se
# lit comme un seul dessin, et l'on ne sait plus ou finit l'un et ou commence
# l'autre. La colonne perdue est ce qui rend les deux lisibles.
CHIFFRES = (
    ("090", "990", "090", "090", "999"),
    ("999", "009", "999", "900", "999"),
    ("999", "009", "999", "009", "999"),
    ("909", "909", "999", "009", "009"),
    ("999", "900", "999", "009", "999"),
)

# Plafond de luminosite des LED de sol, par canal. Tres bas expres : une WS2812
# a fond tire 60 mA, soit 240 mA pour les quatre — plus que les moteurs.
SOL_LUM = 40

# La carte de couleurs des grandeurs sonores : froid en bas, chaud en haut.
#
# Pourquoi une teinte et non une luminosite : l'oeil ne sait pas juger une
# luminosite absolue. Il en juge le contraste avec ce qui l'entoure, donc la
# lecture change avec la distance, avec l'eclairage de la piece, et selon qu'une
# pale passe devant ou non. Une teinte, elle, se NOMME d'un coup d'oeil, et
# reste la meme a trois metres comme a trente centimetres. Sur un cadran qu'on
# lit de loin, a travers les pales, c'est ce qui fait la difference entre un
# indicateur et une guirlande.
#
# Les amplitudes ne sont pas normalisees a la meme somme mais a la meme
# luminosite APPARENTE, corrigee a l'oeil : le bleu pur parait tres sombre a
# egale puissance, le vert et le jaune tres clairs. Sans cette correction, la
# carte se lit autant comme un degrade de luminosite que de teinte, et les deux
# se contredisent au milieu.
# Exposant de compression de l'echelle, voir Moulin._teinte.
SOL_COMPRESSION = 0.7

# Marge au dessus du sommet du morceau. Sans elle, le seuil de detection — qui
# se tient juste sous les cretes, c'est sa raison d'etre — sature en haut de la
# carte et reste rouge en permanence : une LED figee, qui n'apprend rien. Avec
# 12 % de marge il se pose dans l'orange, les temps atteignent le rouge, et
# l'ecart entre les deux redevient lisible.
SOL_MARGE = 1.12

SOL_CARTE = (
    (0.00, (0.00, 0.00, 1.00)),   # bleu    — au niveau du silence
    (0.25, (0.00, 0.50, 0.90)),   # cyan
    (0.50, (0.00, 0.75, 0.00)),   # vert
    (0.75, (0.90, 0.60, 0.00)),   # jaune
    (1.00, (1.00, 0.00, 0.00)),   # rouge   — au sommet du morceau
)


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
        # Evite de repeter l'ordre d'arret et l'affichage a chaque tour pendant
        # un silence, qui peut durer des heures.
        self.endormi = False
        # Le logo est un contact tactile, pas un bouton : il rend True tant
        # qu'on le touche. Sans ce front, les tests repartiraient en boucle.
        self.logo_touche = False
        self.tic = 0
        # Vitesse moteur en cours, pour la LED de sol qui la montre.
        self.vitesse = 0
        # Dernier etat dessine sur la matrice, pour ne pas la reconstruire a
        # chaque tour. None force le prochain dessin.
        self.affiche = None

    def motif_suivant(self):
        """Bouton A : on avance dans le repertoire, en boucle."""
        self.index = (self.index + 1) % len(choregraphie.REPERTOIRE)
        self.motif = choregraphie.REPERTOIRE[self.index]()
        self.vitesse = 0
        maqueen.pales(0, 0)

    def amortissement_suivant(self):
        """Bouton B : on avance dans les crans, en boucle.

        En boucle et non en butee : avec six crans seulement, revenir a zero
        depuis le maximum coute un appui, pas dix. Un seul bouton suffit donc,
        ce qui libere l'autre pour les motifs.
        """
        niveau = maqueen.amortissement() + 1
        if niveau > maqueen.AMORTISSEMENT_MAX:
            niveau = 0
        maqueen.regle_amortissement(niveau)

    def tableau(self):
        """La matrice, en permanence : le motif a gauche, l'amortissement a droite.

            colonnes 0 a 2   le numero du motif, de 1 a 5
            colonne 3        vide, pour separer
            colonne 4        la jauge d'amortissement, une LED par cran,
                             remplie par le bas

        Les deux reglages sont affiches EN PERMANENCE, et non le temps d'un
        appui. C'est ce qui permet de regler sans regarder ce qu'on fait : on
        appuie jusqu'a voir la bonne jauge. Auparavant le chiffre s'affichait
        400 ms puis disparaissait, et l'on reglait de memoire — en bloquant la
        boucle pendant ce temps, qui plus est.

        Une jauge et non un chiffre pour l'amortissement : elle se lit sans
        rien interpreter, et son remplissage va dans le meme sens que ce qu'elle
        commande — plus elle monte, plus la pale est arretee net.

        L'image n'est reconstruite que lorsqu'un des deux reglages change : sans
        ce cache, on fabriquerait un objet Image cinquante fois par seconde pour
        rien.
        """
        amorti = maqueen.amortissement()
        etat = (self.index, amorti)
        if etat == self.affiche:
            return
        self.affiche = etat
        chiffre = CHIFFRES[self.index]
        lignes = []
        for rang in range(5):
            jauge = "9" if rang >= 5 - amorti else "0"
            lignes.append(chiffre[rang] + "0" + jauge)
        display.show(Image(":".join(lignes)))

    def eclaire_sol(self):
        """Les quatre LED sous le chassis : le tableau de bord.

            RGB0  volume brut          carte de couleurs
            RGB1  signal moteur        vert entraine / ROUGE freine
            RGB2  reglage du seuil     carte, se lit AU VERT
            RGB3  regularite du tempo  carte, se lit AU FROID, eteint si rien

        RGB2 et RGB3 ne montrent pas des grandeurs mais des DIAGNOSTICS. C'est
        deliberé : une premiere version y affichait le seuil et la moyenne
        mobile, deux valeurs brutes, et elles n'apprenaient rien. La moyenne
        mobile d'une nappe, c'est la nappe — elle affichait donc la meme couleur
        que RGB0 entre deux temps. Et le seuil, qui se tient par construction
        juste sous les cretes, ne bougeait pratiquement pas. Les deux
        demandaient a l'oeil de COMPARER trois lumieres pour en tirer une
        conclusion. Ces deux la tirent la conclusion.

        RGB2, le reglage du seuil. Ou le seuil se situe entre la nappe et les
        cretes :

            bleu   au dessus des cretes. Rien ne sera detecte, il est trop haut.
            vert   a mi chemin. C'est le reglage sain.
            rouge  au niveau de la nappe. Tout le declenche, c'est la rafale.

        RGB3, la regularite du tempo. L'ecart moyen entre deux intervalles :

            eteint  aucun tempo en cours. Silence, ou rien de detecte.
            bleu    regulier comme un metronome.
            rouge   erratique : ce qui est detecte n'est pas un rythme.

        Mesure sur signal de reference : une musique a 120 BPM donne une gigue
        de 0,00, un bruit sans rythme donne 0,27. Les deux se distinguent d'un
        coup d'oeil, ce qu'aucune des grandeurs brutes ne permettait.
        """
        d = self.detecteur
        bas = d.fond
        haut = d.pic if d.pic > d.seuil() else d.seuil()
        # Une etendue plancher evite qu'un silence total, ou fond et haut se
        # rejoignent, ne fasse partir les teintes dans tous les sens sur du
        # bruit de fond.
        etendue = max(haut * SOL_MARGE - bas, 8)

        if maqueen.frein_declenche():
            # Le freinage dure 27 ms au plus : sans ce verrou pose par maqueen,
            # un rafraichissement sur trois tics le manquerait presque toujours.
            moteur = (SOL_LUM, 0, 0)
        else:
            vert = SOL_LUM * self.vitesse // 255
            moteur = (0, vert, 0)

        if d.tempo_etabli():
            tempo = self._carte(d.gigue)
        else:
            tempo = (0, 0, 0)

        maqueen.sol((
            self._teinte(d.niveau, bas, etendue),
            moteur,
            self._carte(d.marge()),
            tempo,
        ))

    @classmethod
    def _teinte(cls, valeur, bas, etendue):
        """Couleur d'un niveau sonore, sur l'echelle du morceau.

        L'echelle est COMPRESSEE, et c'est ce qui rend le cadran lisible. En
        lineaire tout se tasse en bas : dans un morceau, les cretes sont breves,
        donc la nappe reste tres proche du creux et ne quitte jamais le bleu. La
        compression etale le bas de la plage, ou tout se joue. C'est le principe
        d'un VU-metre en decibels.

        L'exposant est mesure, pas choisi par gout. Une racine carree (0.5)
        etale bien le bas mais tasse le haut : le contretemps et le temps
        finissent tous deux dans le rouge, et l'on perd la nuance qui compte
        justement au moment du beat. 0.7 separe les reperes du signal de
        reference sur toute la carte.
        """
        part = (valeur - bas) / etendue
        if part <= 0:
            part = 0.0
        elif part > 1:
            part = 1.0
        else:
            part = part ** SOL_COMPRESSION
        return cls._carte(part)

    @staticmethod
    def _carte(part):
        """Couleur d'une valeur deja normalisee entre 0 et 1, sur SOL_CARTE.

        Les diagnostics passent par ici sans compression : ils sont deja des
        rapports, une echelle lineaire est ce qu'on veut.
        """
        if part <= 0:
            part = 0.0
        elif part > 1:
            part = 1.0
        precedent, couleur_precedente = SOL_CARTE[0]
        for borne, couleur in SOL_CARTE:
            if part <= borne:
                largeur = borne - precedent
                t = 0.0 if largeur <= 0 else (part - precedent) / largeur
                return tuple(
                    int(SOL_LUM * (a + (b - a) * t))
                    for a, b in zip(couleur_precedente, couleur))
            precedent, couleur_precedente = borne, couleur
        return tuple(int(SOL_LUM * c) for c in SOL_CARTE[-1][1])

    def tests(self):
        """Diagnostic complet, sur le logo tactile.

        L'ordre n'est pas indifferent : les phares d'abord, ils ne demandent
        pas de degager les pales, puis les roues, qui si.
        """
        maqueen.arret()
        self.test_phares()
        self.test_roues()
        self.demarre()

    def test_phares(self):
        """Diagnostic des phares avant.

        Les phares ne clignotent qu'aux temps detectes : s'ils restent eteints
        pendant un morceau, on ne peut pas savoir si c'est la detection qui ne
        trouve rien ou le cablage qui ne suit pas. Cette sequence tranche, sans
        musique et sans REPL.

        Elle essaie les DEUX voies possibles, en annoncant chacune sur la
        matrice :

            P   les broches P8 et P12, cablage du micro:Maqueen V4.2
            I   le bus I2C, registres 11 et 12, cablage des Maqueen V5 et Plus

        Si les phares s'allument sur "I" et pas sur "P", c'est que la carte est
        une revision recente : passer PHARES_I2C a True dans maqueen.py.
        Si aucune des deux ne donne rien, c'est le chassis — souvent
        l'interrupteur ou les piles, comme pour les moteurs.
        """
        for lettre, allume in (("P", maqueen.phares_broches),
                               ("I", maqueen.phares_i2c)):
            display.show(lettre)
            for _ in range(3):
                allume(True, True)
                sleep(300)
                allume(False, False)
                sleep(200)
        display.clear()

    def test_roues(self):
        """Diagnostic moteur.

        Fait tourner chaque roue separement puis les deux ensemble. Permet de
        distinguer d'un coup d'oeil les pannes qui se ressemblent toutes depuis
        la matrice : moteur mort, cablage, ou chassis hors tension. Les deux
        roues sont essayees meme si l'une est desactivee dans maqueen.py :
        c'est un test du materiel, pas de la sculpture.

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

    def pause(self):
        """Arret d'urgence. On en ressort par le logo."""
        self.actif = False
        self.endormi = False
        self.vitesse = 0
        self.affiche = None   # la matrice est prise par le carre d'arret
        maqueen.arret()   # coupe aussi les phares et les LED de sol
        display.show(Image.SQUARE_SMALL)

    def demarre(self):
        self.actif = True
        self.endormi = False
        self.affiche = None   # la matrice appartient de nouveau au tableau
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

        maqueen.arret()

        # Le robot va se lancer tout seul : on previent, et on laisse le temps
        # de le reposer sur son berceau.
        for reste in range(COMPTE_A_REBOURS, 0, -1):
            display.show(str(reste))
            sleep(1000)
        self.demarre()

        while True:
            self.tic += 1

            # Un bouton par reglage, et chacun tourne en boucle. Les deux
            # etant affiches en permanence sur la matrice, on appuie jusqu'a
            # voir ce qu'on veut : pas besoin d'un sens de retour.
            if button_a.was_pressed():
                self.motif_suivant()
            if button_b.was_pressed():
                self.amortissement_suivant()

            # Le logo remet le reglage a sa valeur d'usine et rejoue les tests :
            # c'est le geste de celui qui ne comprend plus ce que fait le robot.
            touche = pin_logo.is_touched()
            if touche and not self.logo_touche:
                maqueen.regle_amortissement(maqueen.AMORTISSEMENT_DEFAUT)
                self.tests()
            self.logo_touche = touche

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

            # Le VU-metre tourne meme pendant le silence : c'est ce qui montre
            # que le dispositif ecoute toujours, et non qu'il est plante.
            if self.tic % SOL_TOUS_LES == 0:
                self.eclaire_sol()

            # Plus de musique : on coupe les moteurs. La detection, elle,
            # continue de tourner, donc les pales repartent seules des que le
            # son revient — sans intervention, ce qui compte pour une
            # installation laissee seule plusieurs heures.
            if self.detecteur.silence(SILENCE_MS):
                if not self.endormi:
                    self.vitesse = 0
                    maqueen.pales(0, 0)
                    maqueen.phares(False, False)
                    display.show(Image.ASLEEP)
                    self.affiche = None   # le dormeur prend la matrice
                    self.endormi = True
                sleep(PERIODE_MS)
                continue

            if self.endormi:
                # La musique reprend.
                self.endormi = False
                self.affiche = None

            gauche, droite, contra = self.motif.tic(self.detecteur.energie)
            self.vitesse = gauche if gauche > droite else droite
            maqueen.pales(gauche, droite, contra)

            # La matrice porte les reglages, en permanence. Elle ne compte plus
            # les temps : les phares le font deja, et de bien plus loin, alors
            # que les reglages n'avaient aucun affichage durable.
            self.tableau()

            if running_time() - self.flash >= FLASH_MS:
                maqueen.phares(False, False)

            sleep(PERIODE_MS)


try:
    Moulin().boucle()
finally:
    # Quoi qu'il arrive, y compris une erreur de programmation, les moteurs
    # s'arretent. Des pales lancees dans un robot plante sont dangereuses.
    maqueen.arret()
