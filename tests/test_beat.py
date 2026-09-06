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


if __name__ == "__main__":
    for nom, fonction in sorted(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("ok   %s" % nom)
    print("\ntous les tests passent")
