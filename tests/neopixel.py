"""Bouchon du module `neopixel`, pour tester les LED de sol sans robot."""


class NeoPixel:
    def __init__(self, broche, nombre):
        self.broche = broche
        self.pixels = [(0, 0, 0)] * nombre
        self.montres = []

    def __setitem__(self, rang, couleur):
        self.pixels[rang] = tuple(couleur)

    def __getitem__(self, rang):
        return self.pixels[rang]

    def show(self):
        self.montres.append(list(self.pixels))
