"""Vérifie ce que le pilote envoie vraiment sur le bus.

Ces tests existent pour une raison précise : un motif peut commander l'arrêt en
toute bonne foi sans que les pales s'arrêtent pour autant. Vitesse zéro laisse
le pont en H en roue libre et l'inertie fait le reste. On vérifie donc les
trames, pas les intentions.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import microbit
import maqueen


def neuf():
    microbit.remet_a_zero()
    maqueen._lancee[:] = [False, False]


def trames():
    """Les trames moteur écrites depuis la remise à zéro, décodées."""
    return [(t[0], t[1], t[2]) for _adresse, t in microbit.i2c.ecrites
            if len(t) == 3]


def test_l_arret_est_bien_transmis():
    # Le cas de base : commander zéro doit produire une trame à zéro sur les
    # deux roues, pas seulement l'absence d'ordre.
    neuf()
    maqueen.pales(200, 200)
    maqueen.pales(0, 0)
    zeros = [t for t in trames() if t[2] == 0]
    assert any(t[0] == maqueen.GAUCHE for t in zeros), trames()
    assert any(t[0] == maqueen.DROITE for t in zeros), trames()


def test_l_arret_freine_la_roue_lancee():
    # LE test qui compte pour les à-coups : entre deux temps il faut une
    # impulsion à contresens, sinon les pales finissent leur élan et la
    # sculpture n'a plus l'air que d'un moteur qui tourne.
    neuf()
    maqueen.pales(255, 0)
    debut = len(microbit.i2c.ecrites)
    maqueen.pales(0, 0)
    apres = trames()[debut:]
    freins = [t for t in apres
              if t[0] == maqueen.GAUCHE and t[1] == maqueen.ANTIHORAIRE and t[2]]
    assert freins, ("aucune impulsion de freinage", apres)
    assert apres[-1][2] == 0, ("le freinage doit finir par un arret", apres)


def test_on_ne_freine_pas_une_roue_deja_arretee():
    # Sinon chaque tic de silence enverrait une impulsion : la roue vibrerait
    # en permanence et le bus serait saturé pour rien.
    neuf()
    maqueen.pales(0, 0)
    debut = len(microbit.i2c.ecrites)
    for _ in range(5):
        maqueen.pales(0, 0)
    assert all(t[2] == 0 for t in trames()[debut:]), trames()


def test_une_roue_coupee_ne_recoit_jamais_de_vitesse():
    # La sculpture n'a qu'une croix de pales : la roue droite est désactivée et
    # ne doit tourner sous aucun prétexte, même si un motif la commande.
    neuf()
    assert not maqueen.ROUE_DROITE_ACTIVE, "réglage attendu par ce test"
    for _ in range(10):
        maqueen.pales(255, 255)
    droite = [t for t in trames() if t[0] == maqueen.DROITE]
    assert droite, "la roue coupée doit quand meme recevoir un ordre d'arret"
    assert all(t[2] == 0 for t in droite), droite


def test_l_amortissement_va_de_la_roue_libre_au_frein_sec():
    # Le réglage de scène, boutons A et B. Les deux bouts comptent : zéro doit
    # vraiment supprimer le freinage, pas le réduire.
    neuf()
    assert maqueen.regle_amortissement(0) == 0
    assert maqueen.frein_ms() == 0
    assert maqueen.regle_amortissement(maqueen.AMORTISSEMENT_MAX) \
        == maqueen.AMORTISSEMENT_MAX
    assert maqueen.frein_ms() == maqueen.FREIN_MS_MAX
    # Monotone entre les deux, sinon un cran rendrait le mouvement plus mou.
    durees = []
    for niveau in range(maqueen.AMORTISSEMENT_MAX + 1):
        maqueen.regle_amortissement(niveau)
        durees.append(maqueen.frein_ms())
    assert durees == sorted(durees) and len(set(durees)) == len(durees), durees
    maqueen.regle_amortissement(maqueen.AMORTISSEMENT_DEFAUT)


def test_l_amortissement_reste_dans_ses_bornes():
    # Les boutons ne font qu'incrémenter : il faut buter, pas déborder.
    neuf()
    for _ in range(20):
        maqueen.regle_amortissement(maqueen.amortissement() - 1)
    assert maqueen.amortissement() == 0
    for _ in range(20):
        maqueen.regle_amortissement(maqueen.amortissement() + 1)
    assert maqueen.amortissement() == maqueen.AMORTISSEMENT_MAX
    maqueen.regle_amortissement(maqueen.AMORTISSEMENT_DEFAUT)


def test_amortissement_zero_laisse_la_roue_libre():
    # À zéro, aucune impulsion à contresens ne doit partir : c'est le rendu
    # fluide d'avant le freinage, et il doit être vraiment atteignable.
    neuf()
    maqueen.regle_amortissement(0)
    maqueen.pales(255, 0)
    debut = len(microbit.i2c.ecrites)
    maqueen.pales(0, 0)
    apres = trames()[debut:]
    assert all(t[2] == 0 for t in apres), apres
    maqueen.regle_amortissement(maqueen.AMORTISSEMENT_DEFAUT)


def test_les_led_de_sol_s_eteignent_a_l_arret():
    # Les LED de sol font partie de l'arrêt : un robot à l'arrêt doit être
    # visiblement à l'arrêt.
    neuf()
    maqueen.sol([(9, 9, 9)] * maqueen.SOL_PIXELS)
    maqueen.arret()
    assert maqueen._sol.pixels == [(0, 0, 0)] * maqueen.SOL_PIXELS


def test_la_vitesse_minimale_est_un_plancher_pas_un_arret():
    # Zéro reste zéro : un plancher qui remonterait 0 à 40 ferait tourner les
    # pales en permanence.
    assert maqueen._borne(0) == 0
    assert maqueen._borne(1) == maqueen.VITESSE_MIN
    assert maqueen._borne(999) == maqueen.VITESSE_MAX


if __name__ == "__main__":
    for nom, fonction in sorted(globals().items()):
        if nom.startswith("test_"):
            fonction()
            print("ok   %s" % nom)
    print("\ntous les tests passent")
