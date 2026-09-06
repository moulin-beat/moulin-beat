"""Vérifie que chaque motif produit des vitesses valides et vivantes.

Lancer avec `make test`. Aucun robot n'est nécessaire : le module `microbit`
est remplacé par le bouchon voisin.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import random

import microbit
import choregraphie

PAS_MS = 25
BEAT_TOUS_LES = 8   # un temps toutes les 200 ms, soit 300 BPM
DUREE = 40          # une seconde de simulation


def joue(motif, energie=0.7):
    microbit.remet_a_zero()
    # Aleatoire tire un motif au sort : sans graine fixe, le test passerait ou
    # non selon le tirage, ce qui est la pire espece de test.
    random.seed(4)
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


def test_chaque_motif_marque_le_temps():
    # LE test du répertoire : une pale qui tourne à vitesse constante ne
    # raconte rien, on ne voit plus la musique mais un moteur. Chaque motif
    # doit donc donner un coup au temps et RETOMBER franchement avant le
    # suivant. Ce test a déjà attrapé un vrai bug : un lissage trop lent
    # ramenait tout le répertoire à une rotation continue dès que la musique
    # durait un peu.
    for classe in choregraphie.REPERTOIRE:
        trace = [max(g, d) for g, d, _c in joue(classe())]
        sommet = max(trace)
        assert sommet > 0, classe.nom
        # Le tic juste avant chaque temps : c'est là que le motif est au plus
        # bas de sa retombée.
        for pas in range(BEAT_TOUS_LES, DUREE, BEAT_TOUS_LES):
            creux = trace[pas - 1]
            assert creux <= 0.8 * sommet, (classe.nom, creux, sommet)


def test_aleatoire_change_de_motif_et_jamais_pour_le_meme():
    # Sur quatre possibilités, retomber sur le même donnerait deux minutes
    # identiques et l'on croirait à une panne.
    microbit.remet_a_zero()
    random.seed(7)
    meta = choregraphie.Aleatoire(duree=100)
    vus = []
    for _ in range(12):
        vus.append(type(meta.motif))
        microbit.avance(150)
        meta.tic(0.5)
    assert len(set(vus)) > 1, "aucun changement de motif"
    for avant, apres in zip(vus, vus[1:]):
        assert avant is not apres, [c.nom for c in vus]


def test_aleatoire_delegue_vraiment():
    # Un enveloppeur qui oublierait de transmettre sur_beat laisserait les
    # pales immobiles sans que rien ne le signale.
    microbit.remet_a_zero()
    random.seed(1)
    meta = choregraphie.Aleatoire()
    meta.sur_beat()
    trace = [max(g, d) for g, d, _c in
             [meta.tic(0.7) for _ in range(3)]]
    assert max(trace) > 0, trace


def test_le_motif_de_depart_est_percussif():
    # Le premier du répertoire est celui qui démarre : il doit s'arrêter net
    # entre deux temps, sinon le premier essai donne un moteur qui ronronne.
    depart = choregraphie.REPERTOIRE[0]
    assert not depart.continu, depart.nom


if __name__ == "__main__":
    for nom, fonction in sorted(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("ok   %s" % nom)
    print("\ntous les tests passent")
