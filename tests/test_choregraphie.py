"""Vérifie que chaque motif produit des vitesses valides et vivantes.

Lancer avec `make test`. Aucun robot n'est nécessaire : le module `microbit`
est remplacé par le bouchon voisin.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import microbit
import choregraphie

PAS_MS = 25
BEAT_TOUS_LES = 8   # un temps toutes les 200 ms, soit 300 BPM
DUREE = 40          # une seconde de simulation


def joue(motif, energie=0.7):
    microbit.remet_a_zero()
    trace = []
    for pas in range(DUREE):
        if pas % BEAT_TOUS_LES == 0:
            motif.sur_beat()
        trace.append(motif.tic(energie))
        microbit.avance(PAS_MS)
    return trace


def test_vitesses_dans_les_bornes():
    for classe in choregraphie.REPERTOIRE:
        for gauche, droite, contra in joue(classe()):
            assert 0 <= gauche <= 255, (classe.nom, gauche)
            assert 0 <= droite <= 255, (classe.nom, droite)
            assert isinstance(gauche, int) and isinstance(droite, int), classe.nom
            assert isinstance(contra, bool), classe.nom


def test_les_pales_bougent():
    # Un motif figé serait un bug : la sculpture ne raconterait plus rien.
    for classe in choregraphie.REPERTOIRE:
        trace = joue(classe())
        assert len(set(trace)) > 1, "%s ne varie pas dans le temps" % classe.nom


def test_le_silence_ne_lance_rien():
    # Un motif événementiel qui n'a reçu aucun temps doit laisser les pales
    # strictement immobiles. Ce test a déjà attrapé un vrai bug : un `debut`
    # initialisé à 0 déclenchait une impulsion pleine puissance au démarrage,
    # avant le moindre temps détecté.
    for classe in choregraphie.REPERTOIRE:
        if classe.continu:
            continue
        microbit.remet_a_zero()
        motif = classe()
        for _ in range(DUREE):
            gauche, droite, _contra = motif.tic(0.0)
            assert gauche == 0 and droite == 0, classe.nom
            microbit.avance(PAS_MS)


def test_tourbillon_s_inverse_sur_la_mesure():
    motif = choregraphie.Tourbillon(mesure=4)
    microbit.remet_a_zero()
    sens = motif.tic(0.5)[2]
    for _ in range(4):
        motif.sur_beat()
    assert motif.tic(0.5)[2] is not sens, "pas d'inversion au bout de 4 temps"


if __name__ == "__main__":
    for nom, fonction in sorted(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("ok   %s" % nom)
    print("\ntous les tests passent")
