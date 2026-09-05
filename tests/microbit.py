"""Bouchon du module `microbit`, pour tester sur un PC.

Ni `choregraphie.py` ni `beat.py` ne touchent au matériel autrement que par ce
module : c'est précisément ce qui rend ces tests possibles sans robot.

L'horloge n'avance que sur appel explicite — `avance()` ou `sleep()`. Un test
contrôle donc exactement le temps qui passe, sans rien attendre en vrai.
"""

_horloge = [0]

# Niveaux sonores que `microphone.sound_level()` rendra, consommés dans l'ordre.
# La dernière valeur se répète une fois la liste épuisée.
_niveaux = [0]


def running_time():
    return _horloge[0]


def sleep(ms):
    _horloge[0] += int(ms)


def avance(ms):
    _horloge[0] += ms


def remet_a_zero():
    _horloge[0] = 0
    _niveaux[:] = [0]


def joue_niveaux(valeurs):
    """Installe la suite de niveaux sonores que le micro rendra."""
    _niveaux[:] = list(valeurs)


class _Microphone:
    def sound_level(self):
        if len(_niveaux) > 1:
            return _niveaux.pop(0)
        return _niveaux[0]


microphone = _Microphone()


class _Broche:
    """Phare du Maqueen. Retient son état pour que les tests le vérifient."""

    def __init__(self):
        self.etat = 0

    def write_digital(self, valeur):
        self.etat = valeur


pin8 = _Broche()
pin12 = _Broche()


class _I2C:
    def __init__(self):
        self.ecrites = []

    def write(self, adresse, donnees, repeat=True):
        self.ecrites.append((adresse, bytes(donnees)))

    def scan(self):
        return [0x10]


i2c = _I2C()
