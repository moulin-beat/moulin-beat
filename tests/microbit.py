"""Bouchon du module `microbit`, pour tester les chorégraphies sur un PC.

Seul `running_time` est nécessaire : `choregraphie.py` ne touche à rien d'autre
du matériel, c'est précisément ce qui rend ce test possible.
"""

_horloge = [0]


def running_time():
    return _horloge[0]


def avance(ms):
    _horloge[0] += ms


def remet_a_zero():
    _horloge[0] = 0
