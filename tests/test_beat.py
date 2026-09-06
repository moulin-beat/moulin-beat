"""Vérifie la détection de rythme : adaptation continue, seuil, comptage, silence."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import microbit
import beat

PAS_MS = 20


def fait_ecouter(d, niveau, tours):
    """Fait écouter `tours` échantillons à `niveau`, rend les temps détectés."""
    microbit.joue_niveaux([niveau])
    temps = 0
    for _ in range(tours):
        if d.ecoute():
            temps += 1
        microbit.avance(PAS_MS)
    return temps


def neuf(**kw):
    microbit.remet_a_zero()
    return beat.Detecteur(**kw)


def test_les_moyennes_se_calent_sans_calibration():
    # Aucune calibration ponctuelle : les moyennes doivent converger seules,
    # et vite, sinon le démarrage se remplit de faux temps.
    d = neuf()
    fait_ecouter(d, 40, 60)
    assert 35 <= d.moyenne <= 45, d.moyenne
    assert 30 <= d.fond <= 45, d.fond


def test_pas_de_faux_temps_au_demarrage():
    # Le bruit constant d'une pièce ne doit produire aucun temps, y compris
    # dans les premiers instants où les moyennes partent de zéro.
    d = neuf()
    assert fait_ecouter(d, 45, 200) == 0


def test_le_silence_ne_produit_aucun_temps():
    d = neuf()
    assert fait_ecouter(d, 2, 200) == 0
    assert d.compte == 0


def test_un_pic_franc_produit_un_temps():
    d = neuf()
    fait_ecouter(d, 20, 60)
    microbit.joue_niveaux([200])
    assert d.ecoute()
    assert d.compte == 1


def test_le_seuil_suit_une_salle_qui_monte():
    # Le cas qui motive tout : une soirée où le volume monte sur des heures.
    # Le seuil doit suivre, sinon le robot part en rafale de faux temps.
    d = neuf()
    fait_ecouter(d, 20, 300)
    seuil_calme = d.seuil()

    fait_ecouter(d, 120, 4000)
    seuil_fort = d.seuil()

    assert seuil_fort > seuil_calme * 2, (seuil_calme, seuil_fort)

    # Et à ce nouveau volume, le bruit ambiant ne doit toujours rien déclencher.
    assert fait_ecouter(d, 120, 300) == 0


def test_le_seuil_redescend_quand_la_salle_se_calme():
    # L'inverse : après un passage fort, un morceau doux doit rester détecté.
    d = neuf()
    fait_ecouter(d, 150, 4000)
    seuil_fort = d.seuil()
    fait_ecouter(d, 15, 6000)
    assert d.seuil() < seuil_fort / 2, (seuil_fort, d.seuil())


def test_le_plancher_absolu_tient_en_piece_calme():
    # Une pièce très silencieuse ne doit pas rendre le détecteur hypersensible :
    # le plancher demandé à la construction est un minimum, jamais négociable.
    d = neuf(plancher=30)
    fait_ecouter(d, 1, 500)
    assert d.seuil() >= 30, d.seuil()


def test_le_temps_mort_evite_de_compter_deux_fois():
    d = neuf(temps_mort=150)
    fait_ecouter(d, 20, 60)
    microbit.joue_niveaux([200])
    assert d.ecoute()
    microbit.avance(30)
    assert not d.ecoute(), "pic rapproché compté une seconde fois"
    assert d.compte == 1


def test_silence_signale_apres_le_delai():
    d = neuf()
    fait_ecouter(d, 20, 60)
    microbit.joue_niveaux([200])
    assert d.ecoute()
    assert not d.silence(3000)
    microbit.avance(4000)
    assert d.silence(3000), "le silence doit finir par être signalé"


def test_silence_des_le_depart_si_rien_nest_jamais_detecte():
    # Une salle vide au démarrage : il ne faut pas attendre un premier temps
    # qui ne viendra jamais pour décider que c'est le silence.
    d = neuf()
    fait_ecouter(d, 2, 300)
    assert d.silence(3000)


def test_le_rang_dans_la_mesure_tourne():
    d = neuf()
    assert d.temps() == 0, "aucun temps détecté : rien à afficher"
    for attendu in (1, 2, 3, 4, 1, 2):
        d.compte += 1
        assert d.temps() == attendu, (d.compte, d.temps(), attendu)
    d.compte = 4
    assert not d.accent()
    d.compte = 5
    assert d.accent(), "le premier temps de la mesure doit porter l'accent"


def test_la_gigue_separe_la_musique_du_bruit():
    # Les deux diagnostics du tableau de bord n'ont d'intérêt que s'ils
    # discriminent vraiment. Rien ici ne sait si un temps détecté correspond à
    # un vrai temps de la musique — mais un train de temps irréguliers ne peut
    # pas être de la musique.
    import random

    def joue(bruit):
        microbit.remet_a_zero()
        random.seed(5)
        d = beat.Detecteur()
        for tic in range(750):
            if bruit:
                niveau = 90 + random.randint(-6, 60)
            else:
                phase = tic % 25
                niveau = 90 + random.randint(-6, 6)
                if phase == 0:
                    niveau = 150
                elif phase == 1:
                    niveau = 130
            microbit.joue_niveaux([niveau])
            d.ecoute()
            microbit.avance(PAS_MS)
        return d

    # Seuils tirés de la mesure sur quatre graines : la musique donne 0,000
    # à chaque fois, le bruit de 0,14 à 0,25.
    musique = joue(False)
    bruit = joue(True)
    assert musique.gigue < 0.05, musique.gigue
    assert bruit.gigue > 0.12, bruit.gigue


def test_la_marge_dit_ou_le_seuil_est_place():
    # Le diagnostic doit pointer la DIRECTION, sinon il n'est pas actionnable.
    import random

    # Seuil absurde, au-dessus de tout : rien ne passera jamais.
    d = neuf(plancher=250)
    fait_ecouter(d, 90, 300)
    assert d.marge() == 0.0, d.marge()

    # Sur de la vraie musique, le seuil doit se poser entre la nappe et les
    # crêtes — ni en butée haute, ni collé à la nappe. Ce test tient MARGE_FOND
    # en laisse : c'est lui qui a attrapé le réglage à 1,6, où le seuil montait
    # sous les crêtes et où l'indicateur restait bloqué en bleu.
    microbit.remet_a_zero()
    random.seed(5)
    d = beat.Detecteur()
    for tic in range(1500):
        phase = tic % 25
        niveau = 90 + random.randint(-6, 6)
        if phase == 0:
            niveau = 150
        elif phase == 1:
            niveau = 130
        microbit.joue_niveaux([niveau])
        d.ecoute()
        microbit.avance(PAS_MS)
    assert 0.40 < d.marge() < 0.90, d.marge()


def test_pas_de_tempo_sans_temps_detectes():
    # Sans ce garde-fou, « parfaitement régulier » et « rien détecté » vaudraient
    # tous deux zéro et s'afficheraient pareil.
    d = neuf()
    fait_ecouter(d, 2, 300)
    assert not d.tempo_etabli()


if __name__ == "__main__":
    for nom, fonction in sorted(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("ok   %s" % nom)
    print("\ntous les tests passent")
