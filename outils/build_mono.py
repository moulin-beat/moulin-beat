"""Fusionne les modules du projet en un unique script pour le micro:bit.

Pourquoi : `ufs` depose les modules un a un, mais il lui faut le REPL serie. Ce
canal se bloque regulierement — programme occupe, port pris par un autre outil,
DAPLink capricieux — et il devient alors impossible de mettre a jour le robot.

`uflash`, lui, passe par le volume USB de masse et ignore le port serie. Mais il
n'embarque qu'un seul script. On concatene donc les modules dans un fichier
unique, en fusionnant leurs imports `microbit` et en supprimant les prefixes de
module devenus inutiles puisque tout partage le meme espace de noms.

    python3 outils/build_mono.py    ->  build/moulin_beat.py
"""

import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "src")
SORTIE = os.path.join(RACINE, "build", "moulin_beat.py")

# L'ordre compte : chaque module ne doit dependre que de ce qui precede.
MODULES = ("maqueen", "beat", "choregraphie", "main")


def imports_microbit(texte):
    """Recupere les noms importes depuis `microbit`, sur une ou plusieurs lignes."""
    noms = set()
    for bloc in re.findall(r"from microbit import \(([^)]*)\)", texte):
        noms.update(n.strip() for n in bloc.split(",") if n.strip())
    for ligne in re.findall(r"from microbit import ([^(\n]+)", texte):
        noms.update(n.strip() for n in ligne.split(",") if n.strip())
    return noms


def nettoie(texte):
    """Retire les imports, que l'en-tete du fichier fusionne reprend en bloc."""
    texte = re.sub(r"from microbit import \([^)]*\)\n", "", texte)
    texte = re.sub(r"from microbit import [^(\n]+\n", "", texte)
    texte = re.sub(r"^import (%s)\n" % "|".join(MODULES), "", texte, flags=re.M)
    return texte


def deprefixe(texte):
    """`maqueen.arret()` devient `arret()` : un seul espace de noms desormais.

    Les noms des quatre modules ne se recouvrent pas, la fusion est donc sure.
    Le script verifie cette absence de collision avant d'ecrire quoi que ce soit.
    """
    for module in MODULES:
        texte = re.sub(r"\b%s\.(\w)" % module, r"\1", texte)
    return texte


def noms_definis(texte):
    return set(re.findall(r"^(?:def|class)\s+(\w+)", texte, flags=re.M)) | \
           set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", texte, flags=re.M))


def construis():
    sources = {}
    for module in MODULES:
        with open(os.path.join(SOURCE, module + ".py")) as f:
            sources[module] = f.read()

    # Garde-fou : deux modules qui definiraient le meme nom se marcheraient
    # dessus en silence une fois fusionnes, et le bug serait indechiffrable.
    vus = {}
    for module in MODULES:
        for nom in noms_definis(sources[module]):
            if nom in vus:
                raise SystemExit(
                    "collision de nom : %s defini dans %s et %s"
                    % (nom, vus[nom], module))
            vus[nom] = module

    noms = set()
    for texte in sources.values():
        noms |= imports_microbit(texte)

    morceaux = [
        '"""moulin-beat, tous modules fusionnes.\n\n'
        "Fichier GENERE par outils/build_mono.py — ne pas editer a la main.\n"
        "Les sources sont dans src/.\n"
        '"""\n',
        "from microbit import %s\n" % ", ".join(sorted(noms)),
    ]

    for module in MODULES:
        corps = deprefixe(nettoie(sources[module])).strip()
        morceaux.append("\n\n# %s\n# %s\n\n%s\n" % (module, "-" * len(module), corps))

    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w") as f:
        f.write("\n".join(morceaux))

    print("%s ecrit (%d octets)" % (SORTIE, os.path.getsize(SORTIE)))
    return SORTIE


if __name__ == "__main__":
    construis()
