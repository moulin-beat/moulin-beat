"""Vérifie la détection de rythme : calibration, seuil, comptage, mesure."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import microbit
import beat


def test_calibration_retient_le_bruit_ambiant():
    # Une pièce qui bruisse à 40 doit installer 40 comme moyenne de départ,
    # sans quoi les premières secondes se remplissent de faux temps.
    microbit.remet_a_zero()
    microbit.joue_niveaux([40])
    d = beat.Detecteur()
    ambiant = d.calibre(duree=200)
    assert 39 <= ambiant <= 41, ambiant
    assert d.moyenne > 0


def test_calibration_releve_le_plancher_en_piece_bruyante():
    # Le plancher doit suivre le bruit ambiant, sinon le souffle d'une salle
    # pleine se fait détecter comme un rythme.
    microbit.remet_a_zero()
    microbit.joue_niveaux([100])
    d = beat.Detecteur(plancher=12)
    d.calibre(duree=200)
    assert d.plancher > 12, d.plancher


def test_calibration_ne_baisse_jamais_le_plancher():
    # Une pièce silencieuse ne doit pas rendre le détecteur hypersensible.
    microbit.remet_a_zero()
    microbit.joue_niveaux([1])
    d = beat.Detecteur(plancher=12)
    d.calibre(duree=200)
    assert d.plancher >= 12, d.plancher


def test_le_silence_ne_produit_aucun_temps():
    microbit.remet_a_zero()
    microbit.joue_niveaux([2])
    d = beat.Detecteur()
    d.calibre(duree=200)
    for _ in range(50):
        assert not d.ecoute()
        microbit.avance(20)
    assert d.compte == 0


def test_un_pic_franc_produit_un_temps():
    microbit.remet_a_zero()
    microbit.joue_niveaux([20])
    d = beat.Detecteur()
    d.calibre(duree=200)
    microbit.joue_niveaux([200])
    microbit.avance(500)
    assert d.ecoute()
    assert d.compte == 1


def test_le_temps_mort_evite_de_compter_deux_fois():
    # Une caisse claire produit plusieurs pics rapprochés : un seul temps.
    microbit.remet_a_zero()
    microbit.joue_niveaux([20])
    d = beat.Detecteur(temps_mort=150)
    d.calibre(duree=200)
    microbit.joue_niveaux([200])
    microbit.avance(500)
    assert d.ecoute()
    microbit.avance(30)
    assert not d.ecoute(), "pic rapproché compté une seconde fois"
    assert d.compte == 1


def test_le_rang_dans_la_mesure_tourne():
    microbit.remet_a_zero()
    d = beat.Detecteur()
    assert d.temps() == 0, "aucun temps détecté : rien à afficher"
    attendus = (1, 2, 3, 4, 1, 2)
    for attendu in attendus:
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
